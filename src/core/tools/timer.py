from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from src.config import Settings, logger
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
        self._lock = threading.Lock()
        data_dir = str(Settings.resolve_path("./data"))
        os.makedirs(data_dir, exist_ok=True)
        self._persist_path = os.path.join(data_dir, "timer_sessions.json")
        self._load_sessions()

    def _load_sessions(self) -> None:
        try:
            if os.path.exists(self._persist_path):
                with open(self._persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._sessions = data.get("sessions", [])
                    self._active_session = data.get("active_session")
                else:
                    self._sessions = data
        except Exception as e:
            logger.warning(f"加载专注会话记录失败: {e}")

    def _save_sessions(self) -> None:
        try:
            data = {
                "sessions": self._sessions,
                "active_session": self._active_session,
            }
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存专注会话记录失败: {e}")

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

    def start_session(self, topic: str = "学习中", user_id: str = "") -> dict[str, Any]:
        with self._lock:
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
                "user_id": user_id,
                "started_at": datetime.now().isoformat(),
            }
            logger.info(f"专注计时开始 | session={session_id} topic={topic} user={user_id}")
            return {
                "status": "started",
                "session_id": session_id,
                "topic": topic,
                "started_at": self._active_session["started_at"],
            }

    def stop_session(self) -> dict[str, Any]:
        with self._lock:
            if self._active_session is None:
                return {"status": "idle", "message": "没有进行中的计时"}

            elapsed = time.time() - self._active_session["start_time"]
            session_id = self._active_session["session_id"]
            session = {
                **self._active_session,
                "end_time": time.time(),
                "elapsed_minutes": round(elapsed / 60, 2),
                "stopped_at": datetime.now().isoformat(),
            }
            self._sessions.append(session)
            active_cleared = session_id
            self._active_session = None
            today_count = self._count_today_sessions()

        self._save_sessions()
        logger.info(f"专注计时结束 | session={active_cleared} minutes={session['elapsed_minutes']}")
        return {
            "status": "stopped",
            "session_id": active_cleared,
            "elapsed_minutes": session["elapsed_minutes"],
            "total_sessions_today": today_count,
        }

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            active = self._active_session
            if active is None:
                return {"status": "idle", "message": "当前无进行中的计时"}

            elapsed = time.time() - active["start_time"]
            return {
                "status": "running",
                "session_id": active["session_id"],
                "topic": active["topic"],
                "elapsed_minutes": round(elapsed / 60, 2),
            }

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            sessions_snapshot = list(self._sessions)
        today_sessions = [s for s in sessions_snapshot if self._is_today(s.get("started_at", ""))]
        total_minutes = sum(s.get("elapsed_minutes", 0) for s in today_sessions)

        return {
            "today_sessions": len(today_sessions),
            "today_total_minutes": round(total_minutes, 2),
            "all_sessions": len(sessions_snapshot),
            "recent_sessions": sessions_snapshot[-5:],
        }

    @staticmethod
    def _is_today(datetime_str: str) -> bool:
        if not datetime_str:
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        return datetime_str.startswith(today)

    def _count_today_sessions(self) -> int:
        return sum(1 for s in self._sessions if self._is_today(s.get("started_at", "")))