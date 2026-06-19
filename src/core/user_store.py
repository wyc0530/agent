import hashlib
import hmac
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Optional

import mysql.connector
from mysql.connector import pooling

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

        db_config = {
            "host": Settings.MYSQL_HOST,
            "port": Settings.MYSQL_PORT,
            "user": Settings.MYSQL_USER,
            "password": Settings.MYSQL_PASSWORD,
            "database": Settings.MYSQL_DATABASE,
            "charset": "utf8mb4",
            "autocommit": False,
        }

        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="user_store_pool",
                pool_size=Settings.MYSQL_POOL_SIZE,
                **db_config,
            )
            self._init_db()
            logger.info(
                f"MySQL 数据库初始化完成 | "
                f"host={Settings.MYSQL_HOST}:{Settings.MYSQL_PORT} "
                f"database={Settings.MYSQL_DATABASE}"
            )
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            raise

    def _get_conn(self) -> mysql.connector.MySQLConnection:
        return self._pool.get_connection()

    @staticmethod
    def _get_cursor(conn: mysql.connector.MySQLConnection):
        return conn.cursor(dictionary=True)

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            # 确保已有表有主键（兼容旧表）
            try:
                cursor.execute("ALTER TABLE users ADD PRIMARY KEY (id)")
            except Exception:
                pass  # 主键已存在
            try:
                cursor.execute("ALTER TABLE sessions ADD PRIMARY KEY (token)")
            except Exception:
                pass  # 主键已存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    salt VARCHAR(255) NOT NULL,
                    display_name VARCHAR(255) DEFAULT '',
                    email VARCHAR(255) DEFAULT '',
                    level VARCHAR(255) DEFAULT 'beginner',
                    target_field VARCHAR(255) DEFAULT '',
                    available_time VARCHAR(255) DEFAULT '10',
                    preference VARCHAR(255) DEFAULT 'comprehensive',
                    created_at VARCHAR(255) NOT NULL,
                    updated_at VARCHAR(255) NOT NULL,
                    last_login_at VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    created_at VARCHAR(255) NOT NULL,
                    expires_at VARCHAR(255) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    knowledge_point VARCHAR(255) NOT NULL,
                    mastery_level DOUBLE DEFAULT 0.0,
                    total_attempts INT DEFAULT 0,
                    correct_count INT DEFAULT 0,
                    last_practiced_at VARCHAR(255),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_user_kp (user_id, knowledge_point)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    title VARCHAR(255) DEFAULT '新对话',
                    created_at VARCHAR(255) NOT NULL,
                    updated_at VARCHAR(255) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_updated (user_id, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at VARCHAR(255) NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    INDEX idx_conv_id (conversation_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # 修复已存在的表的字符集（兼容旧表）
            try:
                cursor.execute("SET FOREIGN_KEY_CHECKS=0")
                cursor.execute("ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4")
                cursor.execute("ALTER TABLE conversations CONVERT TO CHARACTER SET utf8mb4")
                cursor.execute("ALTER TABLE conversation_messages CONVERT TO CHARACTER SET utf8mb4")
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            except Exception:
                pass
            conn.commit()
        finally:
            cursor.close()
            conn.close()

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
            conn = self._get_conn()
            try:
                cursor = self._get_cursor(conn)
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s", (username,)
                )
                if cursor.fetchone():
                    raise ValueError(f"用户名 '{username}' 已存在")

                user_id = str(uuid.uuid4())[:16]
                salt = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
                password_hash = self._hash_password(password, salt)
                now = datetime.now().isoformat()

                cursor.execute(
                    """INSERT INTO users
                       (id, username, password_hash, salt, display_name, email, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (user_id, username, password_hash, salt, display_name, email, now, now),
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

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
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT id, username, password_hash, salt, display_name, email, level, "
                "target_field, available_time, preference FROM users WHERE username = %s",
                (username,),
            )
            user = cursor.fetchone()
            if not user:
                raise ValueError("用户名或密码错误")

            expected_hash = self._hash_password(password, user["salt"])
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                raise ValueError("用户名或密码错误")

            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE users SET last_login_at = %s, updated_at = %s WHERE id = %s",
                (now, now, user["id"]),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

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

        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                (token, user_id, now, expires_at),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return {"token": token, "expires_at": expires_at}

    def validate_token(self, token: str) -> Optional[str]:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token = %s", (token,)
            )
            session = cursor.fetchone()
            if not session:
                return None
            expires = datetime.fromisoformat(session["expires_at"])
            if datetime.now() > expires:
                cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
                conn.commit()
                return None
            return session["user_id"]
        finally:
            cursor.close()
            conn.close()

    def logout(self, token: str) -> None:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT id, username, display_name, email, level, target_field, "
                "available_time, preference, created_at, last_login_at FROM users WHERE id = %s",
                (user_id,),
            )
            user = cursor.fetchone()
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
        finally:
            cursor.close()
            conn.close()

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
        set_clause = ", ".join(f"{k} = %s" for k in filtered)
        values = list(filtered.values()) + [now, user_id]

        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                f"UPDATE users SET {set_clause}, updated_at = %s WHERE id = %s", values
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return self.get_profile(user_id) or {}

    def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        if len(new_password) < 6:
            raise ValueError("新密码长度不能少于6位")
        if old_password == new_password:
            raise ValueError("新密码不能与旧密码相同")

        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT password_hash, salt FROM users WHERE id = %s", (user_id,)
            )
            user = cursor.fetchone()
            if not user:
                raise ValueError("用户不存在")

            expected_hash = self._hash_password(old_password, user["salt"])
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                raise ValueError("原密码错误")

            new_salt = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
            new_hash = self._hash_password(new_password, new_salt)
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE users SET password_hash = %s, salt = %s, updated_at = %s WHERE id = %s",
                (new_hash, new_salt, now, user_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        logger.info(f"密码修改成功 | user_id={user_id}")

    def update_progress(
        self, user_id: str, knowledge_point: str, is_correct: bool
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT total_attempts, correct_count FROM learning_progress "
                "WHERE user_id = %s AND knowledge_point = %s",
                (user_id, knowledge_point),
            )
            existing = cursor.fetchone()

            if existing:
                total = int(existing["total_attempts"]) + 1
                correct = int(existing["correct_count"]) + (1 if is_correct else 0)
                mastery = correct / total if total > 0 else 0.0
                cursor.execute(
                    "UPDATE learning_progress SET total_attempts = %s, correct_count = %s, "
                    "mastery_level = %s, last_practiced_at = %s WHERE user_id = %s AND knowledge_point = %s",
                    (total, correct, round(mastery, 3), now, user_id, knowledge_point),
                )
            else:
                total = 1
                correct = 1 if is_correct else 0
                mastery = correct / total
                cursor.execute(
                    "INSERT INTO learning_progress "
                    "(user_id, knowledge_point, mastery_level, total_attempts, correct_count, last_practiced_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, knowledge_point, round(mastery, 3), total, correct, now),
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return {
            "knowledge_point": knowledge_point,
            "total_attempts": total if existing else 1,
            "correct_count": correct if existing else (1 if is_correct else 0),
            "mastery_level": round(mastery if existing else (1.0 if is_correct else 0.0), 3),
        }

    def get_progress(self, user_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT knowledge_point, mastery_level, total_attempts, correct_count, "
                "last_practiced_at FROM learning_progress WHERE user_id = %s "
                "ORDER BY mastery_level ASC",
                (user_id,),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
        return [dict(r) for r in rows]

    def get_weak_points(self, user_id: str, threshold: float = 0.6) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT knowledge_point, mastery_level, total_attempts, correct_count "
                "FROM learning_progress WHERE user_id = %s AND mastery_level < %s "
                "ORDER BY mastery_level ASC",
                (user_id, threshold),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
        return [dict(r) for r in rows]

    # ==================== 对话管理 ====================

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        """获取用户的所有对话列表"""
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at,
                          COUNT(cm.id) as message_count
                   FROM conversations c
                   LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                   WHERE c.user_id = %s
                   GROUP BY c.id, c.title, c.created_at, c.updated_at
                   ORDER BY c.updated_at DESC""",
                (user_id,),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
        return [dict(r) for r in rows]

    def create_conversation(self, user_id: str, title: str = "", conv_id: str = "") -> dict[str, Any]:
        """创建新对话"""
        import uuid
        conv_id = conv_id or str(uuid.uuid4())
        now = datetime.now().isoformat()
        title = title or "新对话"
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (conv_id, user_id, title, now, now),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return {"id": conv_id, "title": title, "created_at": now, "message_count": 0}

    def get_conversation(self, user_id: str, conv_id: str) -> Optional[dict[str, Any]]:
        """获取对话详情（含消息）"""
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE id = %s AND user_id = %s",
                (conv_id, user_id),
            )
            conv = cursor.fetchone()
            if not conv:
                return None
            cursor.execute(
                "SELECT role, content, created_at FROM conversation_messages "
                "WHERE conversation_id = %s ORDER BY id ASC",
                (conv_id,),
            )
            messages = [dict(m) for m in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
        return {
            "id": conv["id"],
            "title": conv["title"],
            "messages": messages,
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        }

    def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        """删除对话（级联删除消息）"""
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                (conv_id, user_id),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return deleted

    def update_conversation_title(self, user_id: str, conv_id: str, title: str) -> bool:
        """更新对话标题"""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "UPDATE conversations SET title = %s, updated_at = %s "
                "WHERE id = %s AND user_id = %s",
                (title, now, conv_id, user_id),
            )
            updated = cursor.rowcount > 0
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        return updated

    def append_message(self, conv_id: str, role: str, content: str) -> None:
        """向对话追加消息"""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "INSERT INTO conversation_messages (conversation_id, role, content, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (conv_id, role, content, now),
            )
            cursor.execute(
                "UPDATE conversations SET updated_at = %s WHERE id = %s",
                (now, conv_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def trim_conversation_messages(self, conv_id: str, max_messages: int = 200) -> None:
        """裁剪对话消息，保留最近 N 条"""
        conn = self._get_conn()
        try:
            cursor = self._get_cursor(conn)
            cursor.execute(
                "SELECT COUNT(*) as c FROM conversation_messages WHERE conversation_id = %s",
                (conv_id,),
            )
            row = cursor.fetchone()
            total = row["c"] if row else 0
            if total > max_messages:
                delete_count = total - max_messages
                cursor.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = %s "
                    "ORDER BY id ASC LIMIT %s",
                    (conv_id, delete_count),
                )
                conn.commit()
        finally:
            cursor.close()
            conn.close()

    def check_health(self) -> dict[str, Any]:
        try:
            conn = self._get_conn()
            try:
                cursor = self._get_cursor(conn)
                cursor.execute("SELECT COUNT(*) as c FROM users")
                row = cursor.fetchone()
                user_count = row["c"] if row else 0
            finally:
                cursor.close()
                conn.close()
            return {
                "status": "ok",
                "user_count": user_count,
                "db_type": "mysql",
                "host": f"{Settings.MYSQL_HOST}:{Settings.MYSQL_PORT}",
                "database": Settings.MYSQL_DATABASE,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store