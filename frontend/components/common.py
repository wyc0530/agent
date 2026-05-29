"""
通用交互组件模块
提供加载态、空态提示、确认弹窗等跨页面复用的UI组件。
"""

from contextlib import contextmanager
from typing import Generator

import streamlit as st

from config import MESSAGE_EMPTY_CHAT


@contextmanager
def spinner_context(label: str = "处理中...") -> Generator[None, None, None]:
    """统一的加载状态上下文管理器。

    用法:
        with spinner_context("正在生成..."):
            result = heavy_operation()
    """
    with st.spinner(label):
        yield


def show_loading_overlay(message: str = "加载中..."):
    """显示临时加载覆盖层（非阻塞）。"""
    placeholder = st.empty()
    placeholder.info(f"⏳ {message}")
    return placeholder


def show_empty_state(
    message: str = MESSAGE_EMPTY_CHAT,
    custom_html: str = "",
):
    """显示空状态提示页面。

    Args:
        message: 纯文本或Markdown格式提示内容。
        custom_html: 可选的自定义HTML内容(用于特殊布局)。
    """
    st.markdown(f'<div class="empty-state" role="status">{custom_html}</div>', unsafe_allow_html=True)
    st.markdown(message)


def show_confirmation_dialog(
    message: str,
    key: str = "confirm_dialog",
) -> bool:
    """显示确认对话框。

    Args:
        message: 确认提示文本。
        key: 组件唯一标识，避免与页面其他组件冲突。

    Returns:
        True 表示用户确认，False 表示取消或未操作。
    """
    st.warning(f"⚠️ {message}")
    col_left, col_right = st.columns(2)
    with col_left:
        confirmed = st.button("✅ 确认", key=f"{key}_confirm", use_container_width=True)
    with col_right:
        cancelled = st.button("❌ 取消", key=f"{key}_cancel", use_container_width=True)

    if confirmed:
        return True
    return False


def display_error(message: str, duration_seconds: int = 0):
    """统一的错误消息展示。

    Args:
        message: 错误信息文本。
        duration_seconds: 自动消失时间(秒)，0表示不自动消失。
    """
    if duration_seconds > 0:
        st.toast(f"❌ {message}", icon="❌")
    else:
        st.error(f"❌ {message}")


def display_success(message: str, duration_seconds: int = 0):
    """统一的成功消息展示。

    Args:
        message: 成功信息文本。
        duration_seconds: 自动消失时间(秒)，0表示不自动消失。
    """
    if duration_seconds > 0:
        st.toast(f"✅ {message}", icon="✅")
    else:
        st.success(f"✅ {message}")


def display_warning(message: str):
    """统一的警告消息展示。"""
    st.warning(f"⚠️ {message}")