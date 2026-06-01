import json
from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningPlan, LearningState
from src.core.tools.timer import FocusTimer
from src.core.graph import get_graph_store


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
根据用户消息中的指令生成对应的学习方案。以JSON格式输出以下结构：
```json
{{
    "plan_id": "auto-generated",
    "title": "学习计划标题",
    "goals": [
        {{"title": "掌握基础", "description": "掌握核心概念", "target_date": "2026-07-01", "priority": "high", "status": "pending"}}
    ],
    "phases": [
        {{"title": "基础入门", "description": "了解核心概念和基本语法", "topics": ["变量", "循环"], "duration_days": 14, "order": 1}}
    ]
}}
```
确保阶段之间有清晰的递进关系（order从小到大），从基础到进阶。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "请根据我的当前情况生成一个详细的学习计划"
        response = self._chat(system_prompt, user_msg, temperature=0.6, max_tokens=2048)

        state_changes: dict[str, Any] = {"current_agent": self.role}
        try:
            json_text = self._extract_json(response)
            data = json.loads(json_text.strip())
            plan = LearningPlan(**data)
            state_changes["learning_plan"] = plan.model_dump()
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"学习计划JSON解析失败，使用原始响应: {e}")
            state_changes["learning_plan"] = {"title": "自动生成学习计划", "raw_response": response, "phases": [], "goals": []}

        output = {
            "plan_text": json_text,
            "summary": state_changes["learning_plan"].get("title", message),
            "phases_count": len(state_changes["learning_plan"].get("phases", [])),
        }

        logger.info(f"PlannerAgent 完成 | phases={output['phases_count']}")
        return AgentResult(
            agent_role=self.role,
            output=output,
            state_changes=state_changes,
        )