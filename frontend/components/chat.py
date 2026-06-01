"""
聊天交互组件
实现SSE流式对话、消息渲染和历史展示，支持空态引导和错误恢复。
"""

import json
import threading
from typing import Optional

import requests
import streamlit as st

from api_client import stream_chat_request
from api_client import ApiError
from config import (
    SSE_POLL_INTERVAL,
    SSE_TIMEOUT_SECONDS,
    MESSAGE_EMPTY_CHAT,
    MESSAGE_AGENT_LABEL,
    MESSAGE_TIMEOUT,
    MESSAGE_ERROR_PREFIX,
    AGENT_ROLE_LABELS,
)
from components.common import display_error, show_empty_state

AVATAR_USER = "👤"
AVATAR_ASSISTANT = "🤖"
AVATAR_SYSTEM = "⚠️"


def _parse_sse_line(line: str) -> Optional[dict]:
    """解析单行SSE数据。

    Args:
        line: 原始SSE行数据。

    Returns:
        解析后的数据字典，解析失败返回 None。
    """
    if not line or not line.startswith("data: "):
        return None
    data_str = line[len("data: "):]
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        return None


def _iter_sse_lines(response):
    """安全迭代SSE响应行，自动处理解码和过滤空行。"""
    try:
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line:
                yield raw_line
    except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
        return


def stream_chat(
    message: str,
    agent_role: str = "",
    user_id: str = "",
):
    """执行SSE流式对话请求，实时渲染AI回复。

    使用独立线程发起HTTP长连接请求，
    主线程每 SSE_POLL_INTERVAL 轮询一次结果并更新UI。

    Args:
        message: 用户输入的消息文本。
        agent_role: 指定的Agent角色（空字符串表示自动识别）。
        user_id: 用户标识。
    """
    payload = {
        "message": message,
        "user_id": user_id or st.session_state.get("user_id", ""),
        "history": [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.get("messages", [])[-20:]
        ],
    }
    if agent_role and agent_role != "auto":
        payload["agent_role"] = agent_role

    placeholder = st.empty()
    full_text_container: list[str] = [""]
    agent_role_container: list[str] = [""]
    done = threading.Event()
    error_message: list[Optional[str]] = [None]

    def _fetch_stream():
        """在独立线程中获取SSE数据流。"""
        try:
            response = stream_chat_request(payload)
            for line in _iter_sse_lines(response):
                data = _parse_sse_line(line)
                if data is None:
                    continue

                msg_type = data.get("type", "")
                if msg_type == "start":
                    agent_role_container[0] = data.get("agent_role", "")
                elif msg_type == "chunk":
                    full_text_container[0] += data.get("content", "")
                elif msg_type == "done":
                    break
                elif msg_type == "error":
                    error_message[0] = data.get("content", "流式响应错误")
                    break
        except ApiError as e:
            error_message[0] = str(e)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            error_message[0] = "无法连接到后端 API，请确保服务已启动"
        except Exception:
            error_message[0] = "对话服务暂时不可用，请稍后重试"
        finally:
            done.set()

    fetch_thread = threading.Thread(target=_fetch_stream, daemon=True)
    fetch_thread.start()

    _render_streaming_output(placeholder, done, full_text_container, fetch_thread, agent_role)

    _finalize_chat_message(full_text_container[0], agent_role_container[0], error_message[0])


def _render_streaming_output(
    placeholder,
    done_event: threading.Event,
    full_text_container: list[str],
    fetch_thread: threading.Thread,
    agent_role: str = "",
):
    """渲染流式输出，逐字显示AI回复并带光标动画。

    Args:
        placeholder: Streamlit 空占位符，用于实时更新内容。
        done_event: 标识流式请求是否完成的事件。
        full_text_container: 可变容器，子线程实时更新 [0] 索引的文本内容。
        fetch_thread: 数据获取子线程。
        agent_role: 当前指定的Agent角色（用于显示等待提示）。
    """
    last_rendered_length = 0
    while not done_event.is_set() or len(full_text_container[0]) > last_rendered_length:
        if len(full_text_container[0]) > last_rendered_length:
            placeholder.markdown(full_text_container[0] + "\u258c", unsafe_allow_html=False)
            last_rendered_length = len(full_text_container[0])
        else:
            agent_label = AGENT_ROLE_LABELS.get(agent_role, "助手")
            placeholder.markdown(f"*正在等待 {agent_label} 响应...* \u258c", unsafe_allow_html=False)
        done_event.wait(timeout=SSE_POLL_INTERVAL)

    fetch_thread.join(timeout=SSE_TIMEOUT_SECONDS)


def _finalize_chat_message(
    full_text: str,
    agent_role_text: str,
    error: Optional[str],
):
    """完成聊天消息的最后渲染和存储。

    Args:
        full_text: 完整的AI回复文本。
        agent_role_text: 实际处理消息的Agent角色名称。
        error: 错误消息文本（无错误时为None）。
    """
    if error:
        display_error(error)
        _append_assistant_message(f"{MESSAGE_ERROR_PREFIX} {error}", "system")

    else:
        if not full_text.strip():
            full_text = MESSAGE_TIMEOUT
            display_error(full_text)
        _append_assistant_message(full_text, agent_role_text)


def _append_assistant_message(content: str, agent: str):
    """将助手消息追加到聊天历史。"""
    st.session_state.messages.append({
        "role": "assistant",
        "content": content,
        "avatar": AVATAR_ASSISTANT,
        "agent": agent,
    })


def append_user_message(content: str):
    """将用户消息追加到聊天历史。"""
    st.session_state.messages.append({
        "role": "user",
        "content": content,
        "avatar": AVATAR_USER,
    })


def render_chat_history():
    """渲染完整的聊天消息历史。

    如果没有历史消息，则显示空态引导页面。
    """
    if not st.session_state.messages:
        show_empty_state(MESSAGE_EMPTY_CHAT)
        return

    for msg in st.session_state.messages:
        avatar = msg.get("avatar", AVATAR_ASSISTANT if msg["role"] != "user" else AVATAR_USER)
        display_role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(display_role, avatar=avatar):
            st.markdown(msg["content"], unsafe_allow_html=False)
            if msg.get("agent") and msg["role"] != "user":
                st.caption(MESSAGE_AGENT_LABEL.format(agent=msg["agent"]))


def handle_chat_input():
    """处理聊天输入框的提交事件。

    从 st.chat_input 获取用户输入，发送到后端并渲染回复。
    """
    prompt = st.chat_input("输入你的问题...")
    if not prompt:
        return

    append_user_message(prompt)
    with st.chat_message("user", avatar=AVATAR_USER):
        st.markdown(prompt, unsafe_allow_html=False)

    with st.chat_message("assistant", avatar=AVATAR_ASSISTANT):
        stream_chat(
            prompt,
            agent_role=st.session_state.get("current_agent") or "",
            user_id=st.session_state.get("user_id", ""),
        )
    st.rerun()


def trigger_quick_chat(message: str, agent_role: str = ""):
    """快捷操作触发一次完整的对话流程。

    Args:
        message: 预设的提问消息。
        agent_role: 指定处理的Agent角色。
    """
    append_user_message(message)
    with st.chat_message("assistant", avatar=AVATAR_ASSISTANT):
        stream_chat(
            message,
            agent_role=agent_role,
            user_id=st.session_state.get("user_id", ""),
        )
    st.rerun()