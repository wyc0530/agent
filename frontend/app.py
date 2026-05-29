"""
学习辅助系统 - 前端主入口

Streamlit 交互式UI，负责编排所有组件：
- 登录/注册认证（auth）
- SSE流式对话（chat）
- 个人设置/Agent选择/快捷操作（sidebar）

启动方式:
    streamlit run frontend/app.py
"""

import streamlit as st

from config import (
    PAGE_TITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    GLOBAL_CSS,
    init_session_state,
)
from components.auth import render_login_page
from components.chat import render_chat_history, handle_chat_input
from components.sidebar import (
    render_user_info,
    render_settings_expander,
    render_password_change_expander,
    render_agent_selector,
    render_quiz_generator,
    render_quick_actions,
)


def main():
    """应用主入口，按以下流程编排页面:

    1. 初始化 session_state 和页面配置
    2. 注入全局CSS
    3. 未登录 → 渲染登录页并停止
    4. 已登录 → 渲染侧边栏 + 聊天主界面
    """
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=PAGE_LAYOUT)
    init_session_state()
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    if not st.session_state.logged_in:
        render_login_page()
        st.stop()

    _render_sidebar()
    _render_main_area()


def _render_sidebar():
    """渲染左侧边栏所有功能模块。

    按从上到下的顺序排列:
    用户信息 → 个人设置 → Agent选择 → 快捷操作 → 测验生成
    """
    render_user_info()
    st.sidebar.markdown("---")
    render_settings_expander()
    st.sidebar.markdown("---")
    render_password_change_expander()
    st.sidebar.markdown("---")
    render_agent_selector()
    render_quick_actions()
    st.sidebar.markdown("---")
    render_quiz_generator()


def _render_main_area():
    """渲染主内容区域：标题 + 聊天历史 + 聊天输入框。"""
    st.markdown('<div id="main-content" role="main">', unsafe_allow_html=True)
    st.markdown(
        '<a href="#main-content" class="skip-link" '
        'style="position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;'
        'z-index:999;background:#4a5a7f;color:#fff;padding:8px 16px;border-radius:6px;'
        'text-decoration:none" '
        'onfocus="this.style.left=\'8px\';this.style.top=\'8px\';this.style.width=\'auto\';this.style.height=\'auto\'">'
        '跳至主内容</a>',
        unsafe_allow_html=True,
    )
    st.title("学习辅助系统")

    with st.container():
        render_chat_history()

    handle_chat_input()
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()