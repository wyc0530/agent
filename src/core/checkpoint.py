import asyncio
import json
import os
import threading
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.config import Settings, logger

_JSON_ENCODE_ERROR_STR = "<non-serializable>"


def _safe_serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    try:
        return str(obj)
    except Exception:
        return _JSON_ENCODE_ERROR_STR


class FileBackedMemorySaver(MemorySaver):
    def __init__(self) -> None:
        super().__init__()
        self._persist_path = str(Settings.resolve_path(Settings.CHECKPOINT_STORE_PATH))
        os.makedirs(self._persist_path, exist_ok=True)
        self._file_path = os.path.join(self._persist_path, "checkpoints.json")
        self._dirty = False
        restored = self.load_from_disk()
        if restored > 0:
            logger.info(f"Checkpoint 从磁盘恢复 | count={restored}")

    def put(self, config: dict, checkpoint: dict, metadata: dict, new_versions: dict) -> dict:
        result = super().put(config, checkpoint, metadata, new_versions)
        self._dirty = True
        threading.Thread(target=self._safe_save, daemon=True).start()
        return result

    def _safe_save(self) -> None:
        try:
            storage = getattr(self, "storage", {})
            count = 0
            try:
                count = len(self.list({}))
            except Exception:
                count = len(storage)
            data = {
                "checkpoint_count": count,
                "storage": _safe_serialize(storage),
            }
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
            self._dirty = False
        except Exception as e:
            logger.warning(f"Checkpoint 持久化写入失败: {e}")

    def save_to_disk(self) -> None:
        self._safe_save()

    def load_from_disk(self) -> int:
        try:
            if os.path.exists(self._file_path):
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "storage" in data and hasattr(self, "storage"):
                    for k, v in data["storage"].items():
                        self.storage[k] = v
                return data.get("checkpoint_count", 0)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Checkpoint 持久化读取失败（将重置）: {e}")
            try:
                os.remove(self._file_path)
            except OSError:
                pass
            self._cleanup_legacy_file()
        except Exception as e:
            logger.warning(f"Checkpoint 持久化读取失败（将重置）: {e}")
            try:
                os.remove(self._file_path)
            except OSError:
                pass
            self._cleanup_legacy_file()
        return 0

    def _cleanup_legacy_file(self) -> None:
        legacy_path = os.path.join(self._persist_path, "checkpoints.pkl")
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
                logger.info("已移除旧版pickle格式checkpoint文件")
            except OSError:
                pass


class CheckpointManager:
    _instance: Optional["CheckpointManager"] = None
    _saver: Optional[BaseCheckpointSaver[int]] = None
    _summarizers: dict[str, Any] = {}

    def __new__(cls) -> "CheckpointManager":
        if cls._instance is None:
            try:
                cls._instance = super().__new__(cls)
            except (TypeError, RuntimeError, AttributeError) as e:
                cls._instance = None
                logger.error(f"CheckpointManager 单例创建失败: {e}")
                raise
        return cls._instance

    def __init__(self) -> None:
        if self._saver is not None:
            return
        self._saver = FileBackedMemorySaver()
        logger.info(f"Checkpoint 管理器初始化完成 | backend=file_backed_memory path={Settings.CHECKPOINT_STORE_PATH}")

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