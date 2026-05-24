"""
前端交互层单元测试

覆盖模块: config / api_client / components.common / components.auth / components.chat / components.sidebar
测试框架: pytest + unittest.mock (支持无 Streamlit 环境运行)

运行方式:
    cd c:/Users/asus/Desktop/agent
    python -m pytest tests/test_frontend.py -v
"""

import json
import os
import sys
import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "frontend"))

_HAS_STREAMLIT = False
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _mock_session = MagicMock()
    _mock_session_state = MagicMock()
    _mock_session.session_state = _mock_session_state
    sys.modules["streamlit"] = MagicMock()
    sys.modules["streamlit"].session_state = _mock_session_state


# ===================================================================
# config.py 测试
# ===================================================================

class TestConfig:
    """测试配置模块的常量定义和工具函数。"""

    def test_constants_defined(self):
        from config import (
            PAGE_TITLE, PAGE_ICON, PAGE_LAYOUT,
            REQUEST_TIMEOUT_DEFAULT, REQUEST_TIMEOUT_STREAM,
            SSE_POLL_INTERVAL, SSE_TIMEOUT_SECONDS,
        )
        assert PAGE_TITLE == "学习辅助系统"
        assert PAGE_ICON == "📚"
        assert PAGE_LAYOUT == "wide"
        assert REQUEST_TIMEOUT_DEFAULT == 10
        assert REQUEST_TIMEOUT_STREAM == 120
        assert SSE_POLL_INTERVAL == 0.05
        assert SSE_TIMEOUT_SECONDS == 130

    def test_agent_labels_complete(self):
        from config import AGENT_ROLE_LABELS
        expected_keys = {"auto", "planner", "expert", "partner", "quizzer", "reviewer", "examiner"}
        assert set(AGENT_ROLE_LABELS.keys()) == expected_keys

    def test_level_options(self):
        from config import LEVEL_OPTIONS, LEVEL_LABELS
        assert len(LEVEL_OPTIONS) == 4
        assert LEVEL_OPTIONS[0] == "beginner"
        assert LEVEL_LABELS["beginner"] == "入门"
        assert LEVEL_LABELS["expert"] == "专家"

    def test_preference_options(self):
        from config import PREFERENCE_OPTIONS, PREFERENCE_LABELS
        assert len(PREFERENCE_OPTIONS) == 5
        assert "comprehensive" in PREFERENCE_OPTIONS

    def test_default_profile_structure(self):
        from config import DEFAULT_PROFILE
        assert "display_name" in DEFAULT_PROFILE
        assert "level" in DEFAULT_PROFILE
        assert DEFAULT_PROFILE["available_time"] == 10
        assert DEFAULT_PROFILE["preference"] == "comprehensive"

    def test_session_state_defaults(self):
        from config import SESSION_STATE_DEFAULTS
        assert "messages" in SESSION_STATE_DEFAULTS
        assert SESSION_STATE_DEFAULTS["logged_in"] is False
        assert SESSION_STATE_DEFAULTS["messages"] == []

    def test_global_css_non_empty(self):
        from config import GLOBAL_CSS
        assert ".login-container" in GLOBAL_CSS
        assert ".empty-state" in GLOBAL_CSS
        assert ".stApp" in GLOBAL_CSS

    def test_empty_chat_message(self):
        from config import MESSAGE_EMPTY_CHAT
        assert "欢迎使用学习辅助系统" in MESSAGE_EMPTY_CHAT
        assert "制定学习计划" in MESSAGE_EMPTY_CHAT

    def test_safe_index_found(self):
        from config import _safe_index
        assert _safe_index(["a", "b", "c"], "b") == 1

    def test_safe_index_not_found(self):
        from config import _safe_index
        assert _safe_index(["a", "b"], "z") == 0

    def test_safe_index_empty_list(self):
        from config import _safe_index
        assert _safe_index([], "x") == 0


# ===================================================================
# api_client.py 测试
# ===================================================================

