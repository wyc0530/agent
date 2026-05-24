import hashlib
import hmac
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from src.config import Settings, logger


class UserStore:
    _instance: Optional["UserStore"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "UserStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._db_path = str(Settings.resolve_path("./data/users.db"))
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()
        logger.info(f"用户数据库初始化完成 | path={self._db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    display_name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    level TEXT DEFAULT 'beginner',
                    target_field TEXT DEFAULT '',
                    available_time INTEGER DEFAULT 10,
                    preference TEXT DEFAULT 'comprehensive',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    knowledge_point TEXT NOT NULL,
                    mastery_level REAL DEFAULT 0.0,
                    total_attempts INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    last_practiced_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, knowledge_point)
                )
            """)
            conn.commit()

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()

    @staticmethod
    def _generate_token() -> str:
        return hashlib.sha256(os.urandom(32)).hexdigest()

    def register_user(
        self, username: str, password: str, display_name: str = "", email: str = ""
    ) -> dict[str, Any]:
        with self._lock:
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if existing:
                    raise ValueError(f"用户名 '{username}' 已存在")

                user_id = str(uuid.uuid4())[:16]
                salt = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
                password_hash = self._hash_password(password, salt)
                now = datetime.now().isoformat()

                conn.execute(
                    """INSERT INTO users
                       (id, username, password_hash, salt, display_name, email, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, username, password_hash, salt, display_name, email, now, now),
                )
                conn.commit()

            token_info = self._create_session(user_id)
        logger.info(f"用户注册成功 | username={username} id={user_id}")
        return {
            "user_id": user_id,
            "username": username,
            "display_name": display_name or username,
            "token": token_info["token"],
            "expires_at": token_info["expires_at"],
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        with self._get_conn() as conn:
            user = conn.execute(
                "SELECT id, username, password_hash, salt, display_name, email, level, "
                "target_field, available_time, preference FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if not user:
                raise ValueError("用户名或密码错误")

            expected_hash = self._hash_password(password, user["salt"])
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                raise ValueError("用户名或密码错误")

            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user["id"]),
            )
            conn.commit()

            token_info = self._create_session(user["id"])
            logger.info(f"用户登录成功 | username={username}")
            return {
                "user_id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"] or user["username"],
                "email": user["email"],
                "level": user["level"],
                "target_field": user["target_field"],
                "available_time": user["available_time"],
                "preference": user["preference"],
                "token": token_info["token"],
                "expires_at": token_info["expires_at"],
            }

    def _create_session(self, user_id: str) -> dict[str, str]:
        token = self._generate_token()
        now = datetime.now().isoformat()
        expires = datetime.now().timestamp() + 86400 * 7
        expires_at = datetime.fromtimestamp(expires).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, now, expires_at),
            )
            conn.commit()
        return {"token": token, "expires_at": expires_at}

    def validate_token(self, token: str) -> Optional[str]:
        with self._get_conn() as conn:
            session = conn.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
            ).fetchone()
            if not session:
                return None
            expires = datetime.fromisoformat(session["expires_at"])
            if datetime.now() > expires:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
            return session["user_id"]

    def logout(self, token: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        with self._get_conn() as conn:
            user = conn.execute(
                "SELECT id, username, display_name, email, level, target_field, "
                "available_time, preference, created_at, last_login_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not user:
                return None
            return {
                "user_id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"] or "",
                "email": user["email"] or "",
                "level": user["level"] or "beginner",
                "target_field": user["target_field"] or "",
                "available_time": user["available_time"] or 10,
                "preference": user["preference"] or "comprehensive",
                "created_at": user["created_at"] or "",
                "last_login_at": user["last_login_at"] or "",
            }

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        allowed = {"display_name", "email", "level", "target_field", "available_time", "preference"}
        VALID_LEVELS = {"beginner", "intermediate", "advanced", "expert"}
        filtered: dict[str, Any] = {}
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k == "level" and v not in VALID_LEVELS:
                continue
            if k == "available_time":
                try:
                    v = int(v)
                    if v < 0:
                        v = 0
                except (ValueError, TypeError):
                    continue
            if k == "email" and isinstance(v, str) and len(v) > 254:
                v = v[:254]
            filtered[k] = v
        if not filtered:
            return self.get_profile(user_id) or {}

        now = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [now, user_id]

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE users SET {set_clause}, updated_at = ? WHERE id = ?", values
            )
            conn.commit()
        return self.get_profile(user_id) or {}

    def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        if len(new_password) < 6:
            raise ValueError("新密码长度不能少于6位")
        if old_password == new_password:
            raise ValueError("新密码不能与旧密码相同")

        with self._get_conn() as conn:
            user = conn.execute(
                "SELECT password_hash, salt FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise ValueError("用户不存在")

            expected_hash = self._hash_password(old_password, user["salt"])
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                raise ValueError("原密码错误")

            new_salt = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
            new_hash = self._hash_password(new_password, new_salt)
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                (new_hash, new_salt, now, user_id),
            )
            conn.commit()
        logger.info(f"密码修改成功 | user_id={user_id}")

    def update_progress(
        self, user_id: str, knowledge_point: str, is_correct: bool
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT total_attempts, correct_count FROM learning_progress "
                "WHERE user_id = ? AND knowledge_point = ?",
                (user_id, knowledge_point),
            ).fetchone()

            if existing:
                total = existing["total_attempts"] + 1
                correct = existing["correct_count"] + (1 if is_correct else 0)
                mastery = correct / total if total > 0 else 0.0
                conn.execute(
                    "UPDATE learning_progress SET total_attempts = ?, correct_count = ?, "
                    "mastery_level = ?, last_practiced_at = ? WHERE user_id = ? AND knowledge_point = ?",
                    (total, correct, round(mastery, 3), now, user_id, knowledge_point),
                )
            else:
                total = 1
                correct = 1 if is_correct else 0
                mastery = correct / total
                conn.execute(
                    "INSERT INTO learning_progress "
                    "(user_id, knowledge_point, mastery_level, total_attempts, correct_count, last_practiced_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, knowledge_point, round(mastery, 3), total, correct, now),
                )
            conn.commit()
        return {
            "knowledge_point": knowledge_point,
            "total_attempts": total if existing else 1,
            "correct_count": correct if existing else (1 if is_correct else 0),
            "mastery_level": round(mastery if existing else (1.0 if is_correct else 0.0), 3),
        }

    def get_progress(self, user_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT knowledge_point, mastery_level, total_attempts, correct_count, "
                "last_practiced_at FROM learning_progress WHERE user_id = ? "
                "ORDER BY mastery_level ASC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_weak_points(self, user_id: str, threshold: float = 0.6) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT knowledge_point, mastery_level, total_attempts, correct_count "
                "FROM learning_progress WHERE user_id = ? AND mastery_level < ? "
                "ORDER BY mastery_level ASC",
                (user_id, threshold),
            ).fetchall()
        return [dict(r) for r in rows]

    def check_health(self) -> dict[str, Any]:
        try:
            with self._get_conn() as conn:
                user_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
                return {
                    "status": "ok",
                    "user_count": user_count["c"] if user_count else 0,
                    "db_path": self._db_path,
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store