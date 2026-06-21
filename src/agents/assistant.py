import asyncio
from typing import Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState


_INTENT_PATTERNS: list[tuple[list[str], AgentRole]] = [
    (["制定计划", "学习计划", "规划", "安排", "方案"], AgentRole.PLANNER),
    (["推荐", "资料", "资料推荐", "课程", "教材", "学什么", "资源"], AgentRole.EXPERT),
    (["不会", "怎么", "什么是", "解释", "问题", "帮我理解", "答疑", "请教"], AgentRole.PARTNER),
    (["出题", "做题", "题目", "测试一下", "练习", "自测", "测验"], AgentRole.QUIZZER),
    (["复习", "错题", "整理", "回顾", "总结", "分析错误", "薄弱"], AgentRole.REVIEWER),
    (["考试", "面试", "备考", "应试", "笔试", "考研", "准备"], AgentRole.EXAMINER),
]

ROLE_DESCRIPTIONS: dict[AgentRole, str] = {
    AgentRole.PLANNER: "制定学习计划、安排学习方案",
    AgentRole.EXPERT: "推荐学习资料、搜索课程资源",
    AgentRole.PARTNER: "答疑解惑、陪伴学习、解释概念",
    AgentRole.QUIZZER: "生成练习题、评估能力水平",
    AgentRole.REVIEWER: "错题分析、薄弱点总结、复习整理",
    AgentRole.EXAMINER: "备考策略、面试指导、考试规划",
}

_PARALLEL_SEMAPHORE = asyncio.Semaphore(10)

_LLM_CLASSIFY_PROMPT = """分析用户消息，判断最适合处理该请求的Agent角色。

## 可用角色
- planner: 制定学习计划、安排学习方案
- expert: 推荐学习资料、搜索课程资源
- partner: 答疑解惑、陪伴学习、解释概念
- quizzer: 生成练习题、评估能力水平
- reviewer: 错题分析、薄弱点总结
- examiner: 备考策略、面试指导、考试规划

## 用户消息
{message}

## 指令
只回复一个角色名称，不要任何其他内容。示例: planner"""