class TestApiClient:
    """测试 API 客户端模块的函数逻辑。"""

    def test_api_error_creation(self):
        from api_client import ApiError
        err = ApiError("测试错误", status_code=500)
        assert str(err) == "测试错误"
        assert err.status_code == 500

    def test_api_error_default_code(self):
        from api_client import ApiError
        err = ApiError("连接失败")
        assert err.status_code == 0

    @patch("api_client.requests.request")
    def test_safe_request_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_resp

        from api_client import _safe_request
        resp = _safe_request("GET", "/health")
        assert resp.status_code == 200

    @patch("api_client.requests.request")
    def test_safe_request_connection_error(self, mock_request):
        import requests as req_lib
        mock_request.side_effect = req_lib.exceptions.ConnectionError("refused")

        from api_client import _safe_request, ApiError
        with pytest.raises(ApiError, match="无法连接到后端"):
            _safe_request("GET", "/health")

    @patch("api_client.requests.request")
    def test_safe_request_timeout(self, mock_request):
        import requests as req_lib
        mock_request.side_effect = req_lib.exceptions.Timeout("timeout")

        from api_client import _safe_request, ApiError
        with pytest.raises(ApiError, match="请求超时"):
            _safe_request("GET", "/health")

    @patch("api_client._safe_request")
    def test_login_200(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "t1", "user_id": "u1", "username": "test"}
        mock_safe.return_value = mock_resp

        from api_client import login
        result = login("user", "pass")
        assert result["token"] == "t1"
        assert result["user_id"] == "u1"

    @patch("api_client._safe_request")
    def test_login_401(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "wrong"}
        mock_safe.return_value = mock_resp

        from api_client import login, ApiError
        with pytest.raises(ApiError, match="用户名或密码错误"):
            login("user", "pass")

    @patch("api_client._safe_request")
    def test_register_409(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_safe.return_value = mock_resp

        from api_client import register, ApiError
        with pytest.raises(ApiError, match="用户名已存在"):
            register("user", "pass")

    @patch("api_client._safe_request")
    def test_register_200(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "t1", "user_id": "u1", "username": "new"}
        mock_safe.return_value = mock_resp

        from api_client import register
        result = register("new_user", "pass123", "nick", "e@mail.com")
        assert result["username"] == "new"

    @patch("api_client._safe_request")
    def test_get_profile(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"username": "test", "level": "beginner"}
        mock_safe.return_value = mock_resp

        from api_client import get_profile
        result = get_profile()
        assert result["level"] == "beginner"

    @patch("api_client._safe_request")
    def test_get_profile_failure(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "not found"}
        mock_safe.return_value = mock_resp

        from api_client import get_profile, ApiError
        with pytest.raises(ApiError):
            get_profile()

    @patch("api_client._safe_request")
    def test_update_profile(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"display_name": "updated"}
        mock_safe.return_value = mock_resp

        from api_client import update_profile
        result = update_profile({"display_name": "updated"})
        assert result["display_name"] == "updated"

    @patch("api_client._safe_request")
    def test_check_health(self, mock_safe):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_safe.return_value = mock_resp

        from api_client import check_health
        result = check_health()
        assert result["status"] == "ok"

    @patch("api_client._safe_request")
    def test_logout_no_error(self, mock_safe):
        from api_client import ApiError
        mock_safe.side_effect = ApiError("ignored", status_code=0)
        from api_client import logout
        logout()

    @patch("api_client._safe_request")
    def test_stream_chat_request(self, mock_safe):
        mock_resp = MagicMock()
        mock_safe.return_value = mock_resp

        from api_client import stream_chat_request
        resp = stream_chat_request({"message": "hi"})
        assert resp is mock_resp


# ===================================================================
# components/chat.py 测试
# ===================================================================

class TestChatParsing:
    """测试 SSE 数据解析和消息处理逻辑。"""

    def test_parse_sse_line_valid_start(self):
        from components.chat import _parse_sse_line
        data = _parse_sse_line('data: {"type":"start","agent_role":"planner"}')
        assert data == {"type": "start", "agent_role": "planner"}

    def test_parse_sse_line_valid_chunk(self):
        from components.chat import _parse_sse_line
        data = _parse_sse_line('data: {"type":"chunk","content":"Hello"}')
        assert data["content"] == "Hello"

    def test_parse_sse_line_no_prefix(self):
        from components.chat import _parse_sse_line
        assert _parse_sse_line('{"type":"chunk"}') is None

    def test_parse_sse_line_empty(self):
        from components.chat import _parse_sse_line
        assert _parse_sse_line("") is None

    def test_parse_sse_line_invalid_json(self):
        from components.chat import _parse_sse_line
        assert _parse_sse_line("data: {invalid}") is None

    def test_parse_sse_line_done(self):
        from components.chat import _parse_sse_line
        data = _parse_sse_line('data: {"type":"done"}')
        assert data["type"] == "done"

    def test_parse_sse_line_error(self):
        from components.chat import _parse_sse_line
        data = _parse_sse_line('data: {"type":"error","content":"fail"}')
        assert data["type"] == "error"
        assert data["content"] == "fail"

    @patch("components.chat.requests.Response")
    def test_iter_sse_lines(self, mock_response_class):
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type":"chunk","content":"a"}',
            'data: {"type":"chunk","content":"b"}',
            'data: {"type":"done"}',
        ]
        from components.chat import _iter_sse_lines
        lines = list(_iter_sse_lines(mock_resp))
        assert len(lines) == 3

    @patch("components.chat.requests.Response")
    def test_iter_sse_lines_connection_error(self, mock_response_class):
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.iter_lines.side_effect = req_lib.exceptions.ConnectionError("broken")
        from components.chat import _iter_sse_lines
        lines = list(_iter_sse_lines(mock_resp))
        assert lines == []

    @patch("components.chat.requests.Response")
    def test_iter_sse_lines_filters_empty(self, mock_response_class):
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = ["", 'data: {"type":"chunk","content":"x"}']
        from components.chat import _iter_sse_lines
        lines = list(_iter_sse_lines(mock_resp))
        assert len(lines) == 1


