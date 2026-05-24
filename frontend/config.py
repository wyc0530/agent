"""
前端全局配置模块
集中管理所有常量、样式、页面设置和Agent角色定义。
"""

import os
import streamlit as st

_API_BASE: str = ""
_request_timeout_default: int = 10


def get_api_base() -> str:
    """获取API基础URL，优先从Streamlit secrets读取，其次环境变量。"""
    try:
        import streamlit as st
        return st.secrets.get("API_BASE", os.environ.get("API_BASE", "http://localhost:8000"))
    except ImportError:
        return os.environ.get("API_BASE", "http://localhost:8000")


API_BASE = get_api_base()

PAGE_TITLE = "学习辅助系统"
PAGE_ICON = "📚"
PAGE_LAYOUT = "wide"

REQUEST_TIMEOUT_DEFAULT = 10
REQUEST_TIMEOUT_STREAM = 120
SSE_POLL_INTERVAL = 0.05
SSE_TIMEOUT_SECONDS = 130

AGENT_ROLE_LABELS: dict[str, str] = {
    "auto": "自动识别 (推荐)",
    "planner": "学习规划师",
    "expert": "学习专家",
    "partner": "学习伙伴",
    "quizzer": "出题官",
    "reviewer": "复习助理",
    "examiner": "考试指导",
}

LEVEL_OPTIONS = ["beginner", "intermediate", "advanced", "expert"]
LEVEL_LABELS = {
    "beginner": "入门",
    "intermediate": "中级",
    "advanced": "高级",
    "expert": "专家",
}

PREFERENCE_OPTIONS = ["comprehensive", "visual", "auditory", "reading", "practice"]
PREFERENCE_LABELS = {
    "comprehensive": "综合学习",
    "visual": "视觉学习",
    "auditory": "听觉学习",
    "reading": "文本阅读",
    "practice": "动手实践",
}

DEFAULT_PROFILE = {
    "display_name": "",
    "email": "",
    "level": "beginner",
    "target_field": "",
    "available_time": 10,
    "preference": "comprehensive",
}

SESSION_STATE_DEFAULTS = {
    "messages": [],
    "user_id": "",
    "token": "",
    "current_agent": None,
    "logged_in": False,
    "username": "",
    "display_name": "",
    "profile": {},
}

GLOBAL_CSS = """
<style>
    .stApp { max-width: 1400px; margin: 0 auto; }
    .login-container {
        max-width: 420px;
        margin: 60px auto;
        padding: 2rem;
        border-radius: 12px;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }
    .login-container h2 {
        text-align: center;
        margin-bottom: 0.25rem;
    }
    .login-container p {
        text-align: center;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .chat-container {
        height: calc(100vh - 300px);
        overflow-y: auto;
    }
    .sidebar-user-info {
        padding: 8px 0;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 12px;
    }
    .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #9e9e9e;
    }
    .empty-state .icon {
        font-size: 48px;
        margin-bottom: 12px;
    }
    @media (max-width: 768px) {
        .stApp { max-width: 100%; padding: 0 8px; }
        .login-container { max-width: 100%; margin: 20px auto; padding: 1.25rem; }
        .empty-state { padding: 24px 12px; }
        .empty-state .icon { font-size: 36px; }
        .stMainBlockContainer { padding: 1rem 0.5rem; }
    }
</style>
"""

MESSAGE_EMPTY_CHAT = """
### 👋 欢迎使用学习辅助系统

我是你的 AI 学习助手，可以帮你：

- 📋 **制定学习计划** — 输入"帮我制定一个学习计划"
- 📖 **推荐学习资料** — 输入"推荐Python入门资料"
- ❓ **解答学习问题** — 直接输入你的问题
- 📝 **生成练习题目** — 输入"出几道算法题"
- 🔄 **复习错题** — 输入"帮我分析错题"
- 🎯 **备考指导** — 输入"如何准备面试"

在左侧边栏可以选择指定的 Agent 来获得更专业的帮助。试试输入你的第一个问题吧！
"""

MESSAGE_AGENT_LABEL = "处理: {agent}"
MESSAGE_ERROR_PREFIX = "❌"
MESSAGE_TIMEOUT = "⚠️ 服务器响应超时，请稍后重试。"
MESSAGE_BACKEND_DOWN = "无法连接到后端 API，请确保服务已启动"
MESSAGE_LOGOUT_CONFIRM = "确定要退出登录吗？"


def init_session_state():
    """初始化所有 session_state 变量，仅在首次访问时设置默认值。"""
    for key, default in SESSION_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _safe_index(options: list[str], value: str) -> int:
    """安全获取列表索引，value不在列表中时返回0。"""
    try:
        return options.index(value)
    except ValueError:
        return 0