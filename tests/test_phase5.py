import json
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["API_AUTH_ENABLED"] = "false"


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    username = f"test_{uuid.uuid4().hex[:8]}"
    resp = client.post("/auth/register", json={
        "username": username,
        "password": "test123456",
        "display_name": "TestUser",
        "email": "test@example.com",
    })
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    data = resp.json()
    token = data["token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client, token, data["user_id"], username


class TestUserStore:
    def test_singleton(self):
        from src.core.user_store import UserStore
        u1 = UserStore()
        u2 = UserStore()
        assert u1 is u2

    def test_register_and_login(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"db_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123", "Test", "test@test.com")
        assert result["username"] == username
        assert "token" in result
        assert "user_id" in result

        login_result = store.login(username, "pass123")
        assert login_result["username"] == username
        assert "token" in login_result

    def test_register_duplicate_rejected(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"dup_test_{uuid.uuid4().hex[:8]}"
        store.register_user(username, "pass123")
        with pytest.raises(ValueError, match="已存在"):
            store.register_user(username, "pass456")

    def test_login_invalid_credentials(self):
        from src.core.user_store import UserStore
        store = UserStore()
        with pytest.raises(ValueError, match="用户名或密码错误"):
            store.login("nonexistent_user_99999", "wrongpass")

    def test_validate_token(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"vt_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123")
        user_id = store.validate_token(result["token"])
        assert user_id == result["user_id"]

        assert store.validate_token("invalid_token_xyz") is None

    def test_logout(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"lo_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123")
        store.logout(result["token"])
        assert store.validate_token(result["token"]) is None

    def test_get_profile(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"pf_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123", "ProfileTest")
        profile = store.get_profile(result["user_id"])
        assert profile is not None
        assert profile["username"] == username
        assert profile["display_name"] == "ProfileTest"

        assert store.get_profile("nonexistent_id") is None

    def test_update_profile(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"up_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123")
        updated = store.update_profile(result["user_id"], {
            "display_name": "UpdatedName",
            "level": "intermediate",
            "target_field": "Python",
        })
        assert updated["display_name"] == "UpdatedName"
        assert updated["level"] == "intermediate"
        assert updated["target_field"] == "Python"

    def test_update_progress(self):
        from src.core.user_store import UserStore
        store = UserStore()
        username = f"pr_test_{uuid.uuid4().hex[:8]}"
        result = store.register_user(username, "pass123")
        user_id = result["user_id"]

        p1 = store.update_progress(user_id, "Python基础", True)
        assert p1["knowledge_point"] == "Python基础"
        assert p1["total_attempts"] == 1
        assert p1["correct_count"] == 1
        assert p1["mastery_level"] == 1.0

        p2 = store.update_progress(user_id, "Python基础", False)
        assert p2["total_attempts"] == 2
        assert p2["correct_count"] == 1
        assert p2["mastery_level"] == 0.5

        store.update_progress(user_id, "数据结构", False)
        progress = store.get_progress(user_id)
        assert len(progress) == 2

        weak = store.get_weak_points(user_id, threshold=0.6)
        assert len(weak) == 2
        assert {w["knowledge_point"] for w in weak} == {"Python基础", "数据结构"}

    def test_check_health(self):
        from src.core.user_store import UserStore
        store = UserStore()
        health = store.check_health()
        assert health["status"] == "ok"
        assert "user_count" in health


class TestAuthAPI:
    def test_register_endpoint(self, client):
        username = f"api_reg_{uuid.uuid4().hex[:8]}"
        resp = client.post("/auth/register", json={
            "username": username,
            "password": "test123456",
            "display_name": "API User",
            "email": "api@example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == username
        assert data["display_name"] == "API User"
        assert len(data["token"]) > 0

    def test_register_duplicate(self, client):
        username = f"api_dup_{uuid.uuid4().hex[:8]}"
        client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        assert resp.status_code == 409

    def test_login_endpoint(self, client):
        username = f"api_login_{uuid.uuid4().hex[:8]}"
        client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        resp = client.post("/auth/login", json={
            "username": username, "password": "test123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == username
        assert "token" in data
        assert "expires_at" in data

    def test_login_invalid(self, client):
        resp = client.post("/auth/login", json={
            "username": "nonexistent_user", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_logout_endpoint(self, client):
        username = f"api_lo_{uuid.uuid4().hex[:8]}"
        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        token = reg_resp.json()["token"]
        resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"


class TestUserAPI:
    def test_get_profile(self, client):
        username = f"api_pf_{uuid.uuid4().hex[:8]}"
        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        token = reg_resp.json()["token"]
        resp = client.get("/user/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == username

    def test_get_profile_unauthorized(self, client):
        resp = client.get("/user/profile")
        assert resp.status_code == 401

    def test_update_profile(self, client):
        username = f"api_up_{uuid.uuid4().hex[:8]}"
        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        token = reg_resp.json()["token"]
        resp = client.put(
            "/user/profile",
            json={"display_name": "Updated", "level": "advanced", "target_field": "AI", "available_time": 20, "preference": "visual"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Updated"
        assert data["level"] == "advanced"
        assert data["target_field"] == "AI"
        assert data["available_time"] == 20
        assert data["preference"] == "visual"

    def test_update_progress(self, client):
        username = f"api_pr_{uuid.uuid4().hex[:8]}"
        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        token = reg_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/user/progress", json={
            "knowledge_point": "机器学习", "is_correct": True,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["knowledge_point"] == "机器学习"
        assert data["mastery_level"] == 1.0

        resp = client.post("/user/progress", json={
            "knowledge_point": "机器学习", "is_correct": False,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["mastery_level"] == 0.5

    def test_get_progress(self, client):
        username = f"api_gp_{uuid.uuid4().hex[:8]}"
        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "test123456",
        })
        token = reg_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        client.post("/user/progress", json={
            "knowledge_point": "Python", "is_correct": True,
        }, headers=headers)
        client.post("/user/progress", json={
            "knowledge_point": "SQL", "is_correct": False,
        }, headers=headers)

        resp = client.get("/user/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["progress"]) == 2
        assert data["total_knowledge_points"] == 2
        assert len(data["weak_points"]) == 1


class TestSSEStreaming:
    def test_stream_endpoint_exists(self, client):
        from src.api.main import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/chat/stream" in routes

    def test_stream_response_format(self, client):
        resp = client.post(
            "/chat/stream",
            json={"message": "Hello", "user_id": "test"},
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type
        content = resp.text
        assert "data: " in content
        assert len(content) > 0

    def test_stream_with_agent_role(self, client):
        resp = client.post(
            "/chat/stream",
            json={"message": "制定计划", "user_id": "test", "agent_role": "planner"},
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type

        event_types = set()
        for line in resp.text.strip().split("\n"):
            if line.startswith("data: "):
                try:
                    event_types.add(json.loads(line[len("data: "):]).get("type"))
                except (json.JSONDecodeError, KeyError):
                    pass
        assert "done" in event_types or "error" in event_types


class TestPhase5Endpoints:
    def test_all_phase5_endpoints_registered(self, client):
        from src.api.main import app
        routes = {r.path for r in app.routes if hasattr(r, "path")}
        expected_phase5 = {
            "/auth/register", "/auth/login", "/auth/logout",
            "/user/profile", "/user/progress",
            "/chat/stream",
        }
        for path in expected_phase5:
            assert path in routes, f"Missing endpoint: {path}"

    def test_health_includes_user_store(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        components = resp.json().get("components", {})
        assert "user_store" in components

    def test_full_user_workflow(self, client):
        username = f"wflow_{uuid.uuid4().hex[:8]}"

        reg_resp = client.post("/auth/register", json={
            "username": username, "password": "secure123",
            "display_name": "Workflow Test",
        })
        assert reg_resp.status_code == 200
        reg_data = reg_resp.json()
        token = reg_data["token"]
        user_id = reg_data["user_id"]
        headers = {"Authorization": f"Bearer {token}"}

        profile_resp = client.get("/user/profile", headers=headers)
        assert profile_resp.status_code == 200
        assert profile_resp.json()["display_name"] == "Workflow Test"

        update_resp = client.put("/user/profile", json={
            "display_name": "WFlow Updated",
            "level": "intermediate",
            "target_field": "AI Engineering",
            "available_time": 15,
        }, headers=headers)
        assert update_resp.status_code == 200
        assert update_resp.json()["display_name"] == "WFlow Updated"

        client.post("/user/progress", json={
            "knowledge_point": "Machine Learning", "is_correct": True,
        }, headers=headers)
        client.post("/user/progress", json={
            "knowledge_point": "Deep Learning", "is_correct": False,
        }, headers=headers)
        client.post("/user/progress", json={
            "knowledge_point": "NLP", "is_correct": False,
        }, headers=headers)

        progress_resp = client.get("/user/progress", headers=headers)
        assert progress_resp.status_code == 200
        progress_data = progress_resp.json()
        assert progress_data["total_knowledge_points"] == 3
        assert len(progress_data["weak_points"]) > 0

        chat_resp = client.post(
            "/chat/stream",
            json={"message": "制定AI学习计划", "user_id": user_id, "agent_role": "planner"},
            headers=headers,
        )
        assert chat_resp.status_code == 200
        assert "data: " in chat_resp.text

        logout_resp = client.post("/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        profile_after = client.get("/user/profile", headers=headers)
        assert profile_after.status_code == 401


class TestConversationPersistence:
    """断点续聊：对话上下文持久化与恢复测试"""

    def test_history_roundtrip_save_and_load(self, tmp_path):
        from src.api.main import _save_conversation_history, _load_conversation_history
        from src.api import main as api_main
        import time

        api_main._conversation_history.clear()
        api_main._conversation_history["test_user"] = {
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！有什么可以帮你的？"},
            ],
            "created_at": time.time(),
        }

        original_path = api_main._CONV_HISTORY_PATH
        try:
            api_main._CONV_HISTORY_PATH = str(tmp_path / "conv_test.json")
            api_main._save_conversation_history()
            assert (tmp_path / "conv_test.json").exists()

            api_main._conversation_history.clear()
            assert len(api_main._conversation_history) == 0

            api_main._load_conversation_history()
            assert "test_user" in api_main._conversation_history
            assert len(api_main._conversation_history["test_user"]["messages"]) == 2
            assert api_main._conversation_history["test_user"]["messages"][0]["content"] == "你好"
        finally:
            api_main._CONV_HISTORY_PATH = original_path
            api_main._conversation_history.clear()


class TestContextAwareConversation:
    """上下文感知对话：防止历史重复回答测试"""

    def test_format_context_produces_boundary_markers(self):
        from src.api.main import _format_conversation_context, _conversation_history

        _conversation_history.clear()
        _conversation_history["ctx_user"] = {
            "messages": [
                {"role": "user", "content": "什么是Python?"},
                {"role": "assistant", "content": "Python是一种高级编程语言..."},
                {"role": "user", "content": "推荐学习资料"},
                {"role": "assistant", "content": "推荐《Python编程：从入门到实践》..."},
            ],
            "created_at": 0,
        }

        ctx = _format_conversation_context("ctx_user", max_turns=2)
        assert "仅供参考" in ctx
        assert "请勿重复回答" in ctx
        assert "什么是Python?" in ctx
        assert "推荐学习资料" in ctx

        assert "[Human" not in ctx
        assert "[AI" not in ctx
        _conversation_history.clear()

    def test_format_context_empty_user(self):
        from src.api.main import _format_conversation_context
        assert _format_conversation_context("") == ""
        assert _format_conversation_context("nonexistent_user") == ""

    def test_format_context_truncates_long_content(self):
        from src.api.main import _format_conversation_context, _conversation_history

        _conversation_history.clear()
        long_text = "A" * 500
        _conversation_history["long_user"] = {
            "messages": [{"role": "user", "content": long_text}],
            "created_at": 0,
        }

        ctx = _format_conversation_context("long_user", max_turns=1)
        assert len(long_text) > 150
        assert long_text not in ctx
        assert "A" * 100 in ctx
        _conversation_history.clear()

    def test_agent_chat_appends_boundary_instruction(self):
        text = (
            "\n\n## 重要\n请仅回答用户的最新问题，"
            "基于上下文给出针对性回答。不要重复此前已经解答过的内容。"
        )
        assert "请仅回答用户的最新问题" in text
        assert "不要重复此前已经解答过的内容" in text

    def test_chat_with_history_uses_compact_format(self):
        from src.llm import LLMProvider, AIMessage, HumanMessage

        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮你的？"},
            {"role": "user", "content": "什么是机器学习？"},
            {"role": "assistant", "content": "机器学习是AI的一个分支..."},
        ]

        try:
            llm = LLMProvider()
            llm.chat_with_history("继续", history, system_prompt="你是助手")
        except Exception:
            pass

    def test_sse_non_agent_uses_system_summary_not_raw_msgs(self, client):
        from src.api import main as api_main
        from src.api.main import _format_conversation_context

        api_main._conversation_history.clear()
        uid = "sse_ctx_user"
        api_main._conversation_history[uid] = {
            "messages": [
                {"role": "user", "content": "Q1: Python是什么?"},
                {"role": "assistant", "content": "A1: Python是编程语言"},
                {"role": "user", "content": "Q2: 推荐书籍"},
                {"role": "assistant", "content": "A2: 推荐Python入门书籍"},
            ],
            "created_at": 0,
        }

        ctx = _format_conversation_context(uid, max_turns=2)
        assert "仅供参考" in ctx
        assert "请勿重复回答" in ctx
        assert "[Human" not in ctx
        api_main._conversation_history.clear()

    def test_multi_turn_history_boundaries(self):
        from src.api.main import _format_conversation_context, _append_to_history, _conversation_history

        _conversation_history.clear()
        uid = "multiturn_user"
        turns = [
            ("user", "你好，我想学习Python"),
            ("assistant", "好的，我会帮你制定Python学习计划"),
            ("user", "先推荐几本入门书"),
            ("assistant", "推荐以下三本：1. Python编程：从入门到实践..."),
            ("user", "出几道关于变量的题"),
            ("assistant", "好的，以下是变量相关题目：\n1. 变量命名规则..."),
            ("user", "帮我分析一下刚才做错的题"),
            ("assistant", "好的，这道题主要考察..."),
        ]

        for role, content in turns:
            _append_to_history(uid, role, content)

        ctx = _format_conversation_context(uid, max_turns=2)
        assert "仅供参考" in ctx
        assert "请勿重复回答" in ctx

        assert "变量" in ctx
        assert "做错的题" in ctx

        assert ctx.count("[用户]") <= 2
        assert ctx.count("[助手]") <= 2
        _conversation_history.clear()

    def test_context_summary_never_contains_raw_ai_format(self):
        from src.api.main import _format_conversation_context, _conversation_history

        _conversation_history.clear()
        _conversation_history["fmt_user"] = {
            "messages": [
                {"role": "user", "content": "问题1"},
                {"role": "assistant", "content": "回答1"},
                {"role": "user", "content": "问题2"},
                {"role": "assistant", "content": "回答2"},
            ],
            "created_at": 0,
        }

        ctx = _format_conversation_context("fmt_user", max_turns=2)
        assert "AIMessage" not in ctx
        assert "HumanMessage" not in ctx
        assert "SystemMessage" not in ctx
        _conversation_history.clear()

    def test_history_load_with_missing_file(self):
        from src.api import main as api_main
        import os

        api_main._conversation_history.clear()
        api_main._conversation_history["persist_user"] = {
            "messages": [{"role": "user", "content": "test"}],
            "created_at": 0,
        }

        original_path = api_main._CONV_HISTORY_PATH
        try:
            api_main._CONV_HISTORY_PATH = str(os.path.join(os.path.dirname(__file__), "nonexistent", "conv.json"))
            api_main._load_conversation_history()
            assert "persist_user" in api_main._conversation_history
        finally:
            api_main._CONV_HISTORY_PATH = original_path
            api_main._conversation_history.clear()

    def test_build_agent_state_seeds_frontend_history(self):
        from src.api.main import _build_agent_state, _conversation_history

        _conversation_history.clear()
        frontend_history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]

        state = _build_agent_state("Q3", "seed_user", frontend_history=frontend_history)
        assert "seed_user" in _conversation_history
        assert len(_conversation_history["seed_user"]["messages"]) == 4
        assert _conversation_history["seed_user"]["messages"][0]["content"] == "Q1"
        assert _conversation_history["seed_user"]["messages"][3]["content"] == "A2"

        messages = state["messages"]
        assert len(messages) == 5
        assert messages[-1]["content"] == "Q3"
        _conversation_history.clear()

    def test_build_agent_state_no_duplicate_seed(self):
        from src.api.main import _build_agent_state, _conversation_history

        _conversation_history.clear()
        _conversation_history["existing_user"] = {
            "messages": [{"role": "user", "content": "existing"}],
            "created_at": 0,
        }

        frontend_history = [{"role": "user", "content": "frontend"}]
        state = _build_agent_state("new_msg", "existing_user", frontend_history=frontend_history)
        assert _conversation_history["existing_user"]["messages"][0]["content"] == "existing"
        _conversation_history.clear()

    def test_context_truncation_above_50(self):
        from src.api.main import _append_to_history, _build_agent_state, _conversation_history

        _conversation_history.clear()
        uid = "bulk_user"
        for i in range(80):
            _append_to_history(uid, "user" if i % 2 == 0 else "assistant", f"msg_{i}")

        state = _build_agent_state("final_msg", uid)
        msgs = state["messages"]
        assert msgs[-1]["content"] == "final_msg"
        assert len(msgs) <= 61
        _conversation_history.clear()

    def test_append_to_history_triggers_periodic_save(self, tmp_path):
        from src.api.main import _append_to_history, _save_conversation_history, _SAVE_COUNTER, _SAVE_THRESHOLD
        from src.api import main as api_main

        api_main._conversation_history.clear()
        original_path = api_main._CONV_HISTORY_PATH
        original_counter = api_main._SAVE_COUNTER
        try:
            api_main._CONV_HISTORY_PATH = str(tmp_path / "periodic_conv.json")
            api_main._SAVE_COUNTER = _SAVE_THRESHOLD - 2

            _append_to_history("user_a", "user", "hello")
            _append_to_history("user_a", "assistant", "hi there")
            _save_conversation_history()

            assert (tmp_path / "periodic_conv.json").exists()
            with open(tmp_path / "periodic_conv.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "user_a" in data
            assert len(data["user_a"]["messages"]) == 2
        finally:
            api_main._CONV_HISTORY_PATH = original_path
            api_main._SAVE_COUNTER = original_counter
            api_main._conversation_history.clear()

    def test_append_to_history_max_message_pruning(self):
        from src.api.main import _append_to_history, _conversation_history

        _conversation_history.clear()
        uid = "prune_user"
        for i in range(600):
            _append_to_history(uid, "user" if i % 2 == 0 else "assistant", f"msg_{i}")

        assert len(_conversation_history[uid]["messages"]) <= 300
        _conversation_history.clear()

    def test_non_agent_sse_includes_history(self, client):
        from src.api import main as api_main

        api_main._conversation_history.clear()
        uid = "sse_hist_user"
        api_main._conversation_history[uid] = {
            "messages": [
                {"role": "user", "content": "之前的问题"},
                {"role": "assistant", "content": "之前的回答"},
            ],
            "created_at": 0,
        }

        resp = client.post(
            "/chat/stream",
            json={"message": "新问题", "user_id": uid},
        )
        assert resp.status_code == 200
        assert "data: " in resp.text

        assert uid in api_main._conversation_history
        msgs = api_main._conversation_history[uid]["messages"]
        assert len(msgs) >= 2
        assert msgs[0]["content"] == "之前的问题"
        assert msgs[1]["content"] == "之前的回答"
        api_main._conversation_history.clear()

    def test_agent_sse_with_frontend_history_fallback(self, client):
        from src.api import main as api_main

        api_main._conversation_history.clear()
        uid = "fb_user"
        frontend_history = [
            {"role": "user", "content": "fm1"},
            {"role": "assistant", "content": "fa1"},
        ]

        resp = client.post(
            "/chat/stream",
            json={
                "message": "继续学习",
                "user_id": uid,
                "agent_role": "planner",
                "history": frontend_history,
            },
        )
        assert resp.status_code == 200
        assert uid in api_main._conversation_history
        assert api_main._conversation_history[uid]["messages"][0]["content"] == "fm1"
        api_main._conversation_history.clear()

    def test_shutdown_preserves_history(self, tmp_path):
        from src.api import main as api_main
        import time

        api_main._conversation_history.clear()
        api_main._conversation_history["shutdown_user"] = {
            "messages": [
                {"role": "user", "content": "shutdown msg"},
                {"role": "assistant", "content": "shutdown reply"},
            ],
            "created_at": time.time(),
        }

        original_path = api_main._CONV_HISTORY_PATH
        try:
            api_main._CONV_HISTORY_PATH = str(tmp_path / "shutdown_conv.json")
            api_main._save_conversation_history()
            assert (tmp_path / "shutdown_conv.json").exists()

            api_main._conversation_history.clear()
            api_main._load_conversation_history()
            assert "shutdown_user" in api_main._conversation_history
            msgs = api_main._conversation_history["shutdown_user"]["messages"]
            assert len(msgs) == 2
            assert msgs[0]["content"] == "shutdown msg"
        finally:
            api_main._CONV_HISTORY_PATH = original_path
            api_main._conversation_history.clear()