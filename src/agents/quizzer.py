import random
import threading
import time
from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.tools.quiz import AbilityAssessor, QuizGenerator


_REFLECTION_PROMPT = """你是出题质量反思评估专家。请评估以下出题结果的质量：

## 学生信息
- 近期正确率: {correct_rate:.0%}
- 薄弱知识点: {weak_points}
- 当前难度: {difficulty}

## 出题结果
- 题目数量: {question_count}
- 题目类型: {question_types}
- 知识点覆盖: {knowledge_points}

## 反思要求
请从以下维度反思并给出改进建议（JSON格式）：
1. 难度是否与学生水平匹配
2. 题目是否覆盖了薄弱知识点
3. 题目类型是否多样化
4. 是否需要调整出题策略

输出格式：
```json
{{
    "difficulty_match": "too_easy|appropriate|too_hard",
    "coverage_score": 0.0-1.0,
    "diversity_score": 0.0-1.0,
    "reflection_notes": "反思总结",
    "suggested_adjustment": "suggested_difficulty",
    "next_strategy": "策略建议"
}}
```"""


class QuizzerAgent(BaseAgent):
    role = AgentRole.QUIZZER
    description = "个性出题Agent：分析薄弱点→出题→评估→Reflection反思→RL动态调整难度"

    def __init__(self) -> None:
        super().__init__()
        self._quiz_gen = QuizGenerator()
        self._assessor = AbilityAssessor()
        self._difficulty_cache: dict[str, float] = {}
        self._difficulty_lock = threading.Lock()
        self._reflection_history: dict[str, list[dict[str, Any]]] = {}
        self._reflection_lock = threading.Lock()

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

        user_id = state.get("user_id") or "default"
        reflection_insights = ""
        with self._reflection_lock:
            history = self._reflection_history.get(user_id, [])
            if history:
                last = history[-1]
                reflection_insights = (
                    f"\n## 上次反思结果\n"
                    f"- 难度匹配: {last.get('difficulty_match', 'unknown')}\n"
                    f"- 覆盖评分: {last.get('coverage_score', 0)}\n"
                    f"- 多样性评分: {last.get('diversity_score', 0)}\n"
                    f"- 建议: {last.get('suggested_adjustment', '')}\n"
                )

        return f"""你是一个专业的出题教师。根据学生的学习情况，生成最合适题目。

## 学生评估
- 近期正确率: {recent_score:.0%}
- 薄弱知识点:
{error_summary or "暂无"}
{reflection_insights}
## 出题策略 (强化学习驱动)
- 学生正确率 > 80%：适当提高难度
- 学生正确率 50-80%：维持当前难度
- 学生正确率 < 50%：降低难度，加强基础
- 优先出薄弱知识点的题目
- 根据反思结果动态调整题目类型和难度分布

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
        correct_rate = 0.5
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

        reflection: dict[str, Any] = {}
        try:
            reflection = self._reflect(
                user_id=user_id,
                correct_rate=correct_rate,
                weak_points=weak_points_list,
                difficulty=current_difficulty,
                questions=questions,
            )
        except Exception as e:
            logger.warning(f"Quizzer 反思失败: {e}")

        with self._reflection_lock:
            if user_id not in self._reflection_history:
                self._reflection_history[user_id] = []
            self._reflection_history[user_id].append({
                "timestamp": time.time(),
                **reflection,
            })
            if len(self._reflection_history[user_id]) > 20:
                self._reflection_history[user_id] = self._reflection_history[user_id][-20:]

        state_changes: dict[str, Any] = {
            "current_agent": self.role,
            "weak_points": assessment.get("weak_points", weak),
        }

        logger.info(
            f"QuizzerAgent 完成 | count={len(questions)} difficulty={current_difficulty:.2f} "
            f"reflection={reflection.get('difficulty_match', 'none')}"
        )
        return AgentResult(
            agent_role=self.role,
            output={
                "questions": questions,
                "assessment": assessment,
                "difficulty": round(current_difficulty, 2),
                "strategy": self._get_strategy_description(current_difficulty),
                "reflection": reflection,
            },
            state_changes=state_changes,
        )

    def _reflect(
        self,
        user_id: str,
        correct_rate: float,
        weak_points: list[str],
        difficulty: float,
        questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reflection机制：反思出题质量并给出改进建议"""
        if not questions:
            return {
                "difficulty_match": "unknown",
                "coverage_score": 0.0,
                "diversity_score": 0.0,
                "reflection_notes": "无题目生成，无法反思",
                "suggested_adjustment": "保持当前难度",
                "next_strategy": "重新生成题目",
            }

        question_types = list(set(q.get("question_type", "unknown") for q in questions))
        knowledge_points = list(set(q.get("knowledge_point", "") for q in questions))

        coverage_score = 0.0
        if weak_points:
            covered = sum(1 for kp in knowledge_points if any(wp in kp for wp in weak_points))
            coverage_score = covered / max(len(weak_points), 1)

        diversity_score = len(question_types) / max(len(questions), 1)

        difficulty_match = "appropriate"
        if correct_rate > 0.85 and difficulty < 0.6:
            difficulty_match = "too_easy"
        elif correct_rate < 0.4 and difficulty > 0.6:
            difficulty_match = "too_hard"

        try:
            reflection_prompt = _REFLECTION_PROMPT.format(
                correct_rate=correct_rate,
                weak_points=", ".join(weak_points[:5]) if weak_points else "暂无",
                difficulty=difficulty,
                question_count=len(questions),
                question_types=", ".join(question_types),
                knowledge_points=", ".join(knowledge_points[:5]),
            )
            llm_reflection = self._chat(
                "你是一个出题质量评估专家。",
                reflection_prompt,
                temperature=0.3,
                max_tokens=512,
            )
            import json
            json_text = self._extract_json(llm_reflection)
            parsed = json.loads(json_text.strip())
            return {
                **parsed,
                "auto_coverage_score": round(coverage_score, 2),
                "auto_diversity_score": round(diversity_score, 2),
            }
        except Exception as e:
            logger.debug(f"LLM Reflection 失败，使用自动评估: {e}")

        return {
            "difficulty_match": difficulty_match,
            "coverage_score": round(coverage_score, 2),
            "diversity_score": round(diversity_score, 2),
            "reflection_notes": (
                f"自动评估：难度匹配={difficulty_match}，"
                f"覆盖度={coverage_score:.2f}，"
                f"多样性={diversity_score:.2f}"
            ),
            "suggested_adjustment": (
                "increase" if difficulty_match == "too_easy"
                else "decrease" if difficulty_match == "too_hard"
                else "maintain"
            ),
            "next_strategy": self._get_strategy_description(difficulty),
        }

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