# ===================================================================
# components/auth.py 测试
# ===================================================================

class TestAuthValidation:
    """测试认证表单校验逻辑。"""

    def test_validate_login_empty(self):
        from components.auth import _validate_login_form
        assert _validate_login_form("", "") is False
        assert _validate_login_form("user", "") is False

    def test_validate_login_ok(self):
        from components.auth import _validate_login_form
        assert _validate_login_form("user", "pass") is True

    def test_validate_register_empty(self):
        from components.auth import _validate_register_form
        assert _validate_register_form("", "", "") is False

    def test_validate_register_short_username(self):
        from components.auth import _validate_register_form
        assert _validate_register_form("ab", "123456", "123456") is False

    def test_validate_register_short_password(self):
        from components.auth import _validate_register_form
        assert _validate_register_form("validuser", "12345", "12345") is False

    def test_validate_register_mismatch(self):
        from components.auth import _validate_register_form
        assert _validate_register_form("validuser", "123456", "654321") is False

    def test_validate_register_ok(self):
        from components.auth import _validate_register_form
        assert _validate_register_form("validuser", "123456", "123456") is True

    def test_apply_login_state(self):
        from components.auth import _apply_login_state
        import streamlit as st
        _apply_login_state({
            "token": "t1",
            "user_id": "u1",
            "username": "alice",
            "display_name": "Alice",
        })
        assert st.session_state.logged_in is True
        assert st.session_state.token == "t1"
        assert st.session_state.user_id == "u1"
        assert st.session_state.username == "alice"
        assert st.session_state.display_name == "Alice"


# ===================================================================
# components/sidebar.py 测试
# ===================================================================

class TestSidebarHelpers:
    """测试侧边栏辅助函数。"""

    def test_resolve_index_found(self):
        from components.sidebar import _resolve_index
        assert _resolve_index(["a", "b", "c"], "b") == 1

    def test_resolve_index_not_found(self):
        from components.sidebar import _resolve_index
        assert _resolve_index(["a", "b"], "z") == 0

    def test_resolve_index_empty(self):
        from components.sidebar import _resolve_index
        assert _resolve_index([], "x") == 0


