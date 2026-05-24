import random
import threading
from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.tools.quiz import AbilityAssessor, QuizGenerator


class QuizzerAgent(BaseAgent):
    role = AgentRole.QUIZZER
    description = "个性出题Agent：分析薄弱点→出题→评估→RL动态调整难度"

    def __init__(self) -> None:
        super().__init__()
        self._quiz_gen = QuizGenerator()
        self._assessor = AbilityAssessor()
        self._difficulty_cache: dict[str, float] = {}
        self._difficulty_lock = threading.Lock()

    def _build_system_prompt(self, state: LearningState) -> str:
        errors = state.get("error_records") or []
        weak = state.get("weak_points") or []
        quiz_results = state.get("quiz_results") or []

        error_summary = ""
        for e in errors[:5]:
            kp = e.get("knowledge_point", "未知")
            err_count = e.get("error_count", 0)
            error_summary += f"- {kp}: 错误{err_count}次\n"

        correct = sum(1 for r in quiz_results[-10:] if r.get("is_correct", False))
        total = len(quiz_results[-10:]) or 1
        recent_score = correct / total

        return f"""你是一个专业的出题教师。根据学生的学习情况，生成最合适题目。

## 学生评估
- 近期正确率: {recent_score:.0%}
- 薄弱知识点:
{error_summary or "暂无"}

## 出题策略 (强化学习驱动)
- 学生正确率 > 80%：适当提高难度
- 学生正确率 50-80%：维持当前难度
- 学生正确率 < 50%：降低难度，加强基础
- 优先出薄弱知识点的题目

## 输出要求
生成合适数量和难度的题目，确保覆盖核心知识点和薄弱环节。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        weak = state.get("weak_points") or []
        errors = state.get("error_records") or []

        weak_points_list = [
            w.get("knowledge_point", str(w)) if isinstance(w, dict) else str(w)
            for w in weak[:5]
        ]
        topic = message or "综合"

        user_id = state.get("user_id") or "default"
        current_difficulty = self._difficulty_cache.get(user_id, 0.5)

        quiz_results = state.get("quiz_results") or []
        recent = quiz_results[-10:]
        if recent:
            correct_rate = sum(
                1 for r in recent
                if isinstance(r, dict) and r.get("is_correct", False)
            ) / len(recent)
            with self._difficulty_lock:
                self._adjust_difficulty(user_id, correct_rate, self._difficulty_cache.get(user_id, 0.5))
                current_difficulty = self._difficulty_cache.get(user_id, 0.5)

        questions = []
        try:
            questions = self._quiz_gen.execute(
                topic=topic,
                difficulty=current_difficulty,
                count=max(3, len(weak_points_list) + 1),
                weak_points=weak_points_list if weak_points_list else [topic],
            )
        except Exception as e:
            logger.warning(f"Quizzer 出题失败: {e}")

        assessment: dict[str, Any] = {}
        try:
            assessment = self._assessor.execute(
                quiz_results=quiz_results,
                error_records=errors,
            )
        except Exception as e:
            logger.warning(f"Quizzer 评估失败: {e}")

        state_changes: dict[str, Any] = {
            "current_agent": self.role,
            "weak_points": assessment.get("weak_points", weak),
        }

        logger.info(
            f"QuizzerAgent 完成 | count={len(questions)} difficulty={current_difficulty:.2f}"
        )
        return AgentResult(
            agent_role=self.role,
            output={
                "questions": questions,
                "assessment": assessment,
                "difficulty": round(current_difficulty, 2),
                "strategy": self._get_strategy_description(current_difficulty),
            },
            state_changes=state_changes,
        )

    def _adjust_difficulty(
        self, user_id: str, correct_rate: float, current: float
    ) -> None:
        if correct_rate > 0.8:
            new_diff = min(1.0, current + 0.1)
        elif correct_rate < 0.5:
            new_diff = max(0.2, current - 0.15)
        else:
            new_diff = current + random.uniform(-0.05, 0.05)
        self._difficulty_cache[user_id] = round(new_diff, 2)

    @staticmethod
    def _get_strategy_description(difficulty: float) -> str:
        if difficulty > 0.8:
            return "挑战模式：高难度题目"
        elif difficulty > 0.5:
            return "进阶模式：中等难度"
        else:
            return "巩固模式：基础强化"