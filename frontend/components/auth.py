"""
登录/注册认证组件
负责用户认证页面的完整交互流程，包括表单校验、API调用和状态更新。
"""

import streamlit as st

from api_client import login as api_login
from api_client import register as api_register
from api_client import ApiError
from components.common import display_error, display_success, display_warning

LOGIN_USER_KEY = "login_username"
LOGIN_PASS_KEY = "login_password"
REG_USER_KEY = "reg_username"
REG_DISPLAY_KEY = "reg_display_name"
REG_EMAIL_KEY = "reg_email"
REG_PASS_KEY = "reg_password"
REG_PASS2_KEY = "reg_password_confirm"


def _apply_login_state(auth_data: dict):
    """将登录/注册返回的数据写入 session_state。"""
    st.session_state.logged_in = True
    st.session_state.token = auth_data["token"]
    st.session_state.user_id = auth_data["user_id"]
    st.session_state.username = auth_data["username"]
    st.session_state.display_name = auth_data.get("display_name", auth_data["username"])
    st.session_state.profile = auth_data


def _validate_login_form(username: str, password: str) -> bool:
    """校验登录表单输入。"""
    if not username or not password:
        display_warning("请输入用户名和密码")
        return False
    return True


def _handle_login(username: str, password: str):
    """执行登录API调用并更新状态。"""
    if not _validate_login_form(username, password):
        return
    try:
        auth_data = api_login(username, password)
        _apply_login_state(auth_data)
        display_success("登录成功！")
        st.rerun()
    except ApiError as e:
        display_error(str(e))


def _validate_register_form(
    username: str,
    password: str,
    password_confirm: str,
) -> bool:
    """校验注册表单输入，返回True表示通过。"""
    if not username or not password:
        display_warning("用户名和密码为必填项")
        return False
    if len(username) < 3:
        display_warning("用户名至少3个字符")
        return False
    if len(password) < 6:
        display_warning("密码至少6个字符")
        return False
    if password != password_confirm:
        display_warning("两次密码不一致")
        return False
    return True


def _handle_register(
    username: str,
    password: str,
    display_name: str,
    email: str,
):
    """执行注册API调用并更新状态。"""
    try:
        auth_data = api_register(
            username=username,
            password=password,
            display_name=display_name,
            email=email,
        )
        _apply_login_state(auth_data)
        display_success("注册成功！")
        st.rerun()
    except ApiError as e:
        display_error(str(e))


def render_login_page():
    """渲染登录/注册页面。

    使用居中的卡片布局，包含登录和注册两个Tab。
    登录成功后自动跳转到主界面。
    """
    col_center = st.columns([1, 2, 1])[1]
    with col_center:
        st.markdown('<div class="login-container" role="region" aria-label="登录区域">', unsafe_allow_html=True)
        st.markdown("## 学习辅助")

        tab_login, tab_register = st.tabs(["登录", "注册"])

        with tab_login:
            login_user = st.text_input("用户名", key=LOGIN_USER_KEY)
            login_pass = st.text_input("密码", type="password", key=LOGIN_PASS_KEY)
            if st.button("🔑 登录", use_container_width=True, key="btn_login"):
                _handle_login(login_user, login_pass)

        with tab_register:
            reg_user = st.text_input("用户名", key=REG_USER_KEY)
            reg_display = st.text_input("昵称（可选）", key=REG_DISPLAY_KEY)
            reg_email = st.text_input("邮箱（可选）", key=REG_EMAIL_KEY)
            reg_pass = st.text_input("密码", type="password", key=REG_PASS_KEY)
            reg_pass2 = st.text_input("确认密码", type="password", key=REG_PASS2_KEY)
            if st.button("📝 注册", use_container_width=True, key="btn_register"):
                if _validate_register_form(reg_user, reg_pass, reg_pass2):
                    _handle_register(reg_user, reg_pass, reg_display, reg_email)

        st.markdown("</div>", unsafe_allow_html=True)