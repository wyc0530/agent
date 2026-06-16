import asyncio
from contextlib import asynccontextmanager
import json
import threading
import time
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import Settings, logger
from src.core.memory import VectorStore
from src.core.retriever import Retriever
from src.embedding import EmbeddingProvider
from src.llm import LLMProvider
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()
_RATE_WINDOW = 60
_RATE_MAX_REQUESTS = 100
_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/auth/register", "/auth/login"}
_AUTH_PATHS = {"/auth/register", "/auth/login"}
_AUTH_RATE_LIMIT: dict[str, list[float]] = {}
_AUTH_RATE_WINDOW = 300
_AUTH_RATE_MAX = 10


def reset_rate_limits():
    """重置所有速率限制器状态（仅供测试使用）。"""
    _RATE_LIMIT.clear()
    _AUTH_RATE_LIMIT.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):

    def __init__(self, app):
        super().__init__(app)
        self._last_cleanup: float = 0.0

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS and path not in _AUTH_PATHS:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()

        if path in _AUTH_PATHS:
            return await self._check_auth_rate(path, client, now, call_next, request)

        if now - self._last_cleanup > 300:
            with _RATE_LOCK:
                stale = [c for c, ts_list in list(_RATE_LIMIT.items()) if not [t for t in ts_list if now - t < _RATE_WINDOW]]
                for c in stale:
                    del _RATE_LIMIT[c]
            self._last_cleanup = now

        with _RATE_LOCK:
            if client not in _RATE_LIMIT:
                _RATE_LIMIT[client] = []
            remaining = [t for t in _RATE_LIMIT[client] if now - t < _RATE_WINDOW]

            if len(remaining) >= _RATE_MAX_REQUESTS:
                logger.warning(f"速率限制触发 | client={client}")
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请在1分钟后重试"},
                )

            remaining.append(now)
            _RATE_LIMIT[client] = remaining

        return await call_next(request)

    async def _check_auth_rate(self, path: str, client: str, now: float, call_next, request: Request):
        with _RATE_LOCK:
            if client not in _AUTH_RATE_LIMIT:
                _AUTH_RATE_LIMIT[client] = []
            remaining = [t for t in _AUTH_RATE_LIMIT[client] if now - t < _AUTH_RATE_WINDOW]
            if len(remaining) >= _AUTH_RATE_MAX:
                logger.warning(f"认证频率限制触发 | client={client}")
                return JSONResponse(
                    status_code=429,
                    content={"detail": "认证请求过于频繁，请在5分钟后重试"},
                )
            remaining.append(now)
            _AUTH_RATE_LIMIT[client] = remaining
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key")

        if api_key and api_key == Settings.API_KEY:
            return await call_next(request)

        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            if token == Settings.API_KEY:
                return await call_next(request)
            from src.core.user_store import get_user_store
            user_id = get_user_store().validate_token(token)
            if user_id:
                request.state.user_id = user_id
                return await call_next(request)

        if not Settings.API_AUTH_ENABLED:
            return await call_next(request)

        logger.warning(f"认证失败 | path={path} client={request.client.host if request.client else 'unknown'}")
        return JSONResponse(
            status_code=401,
            content={"detail": "未授权访问，请提供有效的 API Key 或登录凭据"},
        )


class ChatRequest(BaseModel):
    message: str = Field(description="用户消息", min_length=1, max_length=5000)
    user_id: str = Field(default="default", description="用户ID", max_length=100)
    thread_id: str = Field(default="default", description="对话线程ID", max_length=100)
    conversation_id: str = Field(default="", description="对话ID", max_length=100)
    system_prompt: str = Field(default="", description="系统提示词", max_length=2000)
    agent_role: str = Field(default="", max_length=50, pattern=r"^(planner|expert|partner|quizzer|reviewer|examiner|)$", description="指定Agent角色，留空则自动")
    history: list[dict[str, str]] = Field(default=[], description="前端最近对话历史（冗余恢复）")


class ChatResponse(BaseModel):
    response: str = Field(description="AI回复")
    agent_role: str = Field(default="assistant", description="处理Agent")


class SearchRequest(BaseModel):
    query: str = Field(description="搜索关键词", max_length=500)
    top_k: int = Field(default=5, description="返回数量", ge=1, le=20)
    include_web: bool = Field(default=False, description="是否包含网络搜索")


class MemoryStoreRequest(BaseModel):
    content: str = Field(description="要存储的内容", max_length=50000)
    user_id: str = Field(default="default_user", description="用户ID", max_length=100)
    memory_type: str = Field(default="interaction", description="记忆类型", max_length=50)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(description="待向量化的文本列表", max_length=100, min_length=1)


class GraphSearchRequest(BaseModel):
    keyword: str = Field(description="搜索关键词", max_length=200)
    limit: int = Field(default=20, description="返回数量", ge=1, le=100)


class GraphPathRequest(BaseModel):
    start_node_id: str = Field(description="起始节点ID", max_length=200)
    target_node_id: str = Field(description="目标节点ID", max_length=200)
    max_depth: int = Field(default=5, description="最大搜索深度", ge=1, le=10)


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    components: dict[str, Any] = Field(default_factory=dict)


