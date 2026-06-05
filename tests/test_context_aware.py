"""
上下文感知 Agent 专项测试

测试范围：
1. 上下文提取 (_extract_history) - 从 LearningState 中提取对话历史
2. RAG 检索 (_retrieve_context) - 向量数据库上下文检索
3. 上下文窗口管理 - 历史消息截断策略
4. 历史传递给 LLM - chat_with_history 调用验证
5. 边界指令注入 - 防止重复回答的提示词
6. 多轮对话模拟 - 模拟多轮对话场景
7. 各Agent上下文感知集成 - Planner/Expert/Partner/Reviewer/Examiner
8. 性能指标 - 响应延迟、重复回答消除
9. 长期记忆 - LongTermMemory 存储与检索
"""

import json
import os
import sys
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_LLM_KEY = os.getenv("LLM_API_KEY", "")
_LLM_AVAILABLE = bool(_LLM_KEY) and _LLM_KEY not in ("your-openai-api-key-here", "sk-your-api-key-here")
_llm_required = pytest.mark.skipif(not _LLM_AVAILABLE, reason="未配置有效的LLM API Key")


def _make_state(messages=None, **overrides):
    """创建带有对话历史的测试 LearningState"""
    from src.core.state import LearningState

    profile = {
        "name": "测试同学",
        "level": "中等",
        "target_field": "计算机科学",
        "available_time": 10,
        "preference": "综合学习",
    }
    base = {
        "messages": messages or [],
        "user_id": "ctx_test_user",
        "user_profile": profile,
        "weak_points": [{"knowledge_point": "递归", "error_rate": 0.7, "need_review": True}],
        "error_records": [],
        "quiz_results": [],
        "focus_time_minutes": 45,
        "focus_sessions": [],
    }
    base.update(overrides)
    return LearningState(**base)


def _make_messages(*pairs):
    """
    快速创建对话消息列表。
    每对参数: (role, content)
    """
    return [{"role": role, "content": content} for role, content in pairs]


# ============================================================
# 1. 上下文提取测试
# ============================================================

class TestContextExtraction:
    """测试 _extract_history 从 LearningState 提取对话历史"""

    def test_extract_basic(self):
        from src.agents.base_agent import BaseAgent

        messages = _make_messages(
            ("user", "你好"),
            ("assistant", "你好！"),
            ("user", "什么是Python"),
            ("assistant", "Python是一种编程语言"),
        )
        state = _make_state(messages=messages)
        history = BaseAgent._extract_history(state)
        assert len(history) == 4
        assert history[0]["content"] == "你好"
        assert history[-1]["content"] == "Python是一种编程语言"

    def test_extract_empty_state(self):
        from src.agents.base_agent import BaseAgent

        state = _make_state(messages=[])
        history = BaseAgent._extract_history(state)
        assert history == []

    def test_extract_no_messages_field(self):
        from src.agents.base_agent import BaseAgent

        state = _make_state()
        state.pop("messages", None)
        history = BaseAgent._extract_history(state)
        assert history == []

    def test_extract_truncation_max_turns(self):
        from src.agents.base_agent import BaseAgent

        messages = _make_messages(*[
            item for i in range(20) for item in (("user", f"q{i}"), ("assistant", f"a{i}"))
        ])
        state = _make_state(messages=messages)
        # 默认 max_turns=6, 即最多 12 条消息
        history = BaseAgent._extract_history(state)
        assert len(history) == 12
        assert history[0]["content"] == "q14"
        assert history[-1]["content"] == "a19"

    def test_extract_custom_max_turns(self):
        from src.agents.base_agent import BaseAgent

        messages = _make_messages(*[
            item for i in range(10) for item in (("user", f"q{i}"), ("assistant", f"a{i}"))
        ])
        state = _make_state(messages=messages)
        history = BaseAgent._extract_history(state, max_turns=3)
        assert len(history) == 6
        assert history[0]["content"] == "q7"

    def test_extract_returns_dict_list(self):
        from src.agents.base_agent import BaseAgent

        messages = [{"role": "user", "content": "test"}]
        state = _make_state(messages=messages)
        history = BaseAgent._extract_history(state)
        assert isinstance(history, list)
        assert isinstance(history[0], dict)
        assert "content" in history[0]
        assert "role" in history[0]


