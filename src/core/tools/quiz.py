import json as _json
import random
import uuid
from typing import Any

from src.config import logger
from src.core.tools.base import BaseTool, ToolCategory, ToolMetadata, ToolPermission
from src.llm import LLMProvider


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

    def __init__(self) -> None:
        self._llm: LLMProvider | None = None

    def _get_llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = LLMProvider()
        return self._llm

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

            try:
                question = self._generate_llm_question(
                    topic=focused_topic,
                    question_type=question_type,
                    difficulty=difficulty,
                )
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.debug(f"LLM出题失败，使用模板回退: {e}")
                question = self._generate_template_question(
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

    def _generate_llm_question(
        self, topic: str, question_type: str, difficulty: float
    ) -> dict[str, Any]:
        difficulty_label = "简单" if difficulty < 0.4 else ("中等" if difficulty < 0.7 else "困难")
        prompt = f"""你是一个专业的出题教师。请为知识点"{topic}"生成一道{difficulty_label}难度的{question_type}题目。

题型要求:
- single_choice: 单选题，4个选项，标注正确答案
- true_false: 判断题，判断对错
- fill_blank: 填空题，给出标准答案

以JSON格式输出：
```json
{{
    "content": "题目内容",
    "options": ["选项A", "选项B", "选项C", "选项D"],
    "answer": "正确答案",
    "explanation": "解题思路和知识点解析"
}}
```
确保题目有教育价值，解析详细。"""

        response = self._get_llm().chat(prompt, temperature=0.7, max_tokens=512)
        try:
            json_text = response
            if "```json" in response:
                json_text = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                parts = response.split("```")
                if len(parts) >= 2:
                    json_text = parts[1]
            data = _json.loads(json_text.strip())
        except (_json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"LLM出题JSON解析失败，使用模板回退: {e}")
            raise

        question_id = str(uuid.uuid4())[:8]
        return {
            "question_id": question_id,
            "content": data.get("content", ""),
            "question_type": question_type,
            "options": data.get("options", []),
            "answer": data.get("answer", ""),
            "explanation": data.get("explanation", ""),
            "difficulty": difficulty,
            "knowledge_point": topic,
            "tags": [topic, question_type],
        }

    def _generate_template_question(
        self, topic: str, question_type: str, difficulty: float, index: int
    ) -> dict[str, Any]:
        import hashlib
        question_id = str(uuid.uuid4())[:8]
        variant = int(hashlib.md5(f"{topic}{index}".encode()).hexdigest(), 16) % 3

        question_templates: dict[str, Any] = {
            "single_choice": [
                {
                    "content": f"[{topic}] 以下关于 {topic} 的说法中，正确的是？",
                    "options": [f"{topic}的核心概念包括理论和实践", f"{topic}不需要任何基础即可精通", f"{topic}与编程完全无关", f"{topic}只适用于特定场景"],
                    "answer": f"{topic}的核心概念包括理论和实践",
                    "explanation": f"这是关于{topic}的基础知识，核心概念通常包含理论和实践两个方面。",
                },
                {
                    "content": f"[{topic}] 在{topic}的实际应用中，最关键的是？",
                    "options": ["理解核心原理并动手实践", "只阅读理论书籍", "完全依赖工具", "忽略基础概念"],
                    "answer": "理解核心原理并动手实践",
                    "explanation": f"掌握{topic}最有效的方式是理论结合实践。",
                },
                {
                    "content": f"[{topic}] 关于{topic}的学习路径，以下哪项最合理？",
                    "options": ["基础→进阶→项目实战", "直接学习高级内容", "只做练习题", "只关注最新技术"],
                    "answer": "基础→进阶→项目实战",
                    "explanation": f"学习{topic}应从基础开始，逐步提升到高级内容并参与实践。",
                },
            ],
            "true_false": [
                {
                    "content": f"[{topic}] 判断题：{topic}是计算机领域的重要知识体系。",
                    "options": ["正确", "错误"],
                    "answer": "正确",
                    "explanation": f"{topic}确实是计算机领域中重要的知识体系。",
                },
                {
                    "content": f"[{topic}] 判断题：学习{topic}不需要实践，只靠理论即可精通。",
                    "options": ["正确", "错误"],
                    "answer": "错误",
                    "explanation": f"学习{topic}需要理论与实践相结合。",
                },
            ],
            "fill_blank": [
                {
                    "content": f"[{topic}] {topic}的学习需要循序渐进，从___开始逐步深入。",
                    "options": ["基础概念", "高级应用", "底层原理"],
                    "answer": "基础概念",
                    "explanation": f"学习{topic}应当从基础概念入手。",
                },
                {
                    "content": f"[{topic}] 掌握{topic}后，可以帮助解决___问题。",
                    "options": ["实际应用", "所有", "虚构"],
                    "answer": "实际应用",
                    "explanation": f"{topic}的知识主要用于解决实际应用中的问题。",
                },
            ],
        }

        templates = question_templates.get(question_type, question_templates["single_choice"])
        template = templates[variant % len(templates)]

        return {
            "question_id": question_id,
            "content": template["content"],
            "question_type": question_type,
            "options": template["options"],
            "answer": template.get("answer", ""),
            "explanation": template.get("explanation", ""),
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
                point_stats[kp] = {"error_count": 0, "total": 0}
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