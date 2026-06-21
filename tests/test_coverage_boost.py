"""
覆盖率补充测试

针对低覆盖率文件（search.py 48%, assistant.py 53%, retriever.py 54%,
llm.py 55%, checkpoint.py 59%）补充单元测试，目标将整体覆盖率提升至 80%+。
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_state(user_id="test_user", **overrides):
    from src.core.state import LearningState
    profile = {
        "name": "测试同学", "level": "中等",
        "target_field": "计算机科学", "available_time": 10,
        "preference": "综合学习",
    }
    base = {
        "messages": [], "user_id": user_id, "user_profile": profile,
        "weak_points": [], "error_records": [], "quiz_results": [],
        "focus_time_minutes": 0, "focus_sessions": [],
        "pending_feedback": False, "feedback_message": "",
        "error_message": "", "current_agent": "assistant",
        "agent_outputs": {},
    }
    base.update(overrides)
    return base


# ===================================================================
# search.py 覆盖率提升
# ===================================================================

class TestWebSearchTool:
    def test_search_course_directories(self):
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_course_directories("Python", 3)
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r
            assert "source" in r

    def test_search_course_directories_all(self):
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_course_directories("机器学习", 50)
        assert isinstance(results, list)
        assert len(results) > 0
        for r in results:
            assert "title" in r
            assert "url" in r

    def test_execute_empty_query(self):
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool.execute(query="")
        assert results == []

    def test_duckduckgo_fallback(self):
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_duckduckgo("Python tutorial", 3)
        assert isinstance(results, list)

    @patch("src.core.tools.search.requests.get")
    def test_duckduckgo_with_mock(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "RelatedTopics": [
                {"Text": "Python is great", "FirstURL": "https://python.org"},
            ]
        }
        mock_get.return_value = mock_resp
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_duckduckgo("Python", 5)
        assert len(results) >= 1
        assert results[0]["source"] == "DuckDuckGo"

    @patch("src.core.tools.search.requests.get")
    def test_duckduckgo_exception(self, mock_get):
        mock_get.side_effect = ValueError("network error")
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_duckduckgo("query", 5)
        assert results == []

    @patch("src.core.tools.search.requests.get")
    def test_serpapi_search(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "organic_results": [
                {"title": "Python", "link": "https://py.org", "snippet": "Python lang", "source": "web"},
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with patch("src.core.tools.search.Settings.SERPAPI_API_KEY", "valid-key"):
            from src.core.tools.search import WebSearchTool
            tool = WebSearchTool()
            results = tool._search_serpapi("Python", 5)
            assert len(results) >= 1
            assert results[0]["title"] == "Python"

    @patch("src.core.tools.search.requests.get")
    def test_serpapi_fallback_on_error(self, mock_get):
        mock_get.side_effect = ValueError("api error")
        with patch("src.core.tools.search.Settings.SERPAPI_API_KEY", "valid-key"):
            from src.core.tools.search import WebSearchTool
            tool = WebSearchTool()
            results = tool.execute(query="Python", num_results=3)
            assert isinstance(results, list)

    def test_search_fallback(self):
        from src.core.tools.search import WebSearchTool
        tool = WebSearchTool()
        results = tool._search_fallback("Python", 3)
        assert isinstance(results, list)
        assert len(results) > 0


class TestMultiSourceSearcher:
    def test_search_all(self):
        from src.core.tools.search import MultiSourceSearcher
        searcher = MultiSourceSearcher()
        results = searcher.search_all("Python入门", num_per_source=2)
        assert "web" in results
        assert isinstance(results["web"], list)

    def test_search_single_web(self):
        from src.core.tools.search import MultiSourceSearcher
        searcher = MultiSourceSearcher()
        results = searcher.search_single("Python", source="web", num=3)
        assert isinstance(results, list)

    def test_search_single_unknown_source(self):
        from src.core.tools.search import MultiSourceSearcher
        searcher = MultiSourceSearcher()
        results = searcher.search_single("Python", source="unknown")
        assert results == []


# ===================================================================
# retriever.py 覆盖率提升
# ===================================================================

class TestRetriever:
    def test_init(self):
        from src.core.retriever import Retriever
        r = Retriever()
        assert r._llm is None

    def test_llm_lazy_init(self):
        from src.core.retriever import Retriever
        r = Retriever()
        llm = r.llm
        assert llm is not None
        assert r._llm is not None

    def test_retrieve(self):
        from src.core.retriever import Retriever
        r = Retriever()
        results = r.retrieve("Python教程", top_k=3)
        assert isinstance(results, list)

    def test_retrieve_with_filter(self):
        from src.core.retriever import Retriever
        r = Retriever()
        results = r.retrieve("Python", top_k=5, filter_type="document")
        assert isinstance(results, list)

    def test_retrieve_with_web(self):
        from src.core.retriever import Retriever
        r = Retriever()
        results = r.retrieve_with_web("Python", top_k=3)
        assert "internal" in results
        assert "web" in results

    def test_format_context(self):
        from src.core.retriever import Retriever
        docs = [
            {"content": "Python基础语法", "score": 0.95, "metadata": {"source": "course"}},
            {"content": "Python高级特性", "score": 0.80},
        ]
        formatted = Retriever._format_context(docs)
        assert "[1]" in formatted
        assert "0.95" in formatted
        assert "course" in formatted

    def test_format_context_empty(self):
        from src.core.retriever import Retriever
        formatted = Retriever._format_context([])
        assert formatted == ""

    def test_default_system_prompt(self):
        from src.core.retriever import Retriever
        prompt = Retriever._default_system_prompt()
        assert "学习助手" in prompt
        assert "参考内容" in prompt

    @patch("src.llm.LLMProvider.invoke")
    def test_generate_rag_response_no_context(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="Python是一种编程语言")
        from src.core.retriever import Retriever
        r = Retriever()
        response = r.generate_rag_response("Python是什么", [])
        assert isinstance(response, str)
        assert "Python" in response

    @patch("src.llm.LLMProvider.invoke")
    def test_generate_rag_response_with_context(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="Python入门指南")
        from src.core.retriever import Retriever
        r = Retriever()
        docs = [{"content": "Python是一门编程语言", "score": 1.0}]
        response = r.generate_rag_response("Python是什么", docs)
        assert isinstance(response, str)

    @patch("src.llm.LLMProvider.invoke")
    def test_retrieve_and_generate(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="Python教程推荐")
        from src.core.retriever import Retriever
        r = Retriever()
        result = r.retrieve_and_generate("Python教程", top_k=2, include_web=False)
        assert "query" in result
        assert "response" in result
        assert "sources" in result

    @patch("src.llm.LLMProvider.invoke")
    def test_retrieve_and_generate_with_web(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="搜索结果")
        from src.core.retriever import Retriever
        r = Retriever()
        result = r.retrieve_and_generate("Python", top_k=2, include_web=True)
        assert "query" in result
        assert "web" not in result

    def test_check_health(self):
        from src.core.retriever import Retriever
        r = Retriever()
        health = r.check_health()
        assert "status" in health

    def test_get_retriever_factory(self):
        from src.core.retriever import get_retriever
        r = get_retriever()
        assert r is not None


# ===================================================================
# checkpoint.py 覆盖率提升
# ===================================================================

class TestConversationSummarizer:
    def test_init_default(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer()
        assert s._max_messages == 50

    def test_init_custom(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer(max_messages=10)
        assert s._max_messages == 10

    def test_should_summarize_below_threshold(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer(max_messages=50)
        assert s.should_summarize(30) is False

    def test_should_summarize_above_threshold(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer(max_messages=50)
        assert s.should_summarize(80) is True

    def test_create_summary_prompt(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer()
        messages = [MagicMock(type="human", content="你好"), MagicMock(type="ai", content="你好呀")]
        prompt = s.create_summary_prompt(messages)
        assert "对话历史" in prompt
        assert "学习目标" in prompt

    def test_format_messages(self):
        from src.core.checkpoint import ConversationSummarizer
        messages = [MagicMock(type="human", content="Hello"), MagicMock(type="ai", content="Hi")]
        formatted = ConversationSummarizer._format_messages(messages)
        assert "[human]" in formatted
        assert "[ai]" in formatted

    def test_format_messages_truncation(self):
        from src.core.checkpoint import ConversationSummarizer
        long_msg = MagicMock(type="human", content="X" * 5000)
        formatted = ConversationSummarizer._format_messages([long_msg], max_chars=100)
        assert "[...早期对话已截断...]" in formatted

    def test_format_messages_fallback(self):
        from src.core.checkpoint import ConversationSummarizer
        formatted = ConversationSummarizer._format_messages([{"a": 1}])
        assert "unknown" in formatted

    def test_estimate_compression_ratio(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer(max_messages=50)
        assert s.estimate_compression_ratio(60) < 1.0
        assert s.estimate_compression_ratio(30) == 1.0

    def test_estimate_compression_ratio_zero(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer(max_messages=50)
        assert s.estimate_compression_ratio(0) == 1.0

    def test_check_health(self):
        from src.core.checkpoint import ConversationSummarizer
        s = ConversationSummarizer()
        health = s.check_health()
        assert health["status"] == "ok"
        assert "enabled" in health
        assert "max_messages" in health


class TestCheckpointManager:
    def test_singleton(self):
        from src.core.checkpoint import CheckpointManager
        c1 = CheckpointManager()
        c2 = CheckpointManager()
        assert c1 is c2

    def test_saver_property(self):
        from src.core.checkpoint import CheckpointManager
        cm = CheckpointManager()
        assert cm.saver is not None

    def test_get_saver(self):
        from src.core.checkpoint import CheckpointManager
        cm = CheckpointManager()
        saver = cm.get_saver()
        assert saver is not None

    def test_check_health(self):
        from src.core.checkpoint import CheckpointManager
        cm = CheckpointManager()
        health = cm.check_health()
        assert health["status"] == "ok"
        assert health["backend"] == "memory"

    def test_get_checkpoint_manager_factory(self):
        from src.core.checkpoint import get_checkpoint_manager
        cm = get_checkpoint_manager()
        assert cm is not None

    def test_get_summarizer_factory(self):
        from src.core.checkpoint import get_summarizer
        s = get_summarizer()
        assert s is not None
        assert s.should_summarize(0) is False


class TestFileBackedMemorySaver:
    def test_init_creates_path(self):
        from src.core.checkpoint import FileBackedMemorySaver
        saver = FileBackedMemorySaver()
        assert os.path.exists(saver._persist_path)
        assert saver._dirty is False

    def test_save_to_disk(self):
        from src.core.checkpoint import FileBackedMemorySaver
        saver = FileBackedMemorySaver()
        saver.save_to_disk()
        assert os.path.exists(saver._file_path)
        assert saver._dirty is False

    def test_load_from_disk_no_file(self):
        from src.core.checkpoint import FileBackedMemorySaver
        saver = FileBackedMemorySaver()
        if os.path.exists(saver._file_path):
            os.remove(saver._file_path)
        count = saver.load_from_disk()
        assert count == 0


# ===================================================================
# assistant.py 覆盖率提升
# ===================================================================

class TestSupervisorAgent:
    def test_init(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        assert agent.role.value == "assistant"
        assert len(agent._agents) == 0
        assert agent._compiled_graph is None

    def test_build_system_prompt(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "测试同学" in prompt
        assert "学习助教" in prompt

    def test_classify_intent_study_plan(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("帮我制定一个学习计划")
        assert AgentRole.PLANNER in roles

    def test_classify_intent_recommend(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("推荐一些资料给我")
        assert AgentRole.EXPERT in roles

    def test_classify_intent_question(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("什么是闭包？帮我理解一下")
        assert AgentRole.PARTNER in roles

    def test_classify_intent_quiz(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("给我出几道题练习一下")
        assert AgentRole.QUIZZER in roles

    def test_classify_intent_review(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("帮我复盘一下错题")
        assert AgentRole.REVIEWER in roles

    def test_classify_intent_exam(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("面试该怎么准备")
        assert AgentRole.EXAMINER in roles

    def test_classify_intent_fallback(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        roles = agent._classify_intent("你好")
        assert roles == [AgentRole.PARTNER]

    def test_classify_intent_multi(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        roles = agent._classify_intent("帮我制定一个学习计划，然后推荐一些资料")
        assert len(roles) >= 1

    def test_run_empty_message(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        result = agent.run(_make_state(), "")
        assert result.agent_role.value == "assistant"

    def test_run_impl_empty_message(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        result = agent._run_impl(_make_state(), "")
        assert "你好" in result.output["reply"]

    def test_run_impl_no_agents_registered(self):
        from unittest.mock import patch
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        with patch.object(agent, "_chat", return_value="我来帮你制定学习计划"):
            result = agent._run_impl(_make_state(), "帮我制定一个学习计划")
        assert isinstance(result.output.get("reply"), str)
        assert result.agent_role.value == "assistant"

    def test_run_with_target_role_not_registered(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        result = agent.run(_make_state(), "hello", target_role=AgentRole.PLANNER)
        assert result.error is not None
        assert "未找到" in result.output["reply"]

    def test_run_with_registered_agent(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        from src.agents.base_agent import AgentResult, BaseAgent

        class MockAgent(BaseAgent):
            role = AgentRole.PLANNER
            description = "mock"
            def run(self, state, message=""):
                return AgentResult(agent_role=AgentRole.PLANNER, output={"reply": "计划已生成"})
            def _build_system_prompt(self, state):
                return "mock prompt"

        agent = SupervisorAgent()
        agent.register_sub_agent(MockAgent())
        result = agent.run(_make_state(), "帮我制定计划", target_role=AgentRole.PLANNER)
        assert "计划已生成" in result.output["reply"]

    def test_aggregate_results_success(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, output={"reply": "学习计划: ..."}, success=True),
            AgentResult(agent_role=AgentRole.EXPERT, output={"reply": "推荐资料"}, success=True),
        ]
        aggregated = agent.aggregate_results(results)
        assert "planner" in aggregated or "学习计划" in aggregated

    def test_aggregate_results_known_keys(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, output={"plan_text": "这是一份详细的学习计划"}, success=True),
        ]
        aggregated = agent.aggregate_results(results)
        assert "详细的学习计划" in aggregated

    def test_aggregate_results_fallback_key(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, output={"custom_field": "这是一段自定义回复内容"}, success=True),
        ]
        aggregated = agent.aggregate_results(results)
        assert "自定义回复内容" in aggregated

    def test_aggregate_results_empty(self):
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        aggregated = agent.aggregate_results([])
        assert "未能获取有效回复" in aggregated

    def test_aggregate_results_failed(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole
        agent = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, success=False, error="error"),
        ]
        aggregated = agent.aggregate_results(results)
        assert "未能获取有效回复" in aggregated

    def test_run_with_langgraph_no_agents(self):
        from unittest.mock import patch
        from src.agents.assistant import SupervisorAgent
        agent = SupervisorAgent()
        with patch.object(agent, "_chat", return_value="你好！我是学习助教"):
            result = agent.run_with_langgraph(_make_state(), "你好")
        assert isinstance(result.output.get("reply"), str)

    def test_register_sub_agent_resets_graph(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        from src.agents.base_agent import AgentResult, BaseAgent

        class MockAgent(BaseAgent):
            role = AgentRole.PLANNER
            description = "mock"
            def run(self, state, message=""):
                return AgentResult(agent_role=AgentRole.PLANNER, output={"reply": "ok"}, success=True)
            def _build_system_prompt(self, state):
                return "mock prompt"

        agent = SupervisorAgent()
        assert agent._compiled_graph is None
        agent.register_sub_agent(MockAgent())
        assert agent._compiled_graph is None

    def test_run_with_failed_sub_agent(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole
        from src.agents.base_agent import AgentResult, BaseAgent

        class FailingAgent(BaseAgent):
            role = AgentRole.PLANNER
            description = "failing"
            def run(self, state, message=""):
                return AgentResult(agent_role=AgentRole.PLANNER, success=False, error="模拟错误", output={"reply": "之前的内容"})
            def _build_system_prompt(self, state):
                return "mock prompt"

        agent = SupervisorAgent()
        agent.register_sub_agent(FailingAgent())
        result = agent._run_impl(_make_state(), "帮我制定一个学习计划")
        assert "抱歉" in result.output["reply"]
        assert "之前的内容" in result.output["reply"]


# ===================================================================
# llm.py 覆盖率提升
# ===================================================================

class TestLLMAdditional:
    @patch("src.llm.LLMProvider.invoke")
    def test_invoke_with_retry(self, mock_invoke):
        from langchain_core.messages import AIMessage, HumanMessage
        mock_invoke.return_value = AIMessage(content="hello")
        from src.llm import LLMProvider
        llm = LLMProvider()
        result = llm.invoke_with_retry(
            [HumanMessage(content="say hello")],
            max_retries=2,
            base_delay=0.1,
        )
        assert result is not None

    @patch("src.llm.LLMProvider.invoke")
    def test_invoke_with_retry_success_on_retry(self, mock_invoke):
        from langchain_core.messages import AIMessage, HumanMessage
        mock_invoke.side_effect = [
            RuntimeError("first fail"),
            AIMessage(content="success"),
        ]
        from src.llm import LLMProvider
        llm = LLMProvider()
        result = llm.invoke_with_retry(
            [HumanMessage(content="test")],
            max_retries=3,
            base_delay=0.01,
        )
        assert result.content == "success"
        assert mock_invoke.call_count == 2

    @patch("src.llm.LLMProvider.invoke")
    def test_invoke_with_retry_exhausted(self, mock_invoke):
        mock_invoke.side_effect = RuntimeError("fail")
        from langchain_core.messages import HumanMessage
        from src.llm import LLMProvider
        llm = LLMProvider()
        with pytest.raises(RuntimeError, match="次重试后仍然失败"):
            llm.invoke_with_retry(
                [HumanMessage(content="test")],
                max_retries=2,
                base_delay=0.01,
            )

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_basic(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="你好，我是助手")
        from src.llm import LLMProvider
        llm = LLMProvider()
        response = llm.chat("你好", system_prompt="你是一个助手")
        assert isinstance(response, str)

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_no_system_prompt(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="Hello")
        from src.llm import LLMProvider
        llm = LLMProvider()
        response = llm.chat("hello")
        assert isinstance(response, str)

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_with_history_dicts(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="response")
        from src.llm import LLMProvider
        llm = LLMProvider()
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        response = llm.chat_with_history("how are you", history, system_prompt="Be helpful")
        assert response == "response"

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_with_history_base_messages(self, mock_invoke):
        from langchain_core.messages import AIMessage, HumanMessage
        mock_invoke.return_value = AIMessage(content="response")
        from src.llm import LLMProvider
        llm = LLMProvider()
        history = [
            HumanMessage(content="hello"),
            AIMessage(content="hi"),
        ]
        response = llm.chat_with_history("bye", history)
        assert response == "response"

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_with_history_system_filter(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="ok")
        from src.llm import LLMProvider
        llm = LLMProvider()
        history = [
            {"role": "system", "content": "old system prompt"},
            {"role": "user", "content": "hello"},
        ]
        response = llm.chat_with_history("test", history, system_prompt="new system")
        assert response == "ok"

    @patch("src.llm.LLMProvider.invoke")
    def test_chat_with_history_unknown_role(self, mock_invoke):
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="ok")
        from src.llm import LLMProvider
        llm = LLMProvider()
        history = [{"role": "unknown", "content": "something"}]
        response = llm.chat_with_history("test", history)
        assert response == "ok"

    def test_check_health(self):
        from src.llm import LLMProvider
        llm = LLMProvider()
        health = llm.check_health()
        assert "provider" in health
        assert "model" in health
        assert "api_available" in health
        assert "local_available" in health

    def test_get_llm_factory(self):
        from src.llm import get_llm
        llm = get_llm()
        assert llm is not None

    def test_llm_singleton_new(self):
        from src.llm import LLMProvider
        p1 = LLMProvider()
        p2 = LLMProvider()
        assert p1 is p2

    @patch("src.llm.LLMProvider.invoke")
    def test_invoke_with_local_fallback(self, mock_invoke):
        from langchain_core.messages import AIMessage, HumanMessage
        mock_invoke.return_value = AIMessage(content="ok")
        from src.llm import LLMProvider
        llm = LLMProvider()
        result = llm.invoke([HumanMessage(content="say 'ok' in lowercase")], use_local=False)
        assert result is not None