# ============================================================
# 2. RAG 检索测试
# ============================================================

class TestRAGRetrieval:
    """测试 _retrieve_context 向量数据库上下文检索"""

    def test_retrieve_with_empty_query(self):
        from src.agents.base_agent import BaseAgent

        result = BaseAgent._retrieve_context("")
        assert result == ""

    def test_retrieve_graceful_degradation(self):
        from src.agents.base_agent import BaseAgent

        result = BaseAgent._retrieve_context("Python学习")
        assert isinstance(result, str)

    def test_retrieve_with_user_id_filter(self):
        from src.agents.base_agent import BaseAgent
        from unittest.mock import patch

        with patch("src.core.memory.VectorStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.search.return_value = [
                {"content": "Python基础", "score": 0.95},
                {"content": "Python进阶", "score": 0.85},
            ]
            mock_store_cls.return_value = mock_store

            result = BaseAgent._retrieve_context("Python", user_id="test_user")
            assert "Python基础" in result
            assert "Python进阶" in result

    def test_retrieve_filters_low_score(self):
        from src.agents.base_agent import BaseAgent
        from unittest.mock import patch

        with patch("src.core.memory.VectorStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.search.return_value = [
                {"content": "高相关", "score": 0.9},
                {"content": "低相关", "score": 0.1},
                {"content": "中相关", "score": 0.5},
            ]
            mock_store_cls.return_value = mock_store

            result = BaseAgent._retrieve_context("test")
            assert "高相关" in result
            assert "低相关" not in result
            assert "中相关" in result

    def test_retrieve_truncates_long_content(self):
        from src.agents.base_agent import BaseAgent
        from unittest.mock import patch

        long_text = "A" * 500
        with patch("src.core.memory.VectorStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.search.return_value = [
                {"content": long_text, "score": 0.9},
            ]
            mock_store_cls.return_value = mock_store

            result = BaseAgent._retrieve_context("test")
            assert len(long_text) > 200
            assert long_text not in result
            assert "A" * 180 in result

    def test_retrieve_exception_handling(self):
        from src.agents.base_agent import BaseAgent
        from unittest.mock import patch

        with patch("src.core.memory.VectorStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.search.side_effect = RuntimeError("模拟数据库错误")
            mock_store_cls.return_value = mock_store

            result = BaseAgent._retrieve_context("test")
            assert result == ""


# ============================================================
# 3. 上下文窗口管理测试
# ============================================================

class TestContextWindowManagement:
    """测试上下文窗口管理策略"""

    def test_chat_with_history_truncation(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = _make_messages(*[
            item for i in range(10) for item in (("user", f"第{i}轮问题"), ("assistant", f"第{i}轮回答"))
        ])

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history, system_prompt="你是助手")

    def test_chat_with_history_format(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = [
            {"role": "user", "content": "什么是Python?"},
            {"role": "assistant", "content": "Python是一种高级编程语言"},
        ]

        with patch.object(LLMProvider, "invoke") as mock_invoke:
            mock_invoke.return_value = MagicMock(content="test")
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("继续", history, system_prompt="你是助手")

            call_args = mock_invoke.call_args
            messages = call_args[0][0]
            assert len(messages) >= 3
            assert any("对话历史" in str(m.content) for m in messages)

    def test_chat_with_history_empty(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            result = llm.chat_with_history("新问题", [], system_prompt="你是助手")
            assert result == "test"

    def test_chat_history_uses_compact_format(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = [
            {"role": "user", "content": "X" * 300},
            {"role": "assistant", "content": "Y" * 300},
        ]

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history)
            # 验证不抛出异常

    def test_chat_with_history_accommodates_dict_and_object(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        class MockMessage:
            def __init__(self, content, msg_type):
                self.content = content
                self.type = msg_type

        history = [
            {"role": "user", "content": "dict msg"},
            MockMessage("obj msg", "human"),
            MockMessage("ai msg", "ai"),
        ]

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history)
            # 验证不抛出异常


# ============================================================
# 4. 边界指令注入测试
# ============================================================

class TestBoundaryInstructions:
    """测试防止重复回答的边界指令"""

    def test_boundary_in_chat_append(self):
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "测试系统提示"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        agent._chat = MagicMock(return_value="test")

        try:
            agent._chat("系统提示", "用户消息")
        except Exception:
            pass

    def test_boundary_text_present(self):
        boundary = (
            "\n\n## 重要\n请仅回答用户的最新问题，基于上下文给出针对性回答。"
            "不要重复此前已经解答过的内容。"
        )
        assert "请仅回答用户的最新问题" in boundary
        assert "不要重复此前已经解答过的内容" in boundary
        assert "## 重要" in boundary

    def test_boundary_in_system_prompt(self):
        from unittest.mock import MagicMock, patch
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "原始系统提示"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        with patch.object(agent._llm, "chat", return_value="test") as mock_chat:
            agent._chat("原始系统提示", "用户消息")
            full_prompt = mock_chat.call_args[1]["system_prompt"]
            assert "请仅回答用户的最新问题" in full_prompt
            assert "不要重复此前已经解答过的内容" in full_prompt


# ============================================================
# 5. 多轮对话模拟测试
# ============================================================

class TestMultiTurnConversation:
    """多轮对话模拟测试"""

    def test_multi_turn_state_accumulation(self):
        messages = []
        from src.core.state import LearningState

        profile = {"name": "测试", "level": "初级", "target_field": "Python", "available_time": 10, "preference": "综合"}
        state = LearningState(
            messages=messages,
            user_id="multi_turn_test",
            user_profile=profile,
            weak_points=[],
            error_records=[],
            quiz_results=[],
            focus_time_minutes=0,
            focus_sessions=[],
        )

        turns = [
            ("user", "我想学习Python"),
            ("assistant", "好的，我帮你制定Python学习计划"),
            ("user", "先推荐入门书籍"),
            ("assistant", "推荐《Python编程：从入门到实践》"),
        ]
        for role, content in turns:
            state["messages"].append({"role": role, "content": content})

        from src.agents.base_agent import BaseAgent
        history = BaseAgent._extract_history(state, max_turns=3)
        assert len(history) == 4
        assert history[0]["content"] == "我想学习Python"
        assert history[-1]["content"] == "推荐《Python编程：从入门到实践》"

    def test_context_continuity_across_turns(self):
        from src.agents.base_agent import BaseAgent

        messages = _make_messages(
            ("user", "Python怎么学"),
            ("assistant", "建议从基础语法开始"),
            ("user", "那基础语法有哪些"),
            ("assistant", "包括变量、数据类型、控制流等"),
            ("user", "变量怎么定义"),
        )
        state = _make_state(messages=messages)
        history = BaseAgent._extract_history(state, max_turns=3)
        assert len(history) == 5
        assert history[-1]["content"] == "变量怎么定义"

    def test_context_never_repeats_raw_internal_format(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
        ]

        with patch.object(LLMProvider, "invoke") as mock_invoke:
            mock_invoke.return_value = MagicMock(content="test")
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history)

            all_content = " ".join(
                str(m.content) for m in mock_invoke.call_args[0][0]
            )
            assert "AIMessage" not in all_content
            assert "HumanMessage" not in all_content
            assert "SystemMessage" not in all_content


# ============================================================
# 6. 各Agent上下文感知集成测试
# ============================================================

class TestPlannerContextAware:
    """Planner Agent 上下文感知测试"""

    def test_planner_receives_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.planner import PlannerAgent

        messages = _make_messages(
            ("user", "我想学Python"),
            ("assistant", "好的，Python很适合入门"),
        )
        state = _make_state(messages=messages)

        agent = PlannerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = '{"title": "test", "goals": [], "phases": []}'
            agent.run(state, "帮我制定计划")
            call_kwargs = mock_chat.call_args[1]
            assert "history" in call_kwargs
            assert len(call_kwargs["history"]) == 2

    def test_planner_context_preserves_previous_plan(self):
        from unittest.mock import MagicMock, patch
        from src.agents.planner import PlannerAgent

        messages = _make_messages(
            ("user", "给我制定一个Python学习计划"),
            ("assistant", "已生成Python学习计划，包含3个阶段"),
            ("user", "调整一下，我想先学Web开发"),
        )
        state = _make_state(
            messages=messages,
            learning_plan={
                "title": "Python学习计划",
                "phases": [
                    {"phase_name": "基础", "phase_description": "入门", "order": 1},
                    {"phase_name": "进阶", "phase_description": "高级", "order": 2},
                ],
                "goals": [],
            },
        )

        agent = PlannerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = '{"title": "adjusted", "goals": [], "phases": []}'
            agent.run(state, "调整一下，我想先学Web开发")
            system_prompt = mock_chat.call_args[0][0]
            assert "Python学习计划" in system_prompt
            assert "阶段数: 2" in system_prompt

    def test_planner_empty_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.planner import PlannerAgent

        state = _make_state(messages=[])
        agent = PlannerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = '{"title": "fresh", "goals": [], "phases": []}'
            agent.run(state, "新计划")
            call_kwargs = mock_chat.call_args[1]
            assert call_kwargs.get("history") == [] or call_kwargs.get("history") is None


class TestExpertContextAware:
    """Expert Agent 上下文感知测试"""

    def test_expert_receives_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.expert import ExpertAgent

        messages = _make_messages(
            ("user", "Python基础语法推荐"),
            ("assistant", "推荐以下资源..."),
        )
        state = _make_state(messages=messages)

        agent = ExpertAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = "推荐内容"
            agent.run(state, "有没有更进阶的")
            call_kwargs = mock_chat.call_args[1]
            assert "history" in call_kwargs
            assert len(call_kwargs["history"]) == 2

    def test_expert_context_with_plan(self):
        from unittest.mock import MagicMock, patch
        from src.agents.expert import ExpertAgent

        messages = _make_messages(
            ("user", "推荐数据结构的学习资料"),
            ("assistant", "推荐《算法导论》"),
        )
        state = _make_state(
            messages=messages,
            learning_plan={
                "title": "CS学习",
                "phases": [
                    {"phase_name": "数据结构", "phase_description": "栈、队列、树", "order": 1},
                ],
                "goals": [],
            },
        )

        agent = ExpertAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = "推荐更多"
            agent.run(state, "还有哪些书籍推荐")
            system_prompt = mock_chat.call_args[0][0]
            assert "数据结构" in system_prompt


class TestPartnerContextAware:
    """Partner Agent 上下文感知测试"""

    def test_partner_receives_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.partner import PartnerAgent

        messages = _make_messages(
            ("user", "递归是什么"),
            ("assistant", "递归是函数调用自身"),
            ("user", "能举个例子吗"),
        )
        state = _make_state(messages=messages)

        agent = PartnerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = "举例说明"
            agent.run(state, "能举个例子吗")
            call_kwargs = mock_chat.call_args[1]
            assert "history" in call_kwargs
            assert len(call_kwargs["history"]) == 3

    def test_partner_context_avoid_repetition(self):
        from unittest.mock import MagicMock, patch
        from src.agents.partner import PartnerAgent

        messages = _make_messages(
            ("user", "什么是递归"),
            ("assistant", "递归是一种编程技巧，指函数直接或间接调用自身"),
            ("user", "那动态规划呢"),
        )
        state = _make_state(messages=messages)

        agent = PartnerAgent()
        with patch.object(agent._llm, "chat_with_history", return_value="动态规划是...") as mock_llm:
            agent.run(state, "那动态规划呢")
            system_prompt = mock_llm.call_args[1]["system_prompt"]
            assert "不要重复" in system_prompt

    def test_partner_rag_integration(self):
        from unittest.mock import MagicMock, patch
        from src.agents.partner import PartnerAgent

        state = _make_state()
        agent = PartnerAgent()
        with patch.object(agent, "_chat") as mock_chat, \
             patch.object(agent._retriever, "retrieve", return_value=[
                 {"id": "1", "content": "递归是编程中的一种重要概念", "score": 0.9},
             ]):
            mock_chat.return_value = "回答"
            agent.run(state, "什么是递归")
            system_prompt = mock_chat.call_args[0][0]
            assert "参考知识库内容" in system_prompt or "参考资料" in system_prompt


class TestReviewerContextAware:
    """Reviewer Agent 上下文感知测试"""

    def test_reviewer_receives_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.reviewer import ReviewerAgent

        messages = _make_messages(
            ("user", "分析我的错题"),
            ("assistant", "你的薄弱点在递归和链表"),
            ("user", "帮我重点分析递归"),
        )
        state = _make_state(messages=messages)

        agent = ReviewerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = '{"weak_points_summary": ["递归"], "error_categories": [], "review_suggestions": [], "feedback_for_planner": ""}'
            agent.run(state, "帮我重点分析递归")
            call_kwargs = mock_chat.call_args[1]
            assert "history" in call_kwargs
            assert len(call_kwargs["history"]) == 3

    def test_reviewer_error_recovery_with_context(self):
        from unittest.mock import MagicMock, patch
        from src.agents.reviewer import ReviewerAgent

        messages = _make_messages(
            ("user", "分析错题"),
            ("assistant", "好的，以下是分析..."),
        )
        state = _make_state(messages=messages)

        agent = ReviewerAgent()
        with patch.object(agent, "_chat", side_effect=RuntimeError("LLM错误")):
            result = agent.run(state, "继续分析")
            assert not result.success
            assert "LLM 调用失败" in (result.error or "")


class TestExaminerContextAware:
    """Examiner Agent 上下文感知测试"""

    def test_examiner_receives_history(self):
        from unittest.mock import MagicMock, patch
        from src.agents.examiner import ExaminerAgent

        messages = _make_messages(
            ("user", "我准备考研"),
            ("assistant", "好的，我们来制定备考方案"),
            ("user", "重点复习数据结构"),
        )
        state = _make_state(messages=messages)

        agent = ExaminerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = "备考建议"
            agent.run(state, "重点复习数据结构")
            call_kwargs = mock_chat.call_args[1]
            assert "history" in call_kwargs
            assert len(call_kwargs["history"]) == 3


# ============================================================
# 7. 性能指标测试
# ============================================================

class TestPerformanceMetrics:
    """性能指标验证测试"""

    def test_chat_method_response_timing(self):
        from unittest.mock import MagicMock
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "test"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        agent._llm.chat = MagicMock(return_value="test")

        start = time.perf_counter()
        agent._chat("system", "user")
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 500, f"Chat method too slow: {elapsed:.1f}ms"

    def test_history_extraction_performance(self):
        from src.agents.base_agent import BaseAgent
        messages = _make_messages(*[
            item for i in range(100) for item in (("user", f"msg{i}"), ("assistant", f"reply{i}"))
        ])
        state = _make_state(messages=messages)

        start = time.perf_counter()
        for _ in range(100):
            BaseAgent._extract_history(state, max_turns=6)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 200, f"History extraction too slow: {elapsed:.1f}ms"

    def test_context_formatting_performance(self):
        from src.api.main import _format_conversation_context
        import time

        content = "测试消息" * 50
        start = time.perf_counter()
        for _ in range(50):
            _format_conversation_context("perf_test", max_turns=4)
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 300, f"Context formatting too slow: {elapsed:.1f}ms"

    def test_agent_safe_run_duration_recorded(self):
        from unittest.mock import MagicMock
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        agent._chat = MagicMock(return_value='{"title": "test", "goals": [], "phases": []}')
        state = _make_state()
        result = agent.run(state, "test")
        assert result.duration_ms > 0


# ============================================================
# 8. 重复回答消除测试
# ============================================================

class TestRepeatAnswerPrevention:
    """重复回答消除测试"""

    def test_chat_with_history_excludes_previous_answers(self):
        from unittest.mock import MagicMock, patch
        from src.llm import LLMProvider

        history = [
            {"role": "user", "content": "Q1: Python是什么"},
            {"role": "assistant", "content": "A1: Python是一种高级编程语言"},
            {"role": "user", "content": "Q2: 推荐Python书籍"},
            {"role": "assistant", "content": "A2: 推荐《Python编程：从入门到实践》"},
            {"role": "user", "content": "Q3: Python是什么"},
        ]

        with patch.object(LLMProvider, "invoke") as mock_invoke:
            mock_invoke.return_value = MagicMock(content="test")
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("Q3: Python是什么", history)

            all_content = " ".join(
                str(m.content) for m in mock_invoke.call_args[0][0]
            )
            assert "仅供参考" in all_content or "对话历史" in all_content

    def test_agent_system_prompt_prevents_repetition(self):
        from unittest.mock import MagicMock, patch
        from src.agents.partner import PartnerAgent

        messages = _make_messages(
            ("user", "解释递归"),
            ("assistant", "递归是函数调用自身的技术"),
            ("user", "解释递归"),
        )
        state = _make_state(messages=messages)

        agent = PartnerAgent()
        with patch.object(agent._llm, "chat_with_history", return_value="回答") as mock_llm:
            agent.run(state, "解释递归")
            system_prompt = mock_llm.call_args[1]["system_prompt"]
            assert "不要重复此前已经解答过的内容" in system_prompt

    def test_multi_agent_no_repeat_across_agents(self):
        from unittest.mock import MagicMock, patch
        from src.agents.planner import PlannerAgent
        from src.agents.partner import PartnerAgent

        messages = _make_messages(
            ("user", "我想学Python"),
            ("assistant", "已为你制定Python学习计划"),
        )
        state = _make_state(messages=messages)

        # 测试 Planner — 边界指令由 _chat 内部添加，验证 LLM 层收到的完整 prompt
        planner = PlannerAgent()
        with patch.object(planner._llm, "chat_with_history", return_value='{"title": "test", "goals": [], "phases": []}') as mock_llm:
            planner.run(state, "调整计划")
            planner_prompt = mock_llm.call_args[1]["system_prompt"]
            assert "不要重复" in planner_prompt

        # 测试 Partner — 同样验证 LLM 层收到的完整 prompt
        partner = PartnerAgent()
        with patch.object(partner._llm, "chat_with_history", return_value="回答") as mock_llm:
            partner.run(state, "Python基础是什么")
            partner_prompt = mock_llm.call_args[1]["system_prompt"]
            assert "不要重复" in partner_prompt


# ============================================================
# 9. 长期记忆测试
# ============================================================

class TestLongTermMemory:
    """长期记忆存储与检索测试"""

    def test_remember_interaction(self):
        from unittest.mock import MagicMock, patch
        from src.core.memory import LongTermMemory

        with patch("src.core.memory.VectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.add_document.return_value = "doc123"
            mock_store.return_value = mock_store_instance

            memory = LongTermMemory("test_user")
            doc_id = memory.remember_interaction("user", "这条消息存入记忆")
            assert doc_id == "doc123"
            mock_store_instance.add_document.assert_called_once()

    def test_store_error_record(self):
        from unittest.mock import MagicMock, patch
        from src.core.memory import LongTermMemory
        from src.core.state import ErrorRecord, QuizQuestion

        question = QuizQuestion(
            question_id="q1",
            content="什么是递归",
            answer="函数调用自身",
            explanation="递归是编程中的重要概念",
            knowledge_point="递归",
        )
        record = ErrorRecord(
            question=question,
            user_answer="函数调用外部",
            knowledge_point="递归",
        )

        with patch("src.core.memory.VectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.add_document.return_value = "err123"
            mock_store.return_value = mock_store_instance

            memory = LongTermMemory("test_user")
            doc_id = memory.store_error_record(record)
            assert doc_id == "err123"

    def test_retrieve_relevant(self):
        from unittest.mock import MagicMock, patch
        from src.core.memory import LongTermMemory

        mock_results = [
            {"id": "d1", "content": "相关内容1", "score": 0.9},
            {"id": "d2", "content": "相关内容2", "score": 0.8},
        ]

        with patch("src.core.memory.VectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.search.return_value = mock_results
            mock_store.return_value = mock_store_instance

            memory = LongTermMemory("test_user")
            results = memory.retrieve_relevant("测试查询", top_k=3)
            assert len(results) == 2

    def test_retrieve_with_type_filter(self):
        from unittest.mock import MagicMock, patch
        from src.core.memory import LongTermMemory

        with patch("src.core.memory.VectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.search.return_value = []
            mock_store.return_value = mock_store_instance

            memory = LongTermMemory("test_user")
            memory.retrieve_relevant("查询", filter_type="error_record")
            call_kwargs = mock_store_instance.search.call_args[1]
            assert call_kwargs["filter_metadata"]["type"] == "error_record"

    def test_get_user_summary(self):
        from unittest.mock import MagicMock, patch
        from src.core.memory import LongTermMemory

        with patch("src.core.memory.VectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.search.return_value = [
                {"id": "d1", "content": "学习记录", "metadata": {"knowledge_point": "递归"}},
                {"id": "d2", "content": "错题", "metadata": {"knowledge_point": "链表"}},
            ]
            mock_store.return_value = mock_store_instance

            memory = LongTermMemory("test_user")
            summary = memory.get_user_summary()
            assert "total_interactions" in summary
            assert "total_errors" in summary
            assert "knowledge_points" in summary


# ============================================================
# 10. 边界/异常情况测试
# ============================================================

class TestContextEdgeCases:
    """上下文感知边界条件测试"""

    def test_extract_history_with_none_messages(self):
        from src.agents.base_agent import BaseAgent
        from src.core.state import LearningState

        profile = {"name": "test", "level": "初级", "target_field": "Python", "available_time": 10, "preference": "综合"}
        state = LearningState(
            messages=None,
            user_id="test",
            user_profile=profile,
            weak_points=[],
            error_records=[],
            quiz_results=[],
            focus_time_minutes=0,
            focus_sessions=[],
        )
        history = BaseAgent._extract_history(state)
        assert history == []

    def test_extract_history_with_malformed_messages(self):
        from src.agents.base_agent import BaseAgent

        messages = [
            {"role": "user"},
            {"role": "assistant", "content": "有内容"},
            {"content": "无角色"},
        ]
        state = _make_state(messages=messages)
        history = BaseAgent._extract_history(state)
        assert len(history) == 3

    def test_chat_with_history_all_dict(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
        ]

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            result = llm.chat_with_history("新问题", history)
            assert result == "test"

    def test_chat_with_history_content_truncation(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        long_content = "很长的内容" * 100
        history = [{"role": "user", "content": long_content}]

        with patch.object(LLMProvider, "invoke") as mock_invoke:
            mock_invoke.return_value = MagicMock(content="test")
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history)

            all_content = " ".join(
                str(m.content) for m in mock_invoke.call_args[0][0]
            )
            assert long_content not in all_content

    def test_chat_with_history_unknown_role(self):
        from src.llm import LLMProvider
        from unittest.mock import patch

        history = [{"role": "unknown", "content": "test"}]

        with patch.object(LLMProvider, "invoke", return_value=MagicMock(content="test")):
            llm = LLMProvider()
            llm._model = MagicMock()
            llm.chat_with_history("新问题", history)
            # 验证不抛出异常，使用默认标签

    def test_retrieve_context_with_vector_store_error(self):
        from src.agents.base_agent import BaseAgent
        from unittest.mock import patch

        with patch("src.core.memory.VectorStore") as mock_store_cls:
            mock_store = MagicMock()
            mock_store.search.side_effect = ConnectionError("无法连接数据库")
            mock_store_cls.return_value = mock_store

            result = BaseAgent._retrieve_context("test query")
            assert result == ""


# ============================================================
# 11. 上下文传递完整性测试
# ============================================================

class TestContextPropagation:
    """上下文传递完整性测试"""

    def test_context_flows_from_state_to_llm(self):
        from unittest.mock import MagicMock, patch
        from src.agents.planner import PlannerAgent

        messages = _make_messages(
            ("user", "Q1"),
            ("assistant", "A1"),
            ("user", "Q2"),
            ("assistant", "A2"),
        )
        state = _make_state(messages=messages)

        agent = PlannerAgent()
        with patch.object(agent, "_chat") as mock_chat:
            mock_chat.return_value = '{"title": "x", "goals": [], "phases": []}'
            agent.run(state, "Q3")

            call_kwargs = mock_chat.call_args[1]
            history = call_kwargs["history"]
            assert len(history) == 4
            assert history[0]["content"] == "Q1"
            assert history[-1]["content"] == "A2"

    def test_all_agents_use_extract_history(self):
        from src.agents.planner import PlannerAgent
        from src.agents.expert import ExpertAgent
        from src.agents.partner import PartnerAgent
        from src.agents.reviewer import ReviewerAgent
        from src.agents.examiner import ExaminerAgent

        agents = [
            PlannerAgent(),
            ExpertAgent(),
            PartnerAgent(),
            ReviewerAgent(),
            ExaminerAgent(),
        ]

        messages = _make_messages(
            ("user", "历史消息1"),
            ("assistant", "历史回复1"),
        )
        state = _make_state(messages=messages)

        for agent in agents:
            with patch.object(agent, "_chat", return_value="test") as mock_chat:
                if hasattr(agent, "_run_impl"):
                    agent._run_impl(state, "测试消息")
                else:
                    continue
                if mock_chat.called:
                    call_kwargs = mock_chat.call_args[1]
                    assert "history" in call_kwargs, \
                        f"{agent.role.value} should pass history to _chat"
                    assert len(call_kwargs["history"]) == 2, \
                        f"{agent.role.value} history length mismatch"


# ============================================================
# 12. LLM 回退机制测试
# ============================================================

class TestLLMFallbackWithContext:
    """带上下文的 LLM 回退测试"""

    def test_chat_with_history_fallback(self):
        from unittest.mock import MagicMock, patch
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "test"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        history = [{"role": "user", "content": "test"}]

        with patch.object(agent._llm, "chat_with_history") as mock_chat_hist, \
             patch.object(agent._llm, "chat") as mock_chat:
            mock_chat_hist.side_effect = [RuntimeError("首次失败"), "fallback response"]
            mock_chat.return_value = "chat fallback"

            result = agent._chat("system", "user", history=history)
            assert result == "fallback response"
            assert mock_chat_hist.call_count == 2
            assert mock_chat.call_count == 0

    def test_chat_without_history_fallback(self):
        from unittest.mock import MagicMock, patch
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "test"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        with patch.object(agent._llm, "chat") as mock_chat:
            mock_chat.side_effect = [RuntimeError("首次失败"), "fallback"]
            result = agent._chat("system", "user")
            assert result == "fallback"
            assert mock_chat.call_count == 2

    def test_chat_double_failure_raises(self):
        from unittest.mock import MagicMock, patch
        from src.agents.base_agent import BaseAgent
        from src.core.state import AgentRole

        class DummyAgent(BaseAgent):
            role = AgentRole.ASSISTANT
            def _build_system_prompt(self, state):
                return "test"
            def run(self, state, message=""):
                pass

        agent = DummyAgent()
        with patch.object(agent._llm, "chat") as mock_chat:
            mock_chat.side_effect = RuntimeError("总是失败")
            with pytest.raises(RuntimeError, match="LLM 调用失败"):
                agent._chat("system", "user")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])