class RegisterRequest(BaseModel):
    username: str = Field(description="用户名", min_length=3, max_length=50)
    password: str = Field(description="密码", min_length=6, max_length=100)
    display_name: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(description="用户名", max_length=50)
    password: str = Field(description="密码", max_length=100)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    display_name: str = ""
    token: str
    expires_at: str


class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    display_name: str = ""
    email: str = ""
    level: str = "beginner"
    target_field: str = ""
    available_time: int = 10
    preference: str = "comprehensive"
    created_at: str = ""
    last_login_at: str = ""


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=100)
    level: str = Field(default="", max_length=30)
    target_field: str = Field(default="", max_length=100)
    available_time: int = Field(default=10, ge=0, le=168)
    preference: str = Field(default="", max_length=50)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(description="原密码", min_length=1, max_length=100)
    new_password: str = Field(description="新密码", min_length=6, max_length=100)


class ProgressUpdateRequest(BaseModel):
    knowledge_point: str = Field(description="知识点", max_length=200)
    is_correct: bool = Field(description="是否回答正确")


class ProgressResponse(BaseModel):
    knowledge_point: str
    mastery_level: float
    total_attempts: int
    correct_count: int
    last_practiced_at: str = ""


_agent_cache: dict[str, Any] = {}
_agent_cache_lock = threading.Lock()
_conversation_history: dict[str, dict[str, Any]] = {}
_last_access: dict[str, float] = {}
_CONV_TTL_SECONDS = 7200
_CONV_CLEANUP_INTERVAL = 600
_last_conv_cleanup: float = 0.0
_CONV_HISTORY_PATH = "data/conversation_history.json"
_CONVERSATIONS_PATH = "data/conversations.json"
_conversations: dict[str, list[dict[str, Any]]] = {}


def _load_conversations() -> None:
    """从磁盘加载多对话数据"""
    import os as _os
    global _conversations
    try:
        if _os.path.exists(_CONVERSATIONS_PATH):
            with open(_CONVERSATIONS_PATH, "r", encoding="utf-8") as f:
                _conversations = json.load(f)
            total = sum(len(v) for v in _conversations.values())
            if total:
                logger.info(f"多对话数据从磁盘恢复 | conversations={total}")
    except Exception as e:
        logger.warning(f"多对话数据加载失败: {e}")


