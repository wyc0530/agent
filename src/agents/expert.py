from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.tools.search import WebSearchTool
from src.core.tools.document import DocumentGenerator


class ExpertAgent(BaseAgent):
    role = AgentRole.EXPERT
    description = "学习专家Agent：分析主题→搜索资料→评估→推荐学习内容与课程"

    def __init__(self) -> None:
        super().__init__()
        self._searcher = WebSearchTool()
        self._doc_gen = DocumentGenerator()

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        plan = state.get("learning_plan")

        plan_context = ""
        if plan and isinstance(plan, dict):
            plan_phases = plan.get("phases", [])
            if plan_phases:
                phases_desc = "\n".join(
                    f"- {p.get('phase_name', p.get('name', ''))}: {p.get('phase_description', p.get('description', ''))}"
                    for p in plan_phases[:3] if isinstance(p, dict)
                )
                plan_context = f"## 当前学习计划中的阶段\n{phases_desc}"

        return f"""你是一个专业的学习指导专家。根据学习阶段推荐最适合的学习资料和课程。

## 用户信息
- 当前水平: {profile.get('level', '未评估')}
- 学习偏好: {profile.get('preference', '综合学习')}

{plan_context}

## 输出要求
为指定的学习主题提供：
1. **核心知识点**：该主题的关键概念（3-5个）
2. **推荐学习路径**：从入门到精通的步骤
3. **学习资料**：推荐的书籍、课程、在线资源
4. **实践建议**：配套的练习和项目

请以结构化格式输出，便于生成文档。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "请推荐当前阶段的学习资料"
        response = self._chat(system_prompt, user_msg, temperature=0.7, max_tokens=2048)

        state_changes: dict[str, Any] = {"current_agent": self.role}

        web_results: list[dict[str, Any]] = []
        try:
            lc = state.get("learning_content")
            topic = (lc.get("topic", "学习资料") if isinstance(lc, dict) else "学习资料") if lc else "学习资料"
            web_results = self._searcher.execute(query=message or topic)
        except Exception as e:
            logger.warning(f"ExpertAgent 搜索失败: {e}")

        doc_content: dict[str, Any] = {"type": "learning_material", "topic": message}
        try:
            doc = self._doc_gen.execute(
                doc_type="course_recommendation",
                data={"materials": web_results},
                title=f"推荐学习: {message}",
            )
            doc_content["document"] = doc
        except Exception as e:
            logger.warning(f"ExpertAgent 文档生成失败: {e}")

        if response:
            doc_content["ai_recommendation"] = response

        logger.info(f"ExpertAgent 完成 | topic={message}")
        return AgentResult(
            agent_role=self.role,
            output=doc_content,
            state_changes=state_changes,
        )