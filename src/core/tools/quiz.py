import random
import uuid
from typing import Any

from src.config import logger
from src.core.tools.base import BaseTool, ToolCategory, ToolMetadata, ToolPermission


class QuizGenerator(BaseTool):
    metadata = ToolMetadata(
        name="quiz_generator",
        description="根据知识点和难度生成个性化题目。支持选择题、判断题和填空题。可指定题型、难度和知识点。",
        category=ToolCategory.QUIZ,
        permission=ToolPermission.READ_ONLY,
        version="1.0.0",
        tags=["quiz", "question", "assessment"],
        input_schema={
            "topic": {"type": "string", "description": "知识点主题"},
            "question_type": {"type": "string", "description": "题型: single_choice/multi_choice/true_false/fill_blank", "default": "single_choice"},
            "difficulty": {"type": "number", "description": "难度 0-1", "default": 0.5},
            "count": {"type": "integer", "description": "生成题目数量", "default": 3},
            "weak_points": {"type": "array", "description": "薄弱知识点列表(用于针对性出题)"},
        },
    )

    def execute(self, **kwargs) -> list[dict[str, Any]]:
        topic = kwargs.get("topic", "通用")
        question_type = kwargs.get("question_type", "single_choice")
        difficulty = float(kwargs.get("difficulty", 0.5))
        count = int(kwargs.get("count", 3))
        weak_points = kwargs.get("weak_points", [])

        count = max(1, min(count, 20))
        difficulty = max(0.1, min(1.0, difficulty))

        questions = []
        for i in range(count):
            focused_topic = topic
            if weak_points and i < len(weak_points):
                focused_topic = weak_points[i]

            question = self._generate_question(
                topic=focused_topic,
                question_type=question_type,
                difficulty=difficulty,
                index=i,
            )
            questions.append(question)

        logger.info(
            f"出题完成 | topic={topic} type={question_type} count={count} difficulty={difficulty}"
        )
        return questions

    def _generate_question(
        self, topic: str, question_type: str, difficulty: float, index: int
    ) -> dict[str, Any]:
        question_id = str(uuid.uuid4())[:8]

        question_templates: dict[str, Any] = {
            "single_choice": {
                "content": f"[{topic}] 以下关于 {topic} 的说法中，正确的是？",
                "options": [
                    f"{topic}的核心概念包括理论和实践",
                    f"{topic}不需要任何基础即可精通",
                    f"{topic}与编程完全无关",
                    f"{topic}只适用于特定场景",
                ],
            },
            "true_false": {
                "content": f"[{topic}] 判断题：{topic}是计算机领域的重要知识体系。",
                "options": ["正确", "错误"],
            },
            "fill_blank": {
                "content": f"[{topic}] {topic}的学习需要循序渐进，从___开始逐步深入。",
                "options": ["基础概念", "高级应用", "底层原理"],
            },
        }

        template = question_templates.get(question_type, question_templates["single_choice"])

        return {
            "question_id": question_id,
            "content": template["content"],
            "question_type": question_type,
            "options": template["options"],
            "difficulty": round(difficulty * (1 + (random.random() - 0.5) * 0.3), 2),
            "knowledge_point": topic,
            "tags": [topic, question_type],
        }


class AbilityAssessor(BaseTool):
    metadata = ToolMetadata(
        name="ability_assessor",
        description="评估学生的能力水平，基于答题历史分析薄弱知识点和掌握程度。",
        category=ToolCategory.QUIZ,
        permission=ToolPermission.READ_ONLY,
        version="1.0.0",
        tags=["assessment", "ability", "diagnostic"],
    )

    def execute(self, **kwargs) -> dict[str, Any]:
        quiz_results = kwargs.get("quiz_results", [])
        error_records = kwargs.get("error_records", [])
        current_level = kwargs.get("current_level", {})

        total_attempts = len(quiz_results)
        correct_count = sum(1 for r in quiz_results if r.get("is_correct", False))

        correct_rate = correct_count / max(total_attempts, 1)

        weak_points = self._analyze_weak_points(error_records)

        level_assessment = self._assess_level(correct_rate, total_attempts)

        return {
            "overall_score": round(correct_rate * 100, 1),
            "total_attempts": total_attempts,
            "correct_count": correct_count,
            "weak_points": weak_points,
            "level": level_assessment,
            "suggested_focus": [w["knowledge_point"] for w in weak_points[:3]],
        }

    @staticmethod
    def _analyze_weak_points(error_records: list) -> list[dict[str, Any]]:
        point_stats: dict[str, dict[str, Any]] = {}
        for record in error_records:
            kp = record.get("knowledge_point", "未知")
            if kp not in point_stats:
                point_stats[kp] = {"error_count": 0, "total": 0, "correct_count": 0}
            point_stats[kp]["error_count"] += record.get("error_count", 0)
            point_stats[kp]["total"] += 1

        weak_points = []
        for kp, stats in point_stats.items():
            rate = stats["error_count"] / max(stats["total"], 1)
            weak_points.append({
                "knowledge_point": kp,
                "error_rate": round(min(rate, 1.0), 2),
                "error_count": stats["error_count"],
                "total_attempts": stats["total"],
                "need_review": rate > 0.3,
            })

        weak_points.sort(key=lambda x: x["error_rate"], reverse=True)
        return weak_points

    @staticmethod
    def _assess_level(correct_rate: float, total: int) -> str:
        if total < 3:
            return "初评阶段"
        if correct_rate >= 0.9:
            return "优秀"
        elif correct_rate >= 0.7:
            return "良好"
        elif correct_rate >= 0.5:
            return "中等"
        else:
            return "待加强"