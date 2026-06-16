import json as _json
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.communication import get_communication
from src.llm import LLMProvider


class AgentResult(BaseModel):
    agent_role: AgentRole
    success: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    state_changes: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0

    @classmethod
    def empty(cls, agent_role: Optional[AgentRole] = None) -> "AgentResult":
        return cls(
            agent_role=agent_role or AgentRole.ASSISTANT,
            output={"reply": "No content to process"},
        )


class BaseAgent(ABC):
    role: AgentRole
    description: str = ""

    def __init__(self) -> None:
        self._llm = LLMProvider()
        self._comm = get_communication()
        self._comm.register_agent(self.role, self.run)
        logger.info(f"Agent 注册完成 | role={self.role.value}")

    @abstractmethod
    def _build_system_prompt(self, state: LearningState) -> str:
        ...

    @abstractmethod
    def run(self, state: LearningState, message: str = "") -> AgentResult:
        ...

    def _chat(self, system_prompt: str, user_message: str, **kwargs: Any) -> str:
        boundary = (
            "\n\n## 重要\n请仅回答用户的最新问题，基于上下文给出针对性回答。"
            "不要重复此前已经解答过的内容。"
        )
        full_prompt = system_prompt + boundary
        history = kwargs.pop("history", None)

        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        try:
            if history:
                return self._llm.chat_with_history(
                    user_message=user_message,
                    history=history,
                    system_prompt=full_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return self._llm.chat(
                system_prompt=full_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.warning(
                f"Agent LLM 调用失败，尝试回退 | role={self.role.value} err={e}"
            )
            try:
                if history:
                    return self._llm.chat_with_history(
                        user_message=user_message,
                        history=history,
                        system_prompt=full_prompt,
                        temperature=0.7,
                        max_tokens=1024,
                    )
                return self._llm.chat(
                    system_prompt=full_prompt,
                    user_message=user_message,
                    temperature=0.7,
                    max_tokens=1024,
                )
            except Exception as e2:
                logger.error(
                    f"Agent LLM 回退调用也失败 | role={self.role.value} err={e2}"
                )
                raise RuntimeError(
                    f"Agent [{self.role.value}] LLM 调用失败，请稍后重试"
                ) from e2

    def _build_stream_context(
        self, state: LearningState, message: str, **kwargs: Any
    ) -> tuple[str, str, list[dict[str, str]], float, int]:
        """构建流式对话所需的上下文，不调用 LLM。

        用于 SSE 流式端点获取 Agent 的 system prompt 和历史记录，
        然后由 API 层使用 LLM 的 astream 进行真正的逐 token 流式输出。

        Args:
            state: 当前学习状态。
            message: 用户消息。
            **kwargs: 额外参数（temperature, max_tokens 等）。

        Returns:
            (system_prompt, user_message, history, temperature, max_tokens)
        """
        system_prompt = self._build_system_prompt(state)
        boundary = (
            "\n\n## 重要\n请仅回答用户的最新问题，基于上下文给出针对性回答。"
            "不要重复此前已经解答过的内容。"
        )
        full_prompt = system_prompt + boundary
        history = self._extract_history(state)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)
        return full_prompt, message, history, temperature, max_tokens

    @staticmethod
    def _extract_history(state: LearningState, max_turns: int = 6) -> list[dict[str, str]]:
        messages = state.get("messages") or []
        if not messages:
            return []
        return messages[-(max_turns * 2):]

    @staticmethod
    def _retrieve_context(query: str, user_id: str = "", top_k: int = 3) -> str:
        try:
            from src.core.memory import VectorStore
            store = VectorStore()
            filter_meta = {}
            if user_id:
                filter_meta["user_id"] = user_id
            results = store.search(
                query=query,
                top_k=top_k,
                filter_metadata=filter_meta if filter_meta else None,
            )
            if not results:
                return ""
            parts = []
            for i, doc in enumerate(results, 1):
                content = doc.get("content", "") or doc.get("_text", "")
                score = doc.get("score", 0.0)
                if score < 0.3:
                    continue
                content_short = content[:200]
                parts.append(f"[RAG-{i}] (相关度: {score:.2f})\n{content_short}")
            return "\n\n".join(parts) if parts else ""
        except Exception as e:
            logger.debug(f"RAG 上下文检索跳过: {e}")
            return ""

    def _safe_run(self, state: LearningState, message: str, runner) -> AgentResult:
        start = time.perf_counter()
        try:
            result = runner(state, message)
            duration = (time.perf_counter() - start) * 1000
            if isinstance(result, AgentResult):
                result.duration_ms = round(duration, 1)
                return result
            logger.warning(f"Agent 返回了非标准结果类型: {type(result).__name__} | role={self.role.value}")
            return AgentResult(
                agent_role=self.role,
                output=result if isinstance(result, dict) else {"content": str(result)},
                duration_ms=round(duration, 1),
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error(f"Agent 执行异常 | role={self.role.value} error={e}\n{traceback.format_exc()}")
            return AgentResult(
                agent_role=self.role,
                success=False,
                error=str(e),
                duration_ms=round(duration, 1),
            )

    def check_health(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "description": self.description,
            "llm_available": self._llm.check_health().get("api_available", False),
        }

    @staticmethod
    def _extract_json(response: str) -> str:
        if not response:
            return response
        if "```json" in response:
            parts = response.split("```json")
            if len(parts) >= 2:
                return parts[1].split("```")[0]
        elif "```" in response:
            parts = response.split("```")
            if len(parts) >= 2:
                return parts[1]
        return response