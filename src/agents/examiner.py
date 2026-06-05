from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState


class ExaminerAgent(BaseAgent):
    role = AgentRole.EXAMINER
    description = "考试指导Agent：分析考试要求→评估当前水平→制定备考计划→提供策略指导"

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        plan = state.get("learning_plan")
        weak = state.get("weak_points") or []

        plan_info = ""
        if plan and isinstance(plan, dict):
            plan_phases = plan.get("phases", [])
            plan_info = (
                f"## 当前学习计划\n"
                f"标题: {plan.get('title', '未设定')}\n"
                f"阶段数: {len(plan_phases)}\n"
            )

        weak_info = "\n".join(f"- {w.get('knowledge_point', str(w))}" for w in weak[:5])

        return f"""你是一个资深的考试和面试指导专家。为考生提供最实用的备考策略。

## 考生信息
- 姓名: {profile.get('name', '考生')}
- 当前水平: {profile.get('level', '未评估')}
- 目标: {profile.get('target_field', '未设定')}

{plan_info}

## 薄弱知识点
{weak_info or '暂无'}

## 指导策略框架
1. **考试分析**：分析考试类型（考研/面试/笔试等）的要求和特点
2. **水平评估**：根据当前水平和薄弱点，评估差距
3. **备考计划**：制定详细的备考时间表和复习节奏
4. **重点突破**：针对薄弱知识点给出专项训练方案
5. **应试技巧**：提供实用的考试策略和时间管理建议
6. **模拟建议**：推荐模拟考试的频率和方法

## 输出要求
以结构化方式输出完整的考试指导方案。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "请根据我的学习情况，给我制定一个考试备考方案"
        history = self._extract_history(state)
        response = self._chat(system_prompt, user_msg, history=history, temperature=0.6, max_tokens=2048)

        state_changes: dict[str, Any] = {"current_agent": self.role}

        logger.info("ExaminerAgent 完成")
        return AgentResult(
            agent_role=self.role,
            output={
                "exam_guidance": response,
                "target": (state.get("user_profile") or {}).get("target_field", "未设定"),
            },
            state_changes=state_changes,
        )