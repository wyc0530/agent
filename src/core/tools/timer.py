import time
import uuid
from datetime import datetime
from typing import Any

from src.config import logger
from src.core.tools.base import BaseTool, ToolCategory, ToolMetadata, ToolPermission


class FocusTimer(BaseTool):
    metadata = ToolMetadata(
        name="focus_timer",
        description="记录和管理学生专注学习时间。启动计时、结束计时、查询今日累计专注时间。",
        category=ToolCategory.TIMER,
        permission=ToolPermission.READ_WRITE,
        version="1.0.0",
        tags=["timer", "focus", "study"],
    )

    def __init__(self) -> None:
        self._sessions: list[dict[str, Any]] = []
        self._active_session: dict[str, Any] | None = None

    def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "start")
        if action == "start":
            return self.start_session(kwargs.get("topic", "学习中"))
        elif action == "stop":
            return self.stop_session()
        elif action == "status":
            return self.get_status()
        elif action == "summary":
            return self.get_summary()
        else:
            return {"error": f"未知操作: {action}"}

    def start_session(self, topic: str = "学习中") -> dict[str, Any]:
        if self._active_session is not None:
            elapsed = time.time() - self._active_session["start_time"]
            return {
                "status": "already_running",
                "message": "已有进行中的计时",
                "session_id": self._active_session["session_id"],
                "elapsed_minutes": round(elapsed / 60, 2),
            }

        session_id = str(uuid.uuid4())[:8]
        self._active_session = {
            "session_id": session_id,
            "start_time": time.time(),
            "topic": topic,
            "started_at": datetime.now().isoformat(),
        }
        logger.info(f"专注计时开始 | session={session_id} topic={topic}")
        return {
            "status": "started",
            "session_id": session_id,
            "topic": topic,
            "started_at": self._active_session["started_at"],
        }

    def stop_session(self) -> dict[str, Any]:
        if self._active_session is None:
            return {"status": "idle", "message": "没有进行中的计时"}

        elapsed = time.time() - self._active_session["start_time"]
        session = {
            **self._active_session,
            "end_time": time.time(),
            "elapsed_minutes": round(elapsed / 60, 2),
            "stopped_at": datetime.now().isoformat(),
        }
        self._sessions.append(session)
        session_id = self._active_session["session_id"]
        self._active_session = None

        logger.info(f"专注计时结束 | session={session_id} minutes={session['elapsed_minutes']}")
        return {
            "status": "stopped",
            "session_id": session_id,
            "elapsed_minutes": session["elapsed_minutes"],
            "total_sessions_today": self._count_today_sessions(),
        }

    def get_status(self) -> dict[str, Any]:
        if self._active_session is None:
            return {"status": "idle", "message": "当前无进行中的计时"}

        elapsed = time.time() - self._active_session["start_time"]
        return {
            "status": "running",
            "session_id": self._active_session["session_id"],
            "topic": self._active_session["topic"],
            "elapsed_minutes": round(elapsed / 60, 2),
        }

    def get_summary(self) -> dict[str, Any]:
        today_sessions = [s for s in self._sessions if self._is_today(s.get("started_at", ""))]
        total_minutes = sum(s.get("elapsed_minutes", 0) for s in today_sessions)

        return {
            "today_sessions": len(today_sessions),
            "today_total_minutes": round(total_minutes, 2),
            "all_sessions": len(self._sessions),
            "recent_sessions": self._sessions[-5:],
        }

    @staticmethod
    def _is_today(datetime_str: str) -> bool:
        if not datetime_str:
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        return datetime_str.startswith(today)

    def _count_today_sessions(self) -> int:
        return sum(1 for s in self._sessions if self._is_today(s.get("started_at", "")))