class SupervisorAgent(BaseAgent):
    role = AgentRole.ASSISTANT
    description = "助教Agent：意图识别→路由→聚合→回复用户"

    def __init__(self) -> None:
        super().__init__()
        self._agents: dict[AgentRole, BaseAgent] = {}
        self._compiled_graph = None
        self._comm_started = False

    def register_sub_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.role] = agent
        self._compiled_graph = None
        logger.info(f"助教注册子Agent | role={agent.role.value}")

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        return f"""你是学习助教，负责理解学生需求并协调各个专业Agent。

## 当前学生
- 姓名: {profile.get('name', '同学')}
- 水平: {profile.get('level', '未评估')}

## 可用Agent
1. **学习规划** - 制定学习计划、安排学习方案
2. **学习专家** - 推荐学习资料、搜索课程
3. **学习伙伴** - 答疑解惑、陪伴学习
4. **个性出题** - 生成练习题、评估能力
5. **复习整理** - 错题分析、薄弱点总结
6. **考试指导** - 备考策略、面试指导

## 你的任务
分析用户需求，将请求路由到最合适的Agent。如果是复合请求，可以调用多个Agent协作。"""

    def _classify_intent(self, message: str) -> list[AgentRole]:
        message_lower = message.lower()
        scored: list[tuple[AgentRole, int]] = []
        for keywords, role in _INTENT_PATTERNS:
            score = sum(1 for kw in keywords if kw in message_lower or kw in message)
            if score > 0:
                scored.append((role, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        roles = [r for r, _ in scored[:3]]
        if not roles:
            roles = [AgentRole.PARTNER]
        if len(roles) == 1 and roles[0] == AgentRole.PARTNER and len(message) > 10 and scored and scored[0][1] <= 1:
            llm_role = self._llm_classify_intent(message)
            if llm_role is not None and llm_role in self._agents:
                roles = [llm_role]
                logger.info(f"LLM语义路由覆盖 | message={message[:40]} -> {llm_role.value}")
        return roles

    def _llm_classify_intent(self, message: str) -> Optional[AgentRole]:
        """当关键词匹配不确定时，使用LLM进行语义意图分类。

        仅返回已注册且有对应Agent的角色，失败时返回None。
        """
        try:
            raw = self._chat(
                "你是一个意图分类器。",
                _LLM_CLASSIFY_PROMPT.format(message=message),
                temperature=0.1,
                max_tokens=16,
            )
            label = raw.strip().lower()
            for role in AgentRole:
                if role.value in label or role.value == label:
                    return role
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"LLM意图分类失败: {e}")
        return None

    def run(self, state: LearningState, message: str = "", target_role: Optional[AgentRole] = None) -> AgentResult:
        if not message:
            return AgentResult.empty(agent_role=self.role)

        if target_role is not None:
            target_agent = self._agents.get(target_role)
            if target_agent is None:
                return AgentResult(
                    agent_role=target_role,
                    output={"reply": f"未找到对应的 Agent: {target_role.value}"},
                    error=f"No agent registered for role: {target_role.value}",
                )
            return target_agent.run(state, message)

        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        if not message:
            return AgentResult(
                agent_role=self.role,
                output={"reply": "你好！我是你的学习助教。有什么我可以帮你的吗？"},
            )

        self._ensure_communication(state)

        matched_roles = self._classify_intent(message)
        primary_role = matched_roles[0]

        logger.info(f"Supervisor 意图识别 | message={message[:60]} -> {[r.value for r in matched_roles]}")

        if primary_role in self._agents:
            agent = self._agents[primary_role]
            result = agent.run(state, message)
        else:
            system_prompt = self._build_system_prompt(state)
            fallback = self._chat(system_prompt, message, temperature=0.7)
            result = AgentResult(
                agent_role=self.role,
                output={"reply": fallback, "routed_to": "assistant"},
            )

        if not result.success:
            existing_reply = result.output.get("reply", "")
            error_part = f"抱歉，{primary_role.value} 处理时遇到了问题：{result.error}\n请稍后再试。"
            result.output["reply"] = f"{existing_reply}\n{error_part}" if existing_reply else error_part

        self._emit_result_signal(state, result, primary_role)

        logger.info(f"Supervisor 路由完成 | -> {primary_role.value} success={result.success}")
        return result

    def _ensure_communication(self, state: LearningState):
        """初始化Communication模块并注册Supervisor为消息监听者。

        仅在首次调用时初始化，后续调用跳过。
        """
        if self._comm_started:
            return
        try:
            from src.core.communication import AgentCommunication

            comm = AgentCommunication()
            user_id = state.get("user_id", "")
            if not user_id:
                return

            comm.register_agent(self.role, self._on_comm_signal)

            self._comm_started = True
            logger.info(f"Agent通信系统已初始化 | user={user_id}")
        except (ValueError, RuntimeError, ImportError) as e:
            logger.debug(f"Agent通信系统初始化跳过: {e}")

    def _on_comm_signal(self, payload: dict[str, Any]):
        """处理来自其他Agent的通信信号。"""
        signal_type = payload.get("type", "")
        from_agent = payload.get("from_agent", "")
        logger.info(f"Agent通信信号 | type={signal_type} from={from_agent}")

    def _emit_result_signal(self, state: LearningState, result: AgentResult, role: AgentRole):
        """Agent处理完成后记录通信信号。

        在同步上下文中记录信号日志，异步信号发送留给事件循环处理。
        """
        if not self._comm_started:
            return
        try:
            reply_content = result.output.get("reply", "") or ""
            status = "success" if result.success else "error"
            logger.debug(
                f"Agent通信信号 | source={self.role.value} target={role.value} "
                f"status={status} summary={reply_content[:60]}"
            )
        except (ValueError, RuntimeError, ImportError) as e:
            logger.debug(f"Agent信号发送跳过: {e}")

    async def run_parallel(
        self, state: LearningState, message: str
    ) -> list[AgentResult]:
        matched_roles = self._classify_intent(message)
        tasks = []
        for r in matched_roles:
            if r in self._agents:
                async def _run_with_semaphore(role=r):
                    async with _PARALLEL_SEMAPHORE:
                        return await asyncio.to_thread(self._agents[role].run, state, message)
                tasks.append(_run_with_semaphore())
        if not tasks:
            return [self.run(state, message)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        clean: list[AgentResult] = []
        for r in results:
            if isinstance(r, AgentResult):
                clean.append(r)
            elif isinstance(r, Exception):
                clean.append(AgentResult(
                    agent_role=self.role, success=False, error=str(r),
                ))
        return clean

    def aggregate_results(self, results: list[AgentResult]) -> str:
        parts = []
        known_keys = {"answer", "analysis", "reply", "plan_text", "ai_recommendation", "exam_guidance", "strategy", "feedback_for_planner", "content"}
        for r in results:
            if r.success and r.output:
                found = None
                for key in known_keys:
                    val = r.output.get(key)
                    if val and isinstance(val, str) and len(val) > 5:
                        found = val
                        break
                if not found:
                    for key, val in r.output.items():
                        if isinstance(val, str) and len(val) > 5:
                            found = val
                            break
                if found:
                    parts.append(f"### {r.agent_role.value}\n{found}")
        if not parts:
            parts.append("未能获取有效回复，请尝试更具体的提问。")
        return "\n\n---\n\n".join(parts)

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(LearningState)

        def _supervisor_node(state: LearningState) -> dict[str, Any]:
            message = state.get("messages", [])
            text = ""
            if message:
                last_msg = message[-1]
                text = last_msg.get("content", "") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
            matched = self._classify_intent(text)
            primary = matched[0] if matched else AgentRole.PARTNER
            logger.info(f"LangGraph Supervisor 路由 | -> {primary.value}")
            return {"current_agent": primary.value}

        graph.add_node("supervisor", _supervisor_node)

        def _make_agent_node(role: AgentRole):
            def _node(state: LearningState) -> dict[str, Any]:
                message = state.get("messages", [])
                text = ""
                if message:
                    last_msg = message[-1]
                    text = last_msg.get("content", "") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
                if role in self._agents:
                    result = self._agents[role].run(state, text)
                    if result.success and result.output:
                        reply = (
                            result.output.get("reply")
                            or result.output.get("answer")
                            or result.output.get("plan_text")
                            or result.output.get("ai_recommendation")
                            or result.output.get("exam_guidance")
                            or result.output.get("analysis")
                            or result.output.get("strategy")
                            or (str(result.output) if result.output else "处理完成")
                        )
                        return {"agent_outputs": {role.value: result.output}, "messages": [{"role": role.value, "content": reply}]}
                    return {"error_message": result.error or f"{role.value} 处理失败"}
                return {"error_message": f"Agent {role.value} 未注册"}
            return _node

        for role in AgentRole:
            if role in self._agents:
                graph.add_node(role.value, _make_agent_node(role))

        agent_roles_set = frozenset(r.value for r in self._agents)

        def _route_supervisor(state: LearningState) -> str:
            current = state.get("current_agent", "")
            if current in agent_roles_set:
                return current
            return END

        graph.add_conditional_edges("supervisor", _route_supervisor, list(agent_roles_set) + [END])

        for role in self._agents:
            graph.add_edge(role.value, END)

        graph.set_entry_point("supervisor")
        return graph

    def run_with_langgraph(self, state: LearningState, message: str = "") -> AgentResult:
        if not self._agents:
            return self.run(state, message)

        try:
            if self._compiled_graph is None:
                graph = self._build_graph()
                from src.core.checkpoint import get_checkpoint_manager
                checkpointer = get_checkpoint_manager().saver
                self._compiled_graph = graph.compile(checkpointer=checkpointer)
                logger.info("LangGraph 图已编译并缓存")

            run_state: LearningState = {
                **state,
                "messages": state.get("messages", []) + [{"role": "user", "content": message}],
            }

            thread_id = state.get("user_id") or state.get("thread_id") or "default"
            result_state = self._compiled_graph.invoke(
                run_state,
                config={"configurable": {"thread_id": thread_id}},
            )

            outputs = result_state.get("agent_outputs", {})
            if outputs:
                primary_role = result_state.get("current_agent", "partner")
                primary_output = outputs.get(primary_role, list(outputs.values())[0])
                return AgentResult(
                    agent_role=self.role,
                    output={"reply": str(primary_output), "routed_to": primary_role, "all_outputs": outputs},
                    state_changes={"agent_outputs": outputs, "current_agent": primary_role},
                )
            return AgentResult(
                agent_role=self.role,
                output={"reply": result_state.get("error_message", "处理完成")},
            )
        except Exception as e:
            logger.warning(f"LangGraph 执行失败，回退到直接路由: {e}")
            return self.run(state, message)