def _save_conversations() -> None:
    """保存多对话数据到磁盘"""
    import os as _os
    try:
        _os.makedirs(_os.path.dirname(_CONVERSATIONS_PATH), exist_ok=True)
        with open(_CONVERSATIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(_conversations, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"多对话数据保存失败: {e}")


def _get_user_conversations(user_id: str) -> list[dict[str, Any]]:
    """获取用户的所有对话"""
    if user_id not in _conversations:
        _conversations[user_id] = []
    return _conversations[user_id]


def _get_conversation(user_id: str, conv_id: str) -> Optional[dict[str, Any]]:
    """获取指定对话"""
    for conv in _get_user_conversations(user_id):
        if conv.get("id") == conv_id:
            return conv
    return None


# 启动时加载多对话数据
_load_conversations()


def _load_conversation_history() -> None:
    global _conversation_history
    import os as _os
    try:
        if _os.path.exists(_CONV_HISTORY_PATH):
            with open(_CONV_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = 0
            for uid, entry in data.items():
                if isinstance(entry, dict) and "messages" in entry:
                    _conversation_history[uid] = {
                        "messages": entry["messages"][-200:],
                        "created_at": entry.get("created_at", time.time()),
                    }
                    loaded += 1
            if loaded:
                logger.info(f"对话历史从磁盘恢复 | users={loaded}")
    except Exception as e:
        logger.warning(f"对话历史加载失败: {e}")


def _save_conversation_history() -> None:
    import os as _os
    try:
        _os.makedirs(_os.path.dirname(_CONV_HISTORY_PATH), exist_ok=True)
        data = {}
        for uid, entry in _conversation_history.items():
            if isinstance(entry, dict) and entry.get("messages"):
                data[uid] = {
                    "messages": entry["messages"][-200:],
                    "created_at": entry.get("created_at", time.time()),
                }
        with open(_CONV_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"对话历史保存失败: {e}")


_KNOWN_REPLY_KEYS = ("reply", "answer", "plan_text", "analysis", "ai_recommendation", "exam_guidance")


def _try_parse_json(text: str) -> Optional[dict[str, Any]]:
    if not text or not isinstance(text, str):
        return None

    attempts = [text.strip()]

    if "```json" in text:
        parts = text.split("```json")
        if len(parts) >= 2:
            inner = parts[1].split("```")
            if inner:
                attempts.append(inner[0].strip())
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            attempts.append(parts[1].strip())

    attempt_count = 0
    for attempt in attempts:
        attempt_count += 1
        try:
            return json.loads(attempt)
        except (json.JSONDecodeError, ValueError, TypeError):
            if attempt_count >= len(attempts):
                start = attempt.find("{")
                end = attempt.rfind("}")
                if start >= 0 and end > start:
                    try:
                        return json.loads(attempt[start:end + 1])
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
    return None


def _format_planner_output(output: dict[str, Any]) -> str:
    plan_text = output.get("plan_text", "")
    if not plan_text or not isinstance(plan_text, str):
        return plan_text

    data = _try_parse_json(plan_text)
    if not data:
        return plan_text

    lines = []
    title = data.get("title", "学习计划")
    lines.append(f"## {title}")
    lines.append("")

    goals = data.get("goals", [])
    if goals:
        lines.append("### 学习目标")
        for g in goals:
            if isinstance(g, dict):
                g_title = g.get("title", "")
                g_desc = g.get("description", "")
                g_date = g.get("target_date", "")
                g_priority = g.get("priority", "")
                priority_icon = "🔴" if g_priority == "high" else "🟡" if g_priority == "medium" else "🟢"
                lines.append(f"- {priority_icon} **{g_title}**")
                if g_desc:
                    lines.append(f"  {g_desc}")
                if g_date:
                    lines.append(f"  目标日期: {g_date}")
        lines.append("")

    phases = data.get("phases", [])
    if phases:
        lines.append("### 学习阶段")
        for p in phases:
            if isinstance(p, dict):
                p_title = p.get("title", "")
                p_desc = p.get("description", "")
                p_days = p.get("duration_days", 0)
                p_topics = p.get("topics", [])
                lines.append(f"#### {p_title}")
                if p_desc:
                    lines.append(f"_{p_desc}_")
                if p_days:
                    lines.append(f"预计时长: {p_days} 天")
                if p_topics:
                    for t in p_topics:
                        lines.append(f"- {t}")
                lines.append("")

    return "\n".join(lines)


def _format_reviewer_output(output: dict[str, Any]) -> str:
    analysis = output.get("analysis", "")
    if not analysis or not isinstance(analysis, str):
        return analysis

    data = _try_parse_json(analysis)
    if not data:
        return analysis

    lines = []
    lines.append("## 学习复习分析")
    lines.append("")

    error_categories = data.get("error_categories", [])
    if error_categories:
        lines.append("### 错误分类")
        for cat in error_categories:
            if isinstance(cat, dict):
                cat_type = cat.get("type", "")
                cat_count = cat.get("count", 0)
                cat_kps = cat.get("knowledge_points", [])
                lines.append(f"- **{cat_type}** ({cat_count}次): {', '.join(str(k) for k in cat_kps)}")
        lines.append("")

    weak_summary = data.get("weak_points_summary", [])
    if weak_summary:
        lines.append("### 薄弱知识点")
        for w in weak_summary:
            lines.append(f"- {w}")
        lines.append("")

    suggestions = data.get("review_suggestions", [])
    if suggestions:
        lines.append("### 复习建议")
        for s in suggestions:
            if isinstance(s, dict):
                kp = s.get("knowledge_point", "")
                method = s.get("method", "")
                lines.append(f"- **{kp}**: {method}")
            elif isinstance(s, str):
                lines.append(f"- {s}")
        lines.append("")

    feedback = data.get("feedback_for_planner", "")
    if feedback:
        lines.append(f"### 学习计划调整建议\n{feedback}")
        lines.append("")

    return "\n".join(lines)


def _format_quizzer_output(output: dict[str, Any]) -> str:
    lines = []
    difficulty = output.get("difficulty", 0.5)
    strategy = output.get("strategy", "")

    if strategy:
        lines.append(f"## {strategy}")
        lines.append(f"难度系数: {difficulty:.0%}")
    else:
        lines.append("## 测验题目")
    lines.append("")

    questions = output.get("questions", [])
    if questions:
        for i, q in enumerate(questions, 1):
            if isinstance(q, dict):
                q_text = q.get("question", q.get("title", str(q)))
                q_options = q.get("options", [])
                q_type = q.get("type", "")
                lines.append(f"### 第{i}题")
                if q_type:
                    lines.append(f"题型: {q_type}")
                lines.append(f"{q_text}")
                if q_options:
                    for j, opt in enumerate(q_options):
                        if isinstance(opt, dict):
                            label = opt.get("label", chr(65 + j))
                            text = opt.get("text", str(opt))
                            lines.append(f"- {label}. {text}")
                        else:
                            lines.append(f"- {chr(65 + j)}. {opt}")
                lines.append("")

    assessment = output.get("assessment", {})
    if isinstance(assessment, dict) and assessment:
        lines.append("### 能力评估")
        level = assessment.get("level", assessment.get("overall", ""))
        if level:
            lines.append(f"综合水平: {level}")
        strengths = assessment.get("strengths", [])
        if strengths:
            lines.append(f"优势: {', '.join(str(s) for s in strengths)}")
        weaknesses = assessment.get("weaknesses", [])
        if weaknesses:
            lines.append(f"待加强: {', '.join(str(w) for w in weaknesses)}")
        lines.append("")

    if not questions:
        lines.append("暂无题目生成，请稍后重试。")

    return "\n".join(lines)


def _format_conversation_context(user_id: str, max_turns: int = 3) -> str:
    """将对话历史格式化为上下文摘要块，防止 LLM 重复回答历史问题。"""
    if not user_id:
        return ""
    try:
        history = _conversation_history.get(user_id, {}).get("messages", [])
        recent = history[-(max_turns * 2):]
        if not recent:
            return ""
        lines = [
            "## 对话历史（仅供参考，请勿重复回答历史问题）"
        ]
        for i, h in enumerate(recent):
            role_tag = "用户" if h.get("role") == "user" else "助手"
            content = str(h.get("content", ""))[:150]
            lines.append(f"{i + 1}. [{role_tag}]: {content}")
        lines.append("\n请仅回答用户的最新的问题，不要重复回答历史对话中已涉及的内容。")
        return "\n".join(lines) + "\n\n"
    except Exception:
        return ""


class CSRFMiddleware(BaseHTTPMiddleware):
    """基于Origin/Referer校验的CSRF防护中间件。

    仅对状态变更请求（POST/PUT/PATCH/DELETE）生效，
    验证请求的Origin或Referer头与服务器预期来源一致。
    使用精确域名匹配而非子串匹配，防止域名绕过攻击。
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
        if not origin:
            return await call_next(request)

        from urllib.parse import urlparse
        parsed = urlparse(origin)
        allowed_host = (parsed.hostname or "").lower()

        _LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})
        if allowed_host in _LOCAL_HOSTS:
            return await call_next(request)

        api_base = (Settings.ALLOWED_ORIGIN or "").strip()
        if not api_base:
            return await call_next(request)

        allowed_hosts = {h.strip().lower() for h in api_base.split(",") if h.strip()}
        if allowed_host in allowed_hosts:
            return await call_next(request)

        logger.warning(f"CSRF校验失败 | origin={origin} method={request.method}")
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF校验失败，请从受信任的来源访问"},
        )


def _extract_reply(result) -> str:
    if not result.output:
        return result.error if result.error is not None else "Agent 处理完成"

    agent_role = getattr(result, "agent_role", None)
    if agent_role:
        role_str = agent_role.value if hasattr(agent_role, "value") else str(agent_role)
        if role_str == "planner":
            return _format_planner_output(result.output)
        if role_str == "reviewer":
            return _format_reviewer_output(result.output)
        if role_str == "quizzer":
            return _format_quizzer_output(result.output)

    for key in _KNOWN_REPLY_KEYS:
        val = result.output.get(key)
        if val and isinstance(val, str) and len(val) > 1:
            return val

    if result.output:
        formatted = _format_planner_output(result.output)
        if formatted and formatted != result.output.get("plan_text", ""):
            return formatted
        formatted = _format_reviewer_output(result.output)
        if formatted and formatted != result.output.get("analysis", ""):
            return formatted
        formatted = _format_quizzer_output(result.output)
        if formatted and formatted != "## 测验题目\n\n暂无题目生成，请稍后重试。":
            return formatted
        return json.dumps(result.output, ensure_ascii=False, default=str, indent=2)

    return "Agent 处理完成"


def _build_agent_state(message: str, user_id: str, frontend_history: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    if user_id and user_id not in _conversation_history:
        _conversation_history[user_id] = {"messages": [], "created_at": time.time()}
        if frontend_history:
            _conversation_history[user_id]["messages"] = frontend_history[-20:]
    if user_id:
        _last_access[user_id] = time.time()
        _cleanup_stale_conversations()
    entry = _conversation_history.get(user_id, {})
    messages = (entry.get("messages", []) if user_id else []) + [
        {"role": "user", "content": message}
    ]

    _MAX_CONTEXT_BUILD = 60
    if len(messages) > _MAX_CONTEXT_BUILD:
        messages = messages[-_MAX_CONTEXT_BUILD:]
        if user_id and user_id in _conversation_history:
            _conversation_history[user_id]["messages"] = _conversation_history[user_id]["messages"][-_MAX_CONTEXT_BUILD:]

    return {
        "user_id": user_id,
        "user_profile": {},
        "messages": messages,
        "agent_outputs": {},
        "weak_points": [],
    }


def _cleanup_stale_conversations() -> None:
    global _last_conv_cleanup
    now = time.time()
    if now - _last_conv_cleanup < _CONV_CLEANUP_INTERVAL:
        return
    _last_conv_cleanup = now
    stale = [
        uid for uid, ts in _last_access.items()
        if now - ts > _CONV_TTL_SECONDS
    ]
    for uid in stale:
        _conversation_history.pop(uid, None)
        _last_access.pop(uid, None)
    if stale:
        logger.info(f"对话历史TTL清理 | removed={len(stale)} users")
    if len(_conversation_history) > 5000:
        excess = len(_conversation_history) - 4000
        sorted_users = sorted(_last_access.items(), key=lambda x: x[1])
        for uid, _ in sorted_users[:excess]:
            _conversation_history.pop(uid, None)
            _last_access.pop(uid, None)
        logger.info(f"历史记录容量清理: 移除 {excess} 个非活跃用户")


def _append_to_history(user_id: str, role: str, content: str) -> None:
    if not user_id or not content:
        return
    if user_id not in _conversation_history:
        _conversation_history[user_id] = {"messages": [], "created_at": time.time()}
    _conversation_history[user_id]["messages"].append({"role": role, "content": content})
    _last_access[user_id] = time.time()
    if len(_conversation_history[user_id]["messages"]) > 500:
        _conversation_history[user_id]["messages"] = _conversation_history[user_id]["messages"][-200:]
    _maybe_save_history_periodically()


_SAVE_COUNTER: int = 0
_SAVE_THRESHOLD = 20


def _maybe_save_history_periodically() -> None:
    global _SAVE_COUNTER
    _SAVE_COUNTER += 1
    if _SAVE_COUNTER >= _SAVE_THRESHOLD:
        _save_conversation_history()
        _SAVE_COUNTER = 0


def _ensure_agents():
    global _agent_cache
    if _agent_cache:
        return _agent_cache

    with _agent_cache_lock:
        if _agent_cache:
            return _agent_cache

        from src.agents.assistant import SupervisorAgent
        from src.agents.planner import PlannerAgent
        from src.agents.expert import ExpertAgent
        from src.agents.partner import PartnerAgent
        from src.agents.quizzer import QuizzerAgent
        from src.agents.reviewer import ReviewerAgent
        from src.agents.examiner import ExaminerAgent
        from src.core.state import AgentRole

        supervisor = SupervisorAgent()

        role_map = {
            "planner": (AgentRole.PLANNER, PlannerAgent),
            "expert": (AgentRole.EXPERT, ExpertAgent),
            "partner": (AgentRole.PARTNER, PartnerAgent),
            "quizzer": (AgentRole.QUIZZER, QuizzerAgent),
            "reviewer": (AgentRole.REVIEWER, ReviewerAgent),
            "examiner": (AgentRole.EXAMINER, ExaminerAgent),
        }
        for role_key, (role_enum, agent_cls) in role_map.items():
            supervisor.register_sub_agent(agent_cls())

        _agent_cache["supervisor"] = supervisor
        _agent_cache["role_map"] = role_map
        logger.info("Agent实例已缓存，后续请求将复用")
        return _agent_cache


def _reset_agent_cache():
    global _agent_cache, _conversation_history, _last_access
    with _agent_cache_lock:
        _agent_cache = {}
        _conversation_history.clear()
        _last_access.clear()
    from src.core.communication import get_communication
    comm = get_communication()
    comm._agent_registry.clear()
    logger.info("Agent实例缓存已重置")


async def _route_with_agent(message: str, user_id: str, agent_role: str = "", timeout: float = 120.0, history: Optional[list[dict[str, str]]] = None) -> tuple[str, str]:
    cache = _ensure_agents()
    supervisor = cache["supervisor"]
    role_map = cache["role_map"]

    target_role = None
    if agent_role and agent_role in role_map:
        target_role = role_map[agent_role][0]

    state = _build_agent_state(message, user_id, history)

    try:
        msg_list = state.get("messages", [])
        _MAX_CONTEXT_MSGS = 50
        if len(msg_list) > _MAX_CONTEXT_MSGS:
            state["messages"] = msg_list[-_MAX_CONTEXT_MSGS:]
            if user_id and user_id in _conversation_history:
                _conversation_history[user_id]["messages"] = _conversation_history[user_id]["messages"][-_MAX_CONTEXT_MSGS:]
            logger.info(f"对话上下文裁剪 | original={len(msg_list)} cropped={_MAX_CONTEXT_MSGS}")
    except Exception as e:
        logger.warning(f"对话上下文裁剪失败: {e}")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(supervisor.run, state, message, target_role),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error(f"Agent 执行超时 | timeout={timeout}s")
        raise HTTPException(status_code=504, detail="请求处理超时，请稍后重试")

    reply = _extract_reply(result)

    _append_to_history(user_id, "user", message)
    _append_to_history(user_id, "assistant", reply)
    return reply, result.agent_role.value


def _build_allowed_origins() -> list[str]:
    if Settings.DEBUG:
        return ["http://localhost:8501", "http://localhost:8000", "http://127.0.0.1:8501"]
    allowed = (Settings.ALLOWED_ORIGIN or "").strip()
    if allowed:
        return [f"https://{h.strip()}" for h in allowed.split(",") if h.strip()]
    return ["http://localhost:3000"]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """注入安全响应头，防御常见Web攻击。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if hasattr(response, "headers"):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("学习辅助系统 API 启动中...")
    logger.info(Settings.display())

    _load_conversation_history()

    from src.core.tools.base import register_all_tools
    register_all_tools()
    logger.info("全部工具已自动注册")

    logger.info("=" * 50)
    yield
    _save_conversation_history()
    _reset_agent_cache()
    logger.info("学习辅助系统 API 关闭")


app = FastAPI(
    title="学习辅助系统 API",
    description="基于 LangGraph 的多智能体学习辅助系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(AuthMiddleware)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    components = {}
    try:
        llm = LLMProvider()
        components["llm"] = llm.check_health()
    except Exception as e:
        components["llm"] = {"status": "uninitialized", "error": str(e)}

    try:
        embedding = EmbeddingProvider()
        components["embedding"] = embedding.check_health()
    except Exception as e:
        components["embedding"] = {"status": "uninitialized", "error": str(e)}

    try:
        store = VectorStore()
        components["vector_store"] = store.check_health()
    except Exception as e:
        components["vector_store"] = {"status": "uninitialized", "error": str(e)}

    try:
        retriever = Retriever()
        components["retriever"] = retriever.check_health()
    except Exception as e:
        components["retriever"] = {"status": "uninitialized", "error": str(e)}

    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        components["graph_store"] = graph.check_health()
    except Exception as e:
        components["graph_store"] = {"status": "uninitialized", "error": str(e)}

    try:
        from src.core.checkpoint import get_checkpoint_manager, get_summarizer
        checkpoint = get_checkpoint_manager()
        components["checkpoint"] = checkpoint.check_health()
        summarizer = get_summarizer()
        components["summarizer"] = summarizer.check_health()
    except Exception as e:
        components["checkpoint"] = {"status": "uninitialized", "error": str(e)}

    try:
        from src.core.user_store import get_user_store
        user_store = get_user_store()
        components["user_store"] = user_store.check_health()
    except Exception as e:
        components["user_store"] = {"status": "uninitialized", "error": str(e)}

    all_ok = all(
        c.get("status") in ("ok", "passed")
        for c in components.values()
        if isinstance(c, dict)
    )
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        components=components,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        if request.agent_role:
            reply, agent_role = await _route_with_agent(request.message, request.user_id, request.agent_role, history=request.history)
            return ChatResponse(response=reply, agent_role=agent_role)

        llm = LLMProvider()
        history = _conversation_history.get(request.user_id, {}).get("messages", []) if request.user_id else []
        response = llm.chat_with_history(request.message, history, system_prompt=request.system_prompt) if history else llm.chat(request.message, system_prompt=request.system_prompt)
        _append_to_history(request.user_id, "user", request.message)
        _append_to_history(request.user_id, "assistant", response)
        return ChatResponse(response=response, agent_role="assistant")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="对话服务暂时不可用，请稍后重试")


@app.post("/search")
async def search(request: SearchRequest):
    try:
        retriever = Retriever()
        result = retriever.retrieve_and_generate(
            query=request.query,
            top_k=request.top_k,
            include_web=request.include_web,
        )
        return result
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="搜索服务暂时不可用，请稍后重试")


@app.post("/embed")
async def embed_texts(request: EmbedRequest):
    try:
        embedding = EmbeddingProvider()
        vectors = embedding.embed_batch(request.texts)
        return {
            "count": len(vectors),
            "dimension": len(vectors[0]) if vectors else 0,
            "vectors": vectors,
        }
    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(status_code=500, detail="嵌入服务暂时不可用，请稍后重试")


@app.get("/tools")
async def list_tools():
    try:
        from src.core.tools.base import get_tool_registry
        registry = get_tool_registry()
        return {"tools": registry.list_all()}
    except Exception as e:
        logger.error(f"Tools error: {e}")
        raise HTTPException(status_code=500, detail="工具服务暂时不可用，请稍后重试")


@app.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    try:
        from src.core.memory import LongTermMemory
        memory = LongTermMemory(user_id=request.user_id)
        doc_id = memory.store_learning_material(request.content, request.memory_type)
        return {"status": "stored", "doc_id": doc_id}
    except Exception as e:
        logger.error(f"Memory store error: {e}")
        raise HTTPException(status_code=500, detail="记忆存储服务暂时不可用，请稍后重试")


@app.get("/graph/stats")
async def graph_stats():
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        return graph.get_stats()
    except Exception as e:
        logger.error(f"Graph stats error: {e}")
        raise HTTPException(status_code=500, detail="图谱统计服务暂时不可用，请稍后重试")


@app.post("/graph/search")
async def graph_search(request: GraphSearchRequest):
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        nodes = graph.search_nodes(keyword=request.keyword, limit=request.limit)
        return {"keyword": request.keyword, "count": len(nodes), "nodes": nodes}
    except Exception as e:
        logger.error(f"Graph search error: {e}")
        raise HTTPException(status_code=500, detail="图谱搜索服务暂时不可用，请稍后重试")


@app.post("/graph/path")
async def graph_path(request: GraphPathRequest):
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        path = graph.build_learning_path(
            start_node_id=request.start_node_id,
            target_node_id=request.target_node_id,
            max_depth=request.max_depth,
        )
        return {"start": request.start_node_id, "target": request.target_node_id, "path": path}
    except Exception as e:
        logger.error(f"Graph path error: {e}")
        raise HTTPException(status_code=500, detail="图谱路径服务暂时不可用，请稍后重试")


@app.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    try:
        from src.core.user_store import get_user_store
        store = get_user_store()
        result = store.register_user(
            username=request.username,
            password=request.password,
            display_name=request.display_name,
            email=request.email,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail="注册失败，用户名可能已存在")
    except Exception as e:
        logger.error(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="注册服务暂时不可用，请稍后重试")


@app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    try:
        from src.core.user_store import get_user_store
        store = get_user_store()
        result = store.login(username=request.username, password=request.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail="认证失败，用户名或密码错误")
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="登录服务暂时不可用，请稍后重试")


