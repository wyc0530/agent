import json
from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState


class ReviewerAgent(BaseAgent):
    role = AgentRole.REVIEWER
    description = "复习整理Agent：分析错题→归类→提炼易错点→反馈给规划Agent"

    def __init__(self) -> None:
        super().__init__()

    def _build_system_prompt(self, state: LearningState) -> str:
        errors = state.get("error_records") or []
        weak = state.get("weak_points") or []

        error_detail = ""
        for e in errors[:10]:
            kp = e.get("knowledge_point", "未知")
            etype = e.get("error_type", "未知类型")
            ec = e.get("error_count", 1)
            error_detail += f"- [{kp}] {etype} (出现{ec}次)\n"

        return f"""你是一个学习复习专家。分析学生的错题记录，提炼薄弱知识点，生成复习建议。

## 错题记录
{error_detail or "暂无错题记录"}

## 已知薄弱点
{', '.join(str(w.get('knowledge_point', w)) for w in weak[:5]) if weak else '暂无'}

## 输出要求
1. **错误分类**：将错题归类（概念不清/计算错误/粗心等）
2. **薄弱知识点总结**：提炼出学生最需要强化的3-5个知识点
3. **复习建议**：针对每个薄弱点给出具体复习方法
4. **反馈信号**：标记需要调整学习计划的部分（将传递给规划Agent）

JSON格式输出：
```json
{{
    "error_categories": [{{"type": "概念不清", "count": 3, "knowledge_points": ["递归", "二叉树"]}}],
    "weak_points_summary": ["递归", "时间复杂度分析"],
    "review_suggestions": [{{"knowledge_point": "递归", "method": "从简单例子开始，逐步增加复杂度"}}],
    "feedback_for_planner": "建议增加递归和动态规划的学习时间"
}}
```"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "请分析我的错题记录，整理薄弱知识点"
        response = self._chat(system_prompt, user_msg, temperature=0.5, max_tokens=2048)

        state_changes: dict[str, Any] = {"current_agent": self.role}

        try:
            json_text = self._extract_json(response)
            data = json.loads(json_text.strip())

            new_weak_points = data.get("weak_points_summary", [])
            existing_weak = state.get("weak_points") or []

            merged_weak = []
            seen = set()
            for w in new_weak_points:
                name = w if isinstance(w, str) else w.get("knowledge_point", str(w))
                if name not in seen:
                    seen.add(name)
                    merged_weak.append({"knowledge_point": name, "need_review": True, "error_rate": 0.6})
            for w in existing_weak:
                name = w.get("knowledge_point", str(w))
                if name not in seen:
                    seen.add(name)
                    merged_weak.append(w)

            state_changes["weak_points"] = merged_weak

            output = {
                "analysis": response,
                "error_categories": data.get("error_categories", []),
                "weak_points_summary": new_weak_points,
                "review_suggestions": data.get("review_suggestions", []),
                "feedback_for_planner": data.get("feedback_for_planner", ""),
            }
        except Exception as e:
            logger.warning(f"ReviewerAgent JSON 解析失败: {e}")
            output = {"analysis": response}

        logger.info(f"ReviewerAgent 完成 | weak_points={len(state_changes.get('weak_points', []))}")
        return AgentResult(
            agent_role=self.role,
            output=output,
            state_changes=state_changes,
        )