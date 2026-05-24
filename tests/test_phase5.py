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