@app.post("/auth/logout")
async def logout(request: Request):
    try:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        if token:
            from src.core.user_store import get_user_store
            get_user_store().logout(token)
        return {"status": "logged_out"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="登出服务暂时不可用，请稍后重试")


@app.get("/user/profile", response_model=UserProfileResponse)
async def get_profile(request: Request):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        from src.core.user_store import get_user_store
        profile = get_user_store().get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="用户不存在")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="用户信息服务暂时不可用，请稍后重试")


@app.put("/user/profile", response_model=UserProfileResponse)
async def update_profile(request: Request, updates: ProfileUpdateRequest):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        from src.core.user_store import get_user_store
        update_dict = updates.model_dump(exclude_none=True, exclude_unset=True)
        profile = get_user_store().update_profile(user_id, update_dict)
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="用户信息更新服务暂时不可用，请稍后重试")


@app.put("/user/profile/password")
async def change_password(request: Request, password_data: PasswordChangeRequest):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        from src.core.user_store import get_user_store
        store = get_user_store()
        store.change_password(user_id, password_data.old_password, password_data.new_password)
        return {"status": "ok", "message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(status_code=500, detail="密码修改服务暂时不可用，请稍后重试")


@app.post("/user/progress", response_model=ProgressResponse)
async def update_progress(request: Request, body: ProgressUpdateRequest):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        from src.core.user_store import get_user_store
        result = get_user_store().update_progress(
            user_id=user_id,
            knowledge_point=body.knowledge_point,
            is_correct=body.is_correct,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update progress error: {e}")
        raise HTTPException(status_code=500, detail="学习进度更新服务暂时不可用，请稍后重试")


@app.get("/user/progress")
async def get_progress(request: Request):
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        from src.core.user_store import get_user_store
        progress = get_user_store().get_progress(user_id)
        weak_points = get_user_store().get_weak_points(user_id)
        return {
            "progress": progress,
            "weak_points": weak_points,
            "total_knowledge_points": len(progress),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get progress error: {e}")
        raise HTTPException(status_code=500, detail="学习进度服务暂时不可用，请稍后重试")


# ===================== 多对话管理 API =====================

class ConversationCreateRequest(BaseModel):
    title: str = Field(default="", description="对话标题", max_length=200)


class ConversationTitleRequest(BaseModel):
    title: str = Field(description="新标题", min_length=1, max_length=200)


@app.get("/conversations")
async def list_conversations(request: Request):
    """获取当前用户的所有对话列表"""
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        convs = _get_user_conversations(user_id)
        result = []
        for c in convs:
            result.append({
                "id": c.get("id", ""),
                "title": c.get("title", "新对话"),
                "created_at": c.get("created_at", 0),
                "updated_at": c.get("updated_at", 0),
                "message_count": len(c.get("messages", [])),
            })
        result.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return {"conversations": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List conversations error: {e}")
        raise HTTPException(status_code=500, detail="获取对话列表失败")


@app.post("/conversations")
async def create_conversation(body: ConversationCreateRequest, request: Request):
    """创建新对话"""
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        import uuid
        conv_id = str(uuid.uuid4())
        now = time.time()
        conv = {
            "id": conv_id,
            "title": body.title or "新对话",
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        _get_user_conversations(user_id).append(conv)
        _save_conversations()
        return {"id": conv_id, "title": conv["title"], "created_at": now, "message_count": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create conversation error: {e}")
        raise HTTPException(status_code=500, detail="创建对话失败")


@app.get("/conversations/{conv_id}")
async def get_conversation_messages(conv_id: str, request: Request):
    """获取指定对话的消息列表"""
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        conv = _get_conversation(user_id, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        return {
            "id": conv["id"],
            "title": conv.get("title", "新对话"),
            "messages": conv.get("messages", []),
            "created_at": conv.get("created_at", 0),
            "updated_at": conv.get("updated_at", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation messages error: {e}")
        raise HTTPException(status_code=500, detail="获取对话消息失败")


@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, request: Request):
    """删除指定对话"""
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        convs = _get_user_conversations(user_id)
        original_len = len(convs)
        _conversations[user_id] = [c for c in convs if c.get("id") != conv_id]
        if len(_conversations[user_id]) == original_len:
            raise HTTPException(status_code=404, detail="对话不存在")
        _save_conversations()
        return {"message": "对话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete conversation error: {e}")
        raise HTTPException(status_code=500, detail="删除对话失败")


@app.put("/conversations/{conv_id}/title")
async def update_conversation_title(conv_id: str, body: ConversationTitleRequest, request: Request):
    """更新对话标题"""
    try:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="请先登录")
        conv = _get_conversation(user_id, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        conv["title"] = body.title
        conv["updated_at"] = time.time()
        _save_conversations()
        return {"id": conv_id, "title": body.title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update conversation title error: {e}")
        raise HTTPException(status_code=500, detail="更新标题失败")


def _append_to_conversation(user_id: str, conv_id: str, role: str, content: str) -> None:
    """向指定对话追加消息"""
    if not user_id or not conv_id or not content:
        return
    conv = _get_conversation(user_id, conv_id)
    if not conv:
        return
    conv["messages"].append({"role": role, "content": content})
    conv["updated_at"] = time.time()
    if len(conv["messages"]) > 500:
        conv["messages"] = conv["messages"][-200:]
    # 自动设置标题（取第一条用户消息的前30字）
    if role == "user" and conv.get("title") == "新对话":
        conv["title"] = content[:30] + ("..." if len(content) > 30 else "")
    _save_conversations()


# ===================== 聊天 API =====================

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate() -> AsyncGenerator[str, None]:
        try:
            if request.agent_role:
                cache = _ensure_agents()
                supervisor = cache["supervisor"]
                role_map = cache["role_map"]

                target_role = None
                if request.agent_role in role_map:
                    target_role = role_map[request.agent_role][0]

                state = _build_agent_state(request.message, request.user_id, request.history)

                try:
                    msg_list = state.get("messages", [])
                    _MAX_CONTEXT_MSGS = 50
                    if len(msg_list) > _MAX_CONTEXT_MSGS:
                        state["messages"] = msg_list[-_MAX_CONTEXT_MSGS:]
                        if request.user_id and request.user_id in _conversation_history:
                            _conversation_history[request.user_id]["messages"] = _conversation_history[request.user_id]["messages"][-_MAX_CONTEXT_MSGS:]
                except Exception as e:
                    logger.warning(f"SSE对话上下文裁剪失败: {e}")

                yield f"data: {json.dumps({'type': 'start', 'agent_role': request.agent_role}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)

                # 使用 Agent 的 system prompt 和历史记录，通过 LLM 进行真正的流式输出
                agent = supervisor._agents.get(target_role) if target_role else None
                full_reply = ""

                if agent:
                    try:
                        system_prompt, user_msg, history, temperature, max_tokens = agent._build_stream_context(
                            state, request.message
                        )
                        llm = LLMProvider()
                        if history:
                            async for chunk in llm.stream_chat_with_history(
                                user_msg, history, system_prompt, temperature, max_tokens
                            ):
                                full_reply += chunk
                                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                        else:
                            async for chunk in llm.stream_chat(
                                user_msg, system_prompt, temperature, max_tokens
                            ):
                                full_reply += chunk
                                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.warning(f"Agent 流式输出失败，回退到同步模式 | role={request.agent_role} err={e}")
                        # 回退：使用同步 agent 调用 + 分块输出
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(None, supervisor.run, state, request.message, target_role)
                        full_reply = _extract_reply(result)
                        chunk_size = 50
                        for i in range(0, len(full_reply), chunk_size):
                            chunk_text = full_reply[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.02)
                else:
                    # 未找到对应 Agent，使用 assistant 流式输出
                    llm = LLMProvider()
                    model = llm.model
                    history_summary = _format_conversation_context(request.user_id, max_turns=2)
                    system_content = (
                        f"{request.system_prompt or '你是一个贴心的学习助手。'}\n\n"
                        f"{history_summary}"
                        f"请仅回答用户的最新问题。"
                    )
                    messages = [SystemMessage(content=system_content)]
                    messages.append(HumanMessage(content=request.message))
                    async for chunk in model.astream(messages):
                        content = chunk.content if hasattr(chunk, "content") and isinstance(chunk.content, str) else ""
                        if content:
                            full_reply += content
                            yield f"data: {json.dumps({'type': 'chunk', 'content': content}, ensure_ascii=False)}\n\n"

                _append_to_history(request.user_id, "user", request.message)
                _append_to_history(request.user_id, "assistant", full_reply)
                if request.conversation_id:
                    _append_to_conversation(request.user_id, request.conversation_id, "user", request.message)
                    _append_to_conversation(request.user_id, request.conversation_id, "assistant", full_reply)
            else:
                llm = LLMProvider()
                model = llm.model

                history_summary = _format_conversation_context(request.user_id, max_turns=2)

                system_content = (
                    f"{request.system_prompt or '你是一个贴心的学习助手。'}\n\n"
                    f"{history_summary}"
                    f"请仅回答用户的最新问题。"
                )

                messages = [SystemMessage(content=system_content)]
                messages.append(HumanMessage(content=request.message))

                yield f"data: {json.dumps({'type': 'start', 'agent_role': 'assistant'}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)

                try:
                    async for chunk in model.astream(messages):
                        content = chunk.content if hasattr(chunk, "content") and isinstance(chunk.content, str) else ""
                        if content:
                            yield f"data: {json.dumps({'type': 'chunk', 'content': content}, ensure_ascii=False)}\n\n"
                    _append_to_history(request.user_id, "user", request.message)
                    if request.conversation_id:
                        _append_to_conversation(request.user_id, request.conversation_id, "user", request.message)
                except (ValueError, RuntimeError, TypeError, KeyError, AttributeError):
                    logger.warning("流式对话失败，回退到非流式模式")
                    llm_response = await llm.achat(request.message, system_prompt=request.system_prompt)
                    chunk_size = 50
                    for i in range(0, len(llm_response), chunk_size):
                        chunk_text = llm_response[i:i + chunk_size]
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.02)
                    _append_to_history(request.user_id, "user", request.message)
                    _append_to_history(request.user_id, "assistant", llm_response)
                    if request.conversation_id:
                        _append_to_conversation(request.user_id, request.conversation_id, "user", request.message)
                        _append_to_conversation(request.user_id, request.conversation_id, "assistant", llm_response)

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except asyncio.TimeoutError:
            error_msg = f"data: {json.dumps({'type': 'error', 'content': '请求处理超时，请稍后重试'}, ensure_ascii=False)}\n\n"
            yield error_msg
        except Exception as e:
            error_msg = f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
            yield error_msg

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main():
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=Settings.HOST,
        port=Settings.PORT,
        reload=Settings.DEBUG,
        log_level=Settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()