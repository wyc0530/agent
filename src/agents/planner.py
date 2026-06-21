from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.tools.timer import FocusTimer
from src.core.graph import get_graph_store

_FALLBACK_PLANNER_TEXT = (
    "抱歉，学习规划师当前无法生成学习计划（LLM 服务暂时不可用）。\n\n"
    "建议：\n"
    "- 请稍后重试\n"
    "- 检查 API 密钥是否有效\n"
    "- 检查网络连接是否正常\n"
)


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER
    description = "学习规划Agent：分析用户目标→拆解阶段→生成结构化学习方案"

    def __init__(self) -> None:
        super().__init__()
        self._timer = FocusTimer()
        self._graph = get_graph_store()

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        plan = state.get("learning_plan")
        weak = state.get("weak_points") or []
        current_plan_text = ""
        if plan and isinstance(plan, dict):
            plan_phases = plan.get("phases", [])
            current_plan_text = (
                f"## 当前学习计划\n"
                f"标题: {plan.get('title', '未设定')}\n"
                f"阶段数: {len(plan_phases)}\n"
            )

        weak_text = "\n".join(f"- {w.get('knowledge_point', w)}" for w in weak[:5]) if weak else "暂无"

        time_info = ""
        try:
            summary = self._timer.get_summary()
            time_info = (
                f"- 今日专注会话: {summary.get('today_sessions', 0)} 次\n"
                f"- 今日累计专注: {summary.get('today_total_minutes', 0)} 分钟\n"
                f"- 历史总会话: {summary.get('all_sessions', 0)} 次\n"
            )
        except (AttributeError, ValueError, RuntimeError, OSError) as e:
            logger.debug(f"计时器摘要获取失败: {e}")

        graph_context = ""
        try:
            target_field = profile.get("target_field", "")
            if target_field:
                related = self._graph.search_nodes(target_field, limit=5)
                if related:
                    nodes_desc = "\n".join(
                        f"  - {n.get('name', '')} ({n.get('node_type', '')}): {n.get('description', '')}"
                        for n in related[:5]
                    )
                    graph_context = f"## 知识图谱关联节点\n{nodes_desc}\n"
        except (AttributeError, ValueError, RuntimeError, OSError) as e:
            logger.debug(f"知识图谱搜索失败: {e}")

        return f"""你是一个专业的学习规划师。根据用户信息和目标制定系统化的学习方案。

## 用户画像
- 姓名: {profile.get('name', '未知')}
- 当前水平: {profile.get('level', '未评估')}
- 可用时间: {profile.get('available_time', '未设置')} 小时/周
- 目标领域: {profile.get('target_field', '未设定')}

## 学习时间统计
{time_info or "暂无学习记录"}

{current_plan_text}

## 薄弱知识点
{weak_text}

{graph_context}
## 输出要求
根据用户消息中的指令生成对应的学习方案。请以自然语言文本格式输出，使用清晰的标题、段落和列表结构，使内容易于阅读。

输出应包含以下内容：
1. **学习计划标题** - 概括整体方向
2. **学习目标** - 列出2-4个具体目标，包含优先级和预计完成时间
3. **学习阶段** - 分阶段描述学习路径，每个阶段包含主题、描述和预计时长
4. **建议作息** - 根据用户可用时间给出每日/每周学习建议

使用Markdown格式组织内容，确保从基础到进阶的递进关系清晰。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "请根据我的当前情况生成一个详细的学习计划"

        state_changes: dict[str, Any] = {"current_agent": self.role}
        history = self._extract_history(state)

        try:
            response = self._chat(system_prompt, user_msg, history=history, temperature=0.6, max_tokens=2048)
        except Exception as e:
            logger.error(f"PlannerAgent LLM 调用完全失败: {e}")
            return AgentResult(
                agent_role=self.role,
                output={
                    "plan_text": _FALLBACK_PLANNER_TEXT,
                    "summary": "学习计划生成失败",
                    "phases_count": 0,
                },
                state_changes=state_changes,
                success=False,
                error=f"LLM 调用失败: {e}",
            )

        state_changes["learning_plan"] = {"title": "学习计划", "raw_response": response, "phases": [], "goals": []}

        output = {
            "plan_text": response,
            "summary": "学习计划",
            "phases_count": 0,
        }

        logger.info(f"PlannerAgent 完成")
        return AgentResult(
            agent_role=self.role,
            output=output,
            state_changes=state_changes,
        )