# ===================================================================
# 集成测试: SSE流式会话模拟
# ===================================================================

class TestSSEStreamSimulation:
    """模拟SSE流式响应处理全流程。"""

    @patch("components.chat.stream_chat_request")
    def test_stream_chat_success_path(self, mock_stream):
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type":"start","agent_role":"planner"}',
            'data: {"type":"chunk","content":"计划"}',
            'data: {"type":"chunk","content":"已生成"}',
            'data: {"type":"done"}',
        ]
        mock_stream.return_value = mock_resp

        from components.chat import stream_chat
        import streamlit as st

        st.session_state.messages = []
        st.session_state.user_id = "test_user"

        with patch("streamlit.empty") as mock_empty:
            mock_placeholder = MagicMock()
            mock_empty.return_value = mock_placeholder
            with patch("streamlit.error"), patch("streamlit.warning"):
                stream_chat("帮我制定计划", agent_role="planner", user_id="test_user")

        assert len(st.session_state.messages) == 1
        assert "计划" in st.session_state.messages[0]["content"]
        assert st.session_state.messages[0]["agent"] == "planner"

    @patch("components.chat.stream_chat_request")
    def test_stream_chat_error_path(self, mock_stream):
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type":"start","agent_role":"partner"}',
            'data: {"type":"error","content":"LLM调用失败"}',
        ]
        mock_stream.return_value = mock_resp

        from components.chat import stream_chat
        import streamlit as st

        st.session_state.messages = []
        st.session_state.user_id = "test_user"

        with patch("streamlit.empty") as mock_empty:
            mock_placeholder = MagicMock()
            mock_empty.return_value = mock_placeholder
            with patch("streamlit.error"), patch("streamlit.warning"):
                stream_chat("test", agent_role="partner", user_id="test_user")

        assert len(st.session_state.messages) >= 1

    @patch("components.chat.stream_chat_request")
    def test_stream_chat_connection_error(self, mock_stream):
        from api_client import ApiError
        mock_stream.side_effect = ApiError("无法连接到后端 API", status_code=0)

        from components.chat import stream_chat
        import streamlit as st

        st.session_state.messages = []
        st.session_state.user_id = "test_user"

        with patch("streamlit.empty") as mock_empty:
            mock_placeholder = MagicMock()
            mock_empty.return_value = mock_placeholder
            with patch("streamlit.error"), patch("streamlit.warning"):
                stream_chat("test", user_id="test_user")

        assert len(st.session_state.messages) == 1
        assert "无法连接" in st.session_state.messages[0]["content"]

    def test_append_user_message(self):
        from components.chat import append_user_message
        import streamlit as st
        st.session_state.messages = []
        append_user_message("hello")
        assert len(st.session_state.messages) == 1
        assert st.session_state.messages[0]["role"] == "user"
        assert st.session_state.messages[0]["content"] == "hello"
        assert st.session_state.messages[0]["avatar"] == "👤"

    def test_append_assistant_message(self):
        from components.chat import _append_assistant_message
        import streamlit as st
        st.session_state.messages = []
        _append_assistant_message("回复内容", "planner")
        assert len(st.session_state.messages) == 1
        assert st.session_state.messages[0]["role"] == "assistant"
        assert st.session_state.messages[0]["agent"] == "planner"


# ===================================================================
# 消息渲染逻辑测试
# ===================================================================

class TestMessageRendering:
    """测试消息渲染相关的工具函数。"""

    def test_message_agent_label_format(self):
        from config import MESSAGE_AGENT_LABEL
        label = MESSAGE_AGENT_LABEL.format(agent="planner")
        assert "planner" in label
        assert "处理" in label

    def test_message_timeout_text(self):
        from config import MESSAGE_TIMEOUT
        assert "超时" in MESSAGE_TIMEOUT
        assert len(MESSAGE_TIMEOUT) > 5

    def test_message_error_prefix(self):
        from config import MESSAGE_ERROR_PREFIX
        assert MESSAGE_ERROR_PREFIX == "❌"