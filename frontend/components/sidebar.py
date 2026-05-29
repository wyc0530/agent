"""
侧边栏组件模块
包含个人设置、Agent选择器、测验生成器、快捷操作等侧边栏交互功能。
"""

import streamlit as st

from api_client import (
    get_profile,
    update_profile,
    change_password,
    logout as api_logout,
    ApiError,
)
from config import (
    AGENT_ROLE_LABELS,
    LEVEL_OPTIONS,
    PREFERENCE_OPTIONS,
    MESSAGE_LOGOUT_CONFIRM,
)
from components.common import (
    display_error,
    display_success,
    display_warning,
    show_confirmation_dialog,
)
from components.chat import trigger_quick_chat

LOGOUT_CONFIRM_KEY = "logout_confirm"


def _resolve_index(options: list[str], value: str) -> int:
    """安全获取列表索引，value不在列表中时返回0。"""
    try:
        return options.index(value)
    except ValueError:
        return 0


def render_user_info():
    """渲染侧边栏顶部用户信息区域。"""
    display_name = st.session_state.get("display_name") or st.session_state.get("username", "")
    username = st.session_state.get("username", "")
    st.sidebar.title(f"{display_name}")
    st.sidebar.markdown(f"*{username}*")


def render_password_change_expander():
    with st.sidebar.expander("🔒 修改密码", expanded=False):
        old_pass = st.text_input(
            "原密码", type="password", key="settings_old_password"
        )
        new_pass = st.text_input(
            "新密码", type="password", key="settings_new_password"
        )
        new_pass2 = st.text_input(
            "确认新密码", type="password", key="settings_new_password_confirm"
        )
        if st.button("🔑 修改密码", key="btn_change_password", use_container_width=True):
            _handle_password_change(old_pass, new_pass, new_pass2)


def _handle_password_change(old_pass: str, new_pass: str, new_pass2: str):
    if not old_pass or not new_pass:
        display_warning("请填写原密码和新密码")
        return
    if len(new_pass) < 6:
        display_warning("新密码长度不能少于6位")
        return
    if new_pass != new_pass2:
        display_warning("两次输入的新密码不一致")
        return
    try:
        change_password(old_pass, new_pass)
        display_success("密码已修改")
    except ApiError as e:
        display_error(str(e))


def render_settings_expander():
    """渲染个人设置展开面板。

    包含信息刷新、昵称/邮箱/水平/领域/时间/偏好编辑和保存功能。
    """
    with st.sidebar.expander("👤 个人设置", expanded=False):

        _render_refresh_button()

        profile = st.session_state.get("profile", {})
        new_display = st.text_input(
            "昵称",
            value=profile.get("display_name", ""),
            key="settings_display_name",
        )
        new_email = st.text_input(
            "邮箱",
            value=profile.get("email", ""),
            key="settings_email",
        )

        level_index = _resolve_index(LEVEL_OPTIONS, profile.get("level", "beginner"))
        new_level = st.selectbox(
            "当前水平",
            LEVEL_OPTIONS,
            index=level_index,
            key="settings_level",
        )

        new_field = st.text_input(
            "目标领域",
            value=profile.get("target_field", ""),
            key="settings_target_field",
        )
        new_time = st.slider(
            "每周可用时间(小时)",
            1,
            80,
            profile.get("available_time", 10),
            key="settings_available_time",
        )

        pref_index = _resolve_index(PREFERENCE_OPTIONS, profile.get("preference", "comprehensive"))
        new_pref = st.selectbox(
            "学习偏好",
            PREFERENCE_OPTIONS,
            index=pref_index,
            key="settings_preference",
        )

        _render_save_button(
            display_name=new_display,
            email=new_email,
            level=new_level,
            target_field=new_field,
            available_time=new_time,
            preference=new_pref,
        )


def _render_refresh_button():
    """渲染刷新个人信息按钮。"""
    if st.button("🔄 刷新信息", key="btn_refresh_profile"):
        try:
            profile_data = get_profile()
            st.session_state.profile = profile_data
            st.rerun()
        except ApiError:
            pass


def _render_save_button(**profile_fields):
    """渲染保存设置按钮及其回调逻辑。"""
    if st.button("💾 保存设置", key="btn_save_settings"):
        try:
            updated = update_profile(profile_fields)
            st.session_state.profile = updated
            display_name = profile_fields.get("display_name", "")
            if display_name:
                st.session_state.display_name = display_name
            display_success("已保存")
        except ApiError as e:
            display_error(str(e))


def render_agent_selector():
    """渲染Agent选择器展开面板。

    允许用户手动选择要使用的Agent角色或使用自动识别。
    """
    with st.sidebar.expander("🤖 Agent 选择", expanded=True):
        selected = st.radio(
            "选择 Agent",
            list(AGENT_ROLE_LABELS.keys()),
            format_func=lambda x: AGENT_ROLE_LABELS[x],
            key="sidebar_agent_select",
        )
        if selected != "auto":
            st.session_state.current_agent = selected
        else:
            st.session_state.current_agent = None


def render_quick_actions():
    st.sidebar.markdown("---")
    col_plan, col_logout = st.sidebar.columns(2)

    with col_plan:
        if st.button("📋 计划", key="btn_quick_plan", use_container_width=True):
            trigger_quick_chat("帮我制定一个学习计划", agent_role="planner")

    with col_logout:
        if st.button("🚪 退出", key="btn_logout_trigger", use_container_width=True):
            st.session_state[LOGOUT_CONFIRM_KEY] = True

    if st.session_state.get(LOGOUT_CONFIRM_KEY):
        st.sidebar.markdown("---")
        if show_confirmation_dialog(MESSAGE_LOGOUT_CONFIRM, key="logout_dialog"):
            _handle_logout()
        elif st.button("❌ 取消", key="btn_logout_cancel", use_container_width=True):
            st.session_state[LOGOUT_CONFIRM_KEY] = False
            st.rerun()


def _handle_logout():
    """执行退出登录流程：调用API注销 → 清空session → 刷新页面。"""
    api_logout()
    session_keys = [
        "logged_in", "token", "user_id", "username",
        "display_name", "profile", "messages", "current_agent",
        LOGOUT_CONFIRM_KEY,
    ]
    for key in session_keys:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def render_quiz_generator():
    """渲染测验生成侧边栏面板。

    允许用户指定知识点和题目数量，一键生成测验。
    """
    with st.sidebar.expander("🧪 测验", expanded=False):
        quiz_topic = st.text_input(
            "知识点",
            value="Python基础",
            key="quiz_gen_topic",
        )
        quiz_count = st.slider(
            "题目数量",
            1,
            10,
            3,
            key="quiz_gen_count",
        )
        if st.button("🎯 生成测验", key="btn_generate_quiz"):
            trigger_quick_chat(
                f"请为{quiz_topic}生成{quiz_count}道测试题",
                agent_role="quizzer",
            )