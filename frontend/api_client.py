"""
API 客户端模块
统一封装所有后端 API 调用，包含认证头、超时设置、错误处理和重试逻辑。
"""

from typing import Any, Optional

import requests

from config import (
    API_BASE,
    REQUEST_TIMEOUT_DEFAULT,
    REQUEST_TIMEOUT_STREAM,
)


class ApiError(Exception):
    """API 调用异常。"""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


def build_headers() -> dict[str, str]:
    """构建请求头，自动附加 Bearer token。"""
    import streamlit as st
    headers = {"Content-Type": "application/json"}
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    return headers


def _safe_request(
    method: str,
    path: str,
    json_data: Optional[dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT_DEFAULT,
    stream: bool = False,
) -> requests.Response:
    """统一的HTTP请求封装，自动处理连接错误。"""
    url = f"{API_BASE}{path}"
    try:
        return requests.request(
            method=method,
            url=url,
            json=json_data,
            headers=build_headers(),
            timeout=timeout,
            stream=stream,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError("无法连接到后端 API，请确保服务已启动", status_code=0)
    except requests.exceptions.Timeout:
        raise ApiError("请求超时，请稍后重试", status_code=0)


def _safe_json(resp: requests.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except (requests.exceptions.JSONDecodeError, ValueError):
        if resp.text and resp.text.strip():
            return {"detail": resp.text.strip()[:200]}
        return {"detail": f"服务返回异常 (HTTP {resp.status_code})"}


def login(username: str, password: str) -> dict[str, Any]:
    """用户登录，成功返回包含 token/user_id 的字典。"""
    resp = _safe_request("POST", "/auth/login", json_data={"username": username, "password": password})
    if resp.status_code == 200:
        return _safe_json(resp)
    if resp.status_code == 401:
        raise ApiError("用户名或密码错误", status_code=401)
    data = _safe_json(resp)
    detail = data.get("detail", "登录失败")
    raise ApiError(detail, status_code=resp.status_code)


def register(
    username: str, password: str, display_name: str = "", email: str = ""
) -> dict[str, Any]:
    """用户注册，成功返回包含 token/user_id 的字典。"""
    resp = _safe_request(
        "POST",
        "/auth/register",
        json_data={
            "username": username,
            "password": password,
            "display_name": display_name,
            "email": email,
        },
    )
    if resp.status_code == 200:
        return _safe_json(resp)
    if resp.status_code == 409:
        raise ApiError("用户名已存在", status_code=409)
    data = _safe_json(resp)
    detail = data.get("detail", "注册失败")
    raise ApiError(detail, status_code=resp.status_code)


def logout():
    """退出登录（忽略错误，确保前端状态清理不被阻塞）。"""
    try:
        _safe_request("POST", "/auth/logout", timeout=5)
    except ApiError:
        pass


def get_profile() -> dict[str, Any]:
    """获取用户个人信息。"""
    resp = _safe_request("GET", "/user/profile")
    if resp.status_code == 200:
        return _safe_json(resp)
    data = _safe_json(resp)
    detail = data.get("detail", "获取信息失败")
    raise ApiError(detail, status_code=resp.status_code)


def update_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    """更新用户个人信息。"""
    resp = _safe_request("PUT", "/user/profile", json_data=profile_data)
    if resp.status_code == 200:
        return _safe_json(resp)
    raise ApiError("保存失败", status_code=resp.status_code)


def change_password(old_password: str, new_password: str) -> dict[str, Any]:
    resp = _safe_request("PUT", "/user/profile/password", json_data={
        "old_password": old_password,
        "new_password": new_password,
    })
    if resp.status_code == 200:
        return _safe_json(resp)
    data = _safe_json(resp)
    detail = data.get("detail", "密码修改失败")
    raise ApiError(detail, status_code=resp.status_code)


def check_health() -> dict[str, Any]:
    """健康检查。"""
    resp = _safe_request("GET", "/health", timeout=5)
    if resp.status_code == 200:
        return _safe_json(resp)
    raise ApiError(f"服务异常 ({resp.status_code})", status_code=resp.status_code)


def stream_chat_request(payload: dict[str, Any]):
    """发起SSE流式对话请求，返回 Response 对象供迭代。"""
    return _safe_request(
        "POST",
        "/chat/stream",
        json_data=payload,
        timeout=REQUEST_TIMEOUT_STREAM,
        stream=True,
    )