from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.retriever import Retriever
from src.core.tools.timer import FocusTimer


class PartnerAgent(BaseAgent):
    role = AgentRole.PARTNER
    description = "学习伙伴Agent：理解问题→检索知识→回答问题→记录专注时间"

    def __init__(self) -> None:
        super().__init__()
        self._retriever = Retriever()
        self._timer = FocusTimer()

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        focus = state.get("focus_sessions") or []
        total_minutes = state.get("focus_time_minutes") or 0

        return f"""你是一个贴心的学习伙伴。用亲切、耐心的方式回答学生问题，帮助他们理解知识点。

## 学生信息
- 昵称: {profile.get('name', '同学')}
- 当前水平: {profile.get('level', '未评估')}
- 累计专注学习: {total_minutes} 分钟 ({len(focus)} 次会话)

## 你的角色
- 用通俗易懂的语言解释复杂概念
- 结合比喻和实例帮助学生理解
- 鼓励学生，保持积极的学习氛围
- 如果问题超出你的知识范围，诚实说明并建议查阅其他资料

## 输出要求
直接回复学生的问题，格式自然。"""

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        system_prompt = self._build_system_prompt(state)
        user_msg = message or "你好，我有一个问题想请教"

        state_changes: dict[str, Any] = {"current_agent": self.role}

        rag_context: list[dict[str, Any]] = []
        rag_text = ""
        try:
            rag_context = self._retriever.retrieve(query=message or "学习", top_k=3)
            if rag_context:
                parts = []
                for i, doc in enumerate(rag_context, 1):
                    content = doc.get("content", "")
                    score = doc.get("score", 0.0)
                    parts.append(f"[参考资料{i}] (相关性: {score:.2f})\n{content}")
                rag_text = "\n\n".join(parts)
        except Exception as e:
            logger.warning(f"PartnerAgent RAG 检索失败: {e}")

        if rag_text:
            system_prompt = (
                f"{system_prompt}\n\n"
                f"## 参考知识库内容（请优先基于以下内容回答）\n{rag_text}\n\n"
                f"请基于以上参考内容回答学生的问题。如果参考内容不足以回答，可以结合你的知识补充。"
            )

        timer_status: dict[str, Any] = {"status": "idle"}
        try:
            user_id = state.get("user_id") or ""
            self._timer.start_session(topic=message or "学习中", user_id=user_id)
            timer_status = self._timer.get_status()
        except (AttributeError, ValueError, RuntimeError, OSError) as e:
            logger.debug(f"计时器启动失败: {e}")

        response = self._chat(system_prompt, user_msg, temperature=0.8, max_tokens=1536)

        try:
            stopped = self._timer.stop_session()
            timer_status = stopped
        except (AttributeError, ValueError, RuntimeError, OSError) as e:
            logger.debug(f"计时器停止失败: {e}")

        logger.info(f"PartnerAgent 完成 | query={user_msg[:50]}")
        return AgentResult(
            agent_role=self.role,
            output={
                "answer": response,
                "rag_references": rag_context,
                "focus_timer": timer_status,
            },
            state_changes=state_changes,
        )