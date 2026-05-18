import asyncio
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.config import Settings, logger


class CheckpointManager:
    _instance: Optional["CheckpointManager"] = None
    _saver: Optional[BaseCheckpointSaver[int]] = None
    _summarizers: dict[str, Any] = {}

    def __new__(cls) -> "CheckpointManager":
        if cls._instance is None:
            try:
                cls._instance = super().__new__(cls)
            except Exception:
                cls._instance = None
                raise
        return cls._instance

    def __init__(self) -> None:
        if self._saver is not None:
            return
        self._saver = MemorySaver()
        logger.info("Checkpoint 管理器初始化完成 | backend=memory")

    @property
    def saver(self) -> Optional[BaseCheckpointSaver[int]]:
        return self._saver

    def get_saver(self) -> Optional[BaseCheckpointSaver[int]]:
        return self._saver

    def check_health(self) -> dict[str, Any]:
        if self._saver is None:
            return {"status": "uninitialized"}
        return {
            "status": "ok",
            "backend": "memory",
            "store_path": Settings.resolve_path(Settings.CHECKPOINT_STORE_PATH),
        }


class ConversationSummarizer:
    def __init__(self, max_messages: int = 50) -> None:
        self._max_messages = max_messages
        self._enabled = Settings.MEMORY_SUMMARY_ENABLED

    def should_summarize(self, message_count: int) -> bool:
        return self._enabled and message_count > self._max_messages

    def create_summary_prompt(self, messages: list) -> str:
        conversation_text = self._format_messages(messages)
        return (
            "请将以下对话历史压缩为一个简洁的摘要，包含关键信息："
            "用户的学习目标、当前进度、提出的问题和学习偏好。"
            "摘要应尽可能保留对后续学习指导有用的信息。\n\n"
            f"## 对话历史\n{conversation_text}"
        )

    @staticmethod
    def _format_messages(messages: list, max_chars: int = 4000) -> str:
        parts = []
        total = 0
        for msg in messages:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", str(msg))
            line = f"[{role}]: {content}"
            if total + len(line) > max_chars:
                parts.append("[...早期对话已截断...]")
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)

    def estimate_compression_ratio(self, original_count: int) -> float:
        if original_count <= self._max_messages:
            return 1.0
        return self._max_messages / max(original_count, 1)

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "enabled": self._enabled,
            "max_messages": self._max_messages,
        }


_checkpoint_manager: Optional[CheckpointManager] = None
_summarizer: Optional[ConversationSummarizer] = None


def get_checkpoint_manager() -> CheckpointManager:
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


def get_summarizer() -> ConversationSummarizer:
    global _summarizer
    if _summarizer is None:
        _summarizer = ConversationSummarizer(max_messages=Settings.MEMORY_MAX_MESSAGES)
    return _summarizer