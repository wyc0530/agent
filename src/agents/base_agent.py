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
        return self._llm.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
        )

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