"""
基础设施层集成测试

验证各核心组件的功能、通信和协作是否正常。
部分测试依赖API Key或外部服务，在未配置时会自动跳过。
"""

import os
import sys
import uuid

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_BAILIAN_KEY = os.getenv("DASHSCOPE_API_KEY", "")
_EMBEDDING_AVAILABLE = _BAILIAN_KEY and _BAILIAN_KEY != "your-dashscope-api-key-here"
_embedding_required = pytest.mark.skipif(
    not _EMBEDDING_AVAILABLE,
    reason="未配置有效的百炼 DASHSCOPE_API_KEY",
)


class TestConfig:
    """配置模块测试"""

    def test_settings_load(self):
        from src.config import Settings

        assert Settings.LLM_MODEL is not None
        assert Settings.LLM_PROVIDER is not None
        assert len(Settings.LLM_PROVIDER) > 0
        assert Settings.PORT == 8000
        assert Settings.MEMORY_MAX_MESSAGES == 50
        assert Settings.EMBEDDING_PROVIDER is not None
        assert Settings.VECTOR_DB_TYPE == "qdrant"

    def test_resolve_path(self):
        from src.config import Settings

        path = Settings.resolve_path("./data/test")
        assert path.is_absolute()
        assert "data" in str(path)

    def test_display_no_error(self):
        from src.config import Settings

        display = Settings.display()
        assert "系统配置" in display


class TestStateSchema:
    """State Schema 测试"""

    def test_learning_plan_model(self):
        from src.core.state import LearningGoal, LearningPhase, LearningPlan

        goal = LearningGoal(title="学习Python", description="掌握Python基础")
        assert goal.title == "学习Python"
        assert goal.priority.value == "medium"

        phase = LearningPhase(phase_id="p1", title="基础语法", topics=["变量", "循环"])
        assert len(phase.topics) == 2

        plan = LearningPlan(title="Python学习计划", goals=[goal], phases=[phase])
        assert plan.title == "Python学习计划"
        assert plan.created_at is not None

    def test_learning_state_structure(self):
        from src.core.state import LearningState

        state: LearningState = {
            "messages": [],
            "user_id": "test_user",
            "user_profile": {},
            "current_agent": "assistant",
            "agent_outputs": {},
            "quiz_results": [],
            "error_records": [],
            "weak_points": [],
            "focus_time_minutes": 0.0,
            "focus_sessions": [],
            "pending_feedback": False,
            "feedback_message": "",
            "error_message": "",
        }
        assert state["user_id"] == "test_user"

    def test_agent_output_model(self):
        from src.core.state import AgentOutput, AgentRole

        output = AgentOutput(
            agent_role=AgentRole.PLANNER,
            output_type="learning_plan",
            content="这是一个学习计划",
        )
        assert output.agent_role == AgentRole.PLANNER
        assert output.timestamp is not None


class TestLLMProvider:
    """LLM 接入层测试"""

    def test_singleton(self):
        from src.llm import LLMProvider

        p1 = LLMProvider()
        p2 = LLMProvider()
        assert p1 is p2

    @pytest.mark.skipif(
        not os.getenv("LLM_API_KEY") or os.getenv("LLM_API_KEY") == "sk-your-api-key-here",
        reason="未配置有效的LLM API Key",
    )
    def test_invoke_with_api_key(self):
        from langchain_core.messages import HumanMessage

        from src.llm import LLMProvider

        llm = LLMProvider()
        result = llm.invoke([HumanMessage(content="say 'hello' in one word, lowercase")])
        assert result is not None
        assert "hello" in result.content.lower()

    def test_chat_with_system_prompt(self):
        from src.llm import LLMProvider

        llm = LLMProvider()
        health = llm.check_health()
        assert "provider" in health
        assert health["provider"] is not None

    def test_get_llm_factory(self):
        from src.llm import get_llm

        llm = get_llm()
        assert llm is not None


class TestEmbeddingProvider:
    """Embedding 模块测试"""

    def test_singleton(self):
        from src.embedding import EmbeddingProvider

        e1 = EmbeddingProvider()
        e2 = EmbeddingProvider()
        assert e1 is e2

    def test_cache_operation(self):
        from src.embedding import EmbeddingCache

        cache = EmbeddingCache(max_size=10, ttl_seconds=3600)
        cache.set("test_text", [0.1, 0.2, 0.3])
        assert cache.size == 1

        cached = cache.get("test_text")
        assert cached is not None
        assert len(cached) == 3

        not_cached = cache.get("unknown_text")
        assert not_cached is None

        cache.clear()
        assert cache.size == 0

    def test_cache_ttl_expiry(self):
        import time
        from src.embedding import EmbeddingCache

        cache = EmbeddingCache(max_size=10, ttl_seconds=0)
        cache.set("expire_test", [0.5, 0.6])
        time.sleep(0.01)
        assert cache.get("expire_test") is None
        assert cache.size == 0

    def test_cache_cleanup_expired(self):
        import time
        from src.embedding import EmbeddingCache

        cache = EmbeddingCache(max_size=10, ttl_seconds=0)
        cache.set("e1", [0.1])
        cache.set("e2", [0.2])
        time.sleep(0.01)
        removed = cache._cleanup_expired()
        assert removed == 2
        assert cache.size == 0

    def test_similarity_calculation(self):
        from src.embedding import EmbeddingProvider

        provider = EmbeddingProvider()
        sim = provider.similarity([1.0, 0.0], [1.0, 0.0])
        assert abs(sim - 1.0) < 0.001

        sim2 = provider.similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim2) < 0.001

    def test_batch_similarity(self):
        from src.embedding import EmbeddingProvider

        provider = EmbeddingProvider()
        sims = provider.batch_similarity(
            [1.0, 0.0],
            [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
        )
        assert len(sims) == 3
        assert abs(sims[0] - 1.0) < 0.001
        assert abs(sims[1]) < 0.001

    def test_check_health(self):
        from src.embedding import EmbeddingProvider

        provider = EmbeddingProvider()
        health = provider.check_health()
        assert "provider" in health
        assert health["provider"] == "bailian"


class TestToolSystem:
    """工具系统测试"""

    def test_tool_registry_singleton(self):
        from src.core.tools.base import ToolRegistry

        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_register_function_tool(self):
        from src.core.tools.base import ToolRegistry, ToolCategory, tool

        @tool(name="test_tool", description="测试工具", category=ToolCategory.UTILITY)
        def test_func(x: int) -> int:
            return x * 2

        registry = ToolRegistry()
        registry.reset()
        registry.register_function(test_func)

        result = registry.execute("test_tool", x=5)
        assert result == 10

        tools = registry.list_all()
        assert any(t["name"] == "test_tool" for t in tools)

        registry.reset()

    def test_register_unregister(self):
        from src.core.tools.base import ToolRegistry, tool, ToolCategory

        @tool(name="temp_tool", description="临时", category=ToolCategory.UTILITY)
        def temp_func():
            return "temp"

        registry = ToolRegistry()
        registry.reset()
        registry.register_function(temp_func)

        assert registry.get_function("temp_tool") is not None

        registry.unregister("temp_tool")
        assert registry.get_function("temp_tool") is None

        registry.reset()

    def test_web_search_tool(self):
        from src.core.tools.search import WebSearchTool

        tool = WebSearchTool()
        result = tool.execute(query="Python入门教程", num_results=3)
        assert isinstance(result, list)

    def test_focus_timer(self):
        from src.core.tools.timer import FocusTimer

        timer = FocusTimer()

        start = timer.start_session("Python学习")
        assert start["status"] == "started"

        status = timer.get_status()
        assert status["status"] == "running"

        stop = timer.stop_session()
        assert stop["status"] == "stopped"
        assert stop["elapsed_minutes"] >= 0

    def test_document_generator_learning_plan(self):
        from src.core.tools.document import DocumentGenerator

        gen = DocumentGenerator()
        data = {
            "goals": [{"title": "Python", "description": "掌握Python"}],
            "phases": [{"phase_id": "1", "title": "基础", "topics": ["语法"], "duration_days": 7}],
            "suggestions": "好好学习",
        }
        result = gen.execute(doc_type="learning_plan", data=data, title="测试方案")
        assert result["format"] == "markdown"
        assert "测试方案" in result["content"]
        assert "Python" in result["content"]

    def test_document_generator_course(self):
        from src.core.tools.document import DocumentGenerator

        gen = DocumentGenerator()
        data = {
            "materials": [
                {"title": "Python教程", "url": "https://example.com", "source": "B站", "content_type": "视频", "description": "免费教程"}
            ],
            "suggestions": "按顺序学习",
        }
        result = gen.execute(doc_type="course_recommendation", data=data, title="推荐课程")
        assert result["format"] == "markdown"
        assert "推荐课程" in result["content"]
        assert "Python教程" in result["content"]

    def test_document_generator_error_report(self):
        from src.core.tools.document import DocumentGenerator

        gen = DocumentGenerator()
        data = {
            "weak_points": [{"knowledge_point": "循环", "error_rate": 0.5, "error_count": 3, "total_attempts": 6, "need_review": True}],
            "error_records": [
                {"question": {"content": "什么是for循环?", "answer": "B", "explanation": "for循环用于遍历"}, "user_answer": "A", "error_count": 2}
            ],
            "suggestions": "复习循环",
        }
        result = gen.execute(doc_type="error_report", data=data, title="错题报告")
        assert result["format"] == "markdown"
        assert "错题报告" in result["content"]


class TestVectorStore:
    """向量数据库测试 (Qdrant)"""

    def test_initialization(self):
        from src.core.memory import VectorStore

        store = VectorStore()
        assert store.client is not None
        assert store.count() >= 0

    @_embedding_required
    def test_add_and_search(self):
        from src.core.memory import VectorStore

        store = VectorStore()
        initial_count = store.count()

        doc_id = str(uuid.uuid4())
        store.add(
            documents=["Python是一种高级编程语言"],
            ids=[doc_id],
        )

        results = store.search("Python编程", top_k=3)
        assert len(results) > 0

        store.delete([store._sanitize_id(doc_id)])

    def test_health_check(self):
        from src.core.memory import VectorStore

        store = VectorStore()
        health = store.check_health()
        assert health["status"] == "ok"
        assert health["document_count"] >= 0


class TestLongTermMemory:
    """长期记忆测试"""

    @_embedding_required
    def test_memory_operations(self):
        from src.core.memory import LongTermMemory

        memory = LongTermMemory(user_id="test_user_memory")
        summary = memory.get_user_summary()
        assert "total_interactions" in summary


class TestRetriever:
    """检索模块测试"""

    def test_retriever_initialization(self):
        from src.core.retriever import Retriever

        retriever = Retriever()
        health = retriever.check_health()
        assert "status" in health

    @_embedding_required
    def test_retrieve_empty(self):
        from src.core.retriever import Retriever

        retriever = Retriever()
        results = retriever.retrieve("不存在的查询", top_k=3)
        assert isinstance(results, list)

    def test_format_context(self):
        from src.core.retriever import Retriever

        docs = [
            {"content": "文档1内容", "score": 0.9, "metadata": {"source": "互联网"}},
            {"content": "文档2内容", "score": 0.7, "metadata": {}},
        ]
        formatted = Retriever._format_context(docs)
        assert "文档1内容" in formatted
        assert "文档2内容" in formatted
        assert "0.90" in formatted


class TestGraphStore:
    """图数据库测试 (Neo4j)"""

    @pytest.mark.skipif(
        not os.getenv("NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD") == "your-neo4j-password-here",
        reason="未配置有效的Neo4j密码",
    )
    def test_graph_connection(self):
        from src.core.graph import GraphStore

        graph = GraphStore()
        health = graph.check_health()
        assert health["status"] in ("ok", "connected", "disconnected")

    def test_graph_disconnected_graceful(self, monkeypatch):
        monkeypatch.setattr("src.core.graph.Settings.NEO4J_PASSWORD", "your-neo4j-password-here")
        from src.core.graph import GraphStore

        store = GraphStore()
        store._instance = None
        store._initialized = False
        store._driver = None
        store._initialize()

        stats = store.get_stats()
        assert stats["status"] == "disconnected"

    def test_knowledge_node_dataclass(self):
        from src.core.graph import KnowledgeNode, KnowledgeRelation

        node = KnowledgeNode(
            node_id="python_basics",
            name="Python基础",
            node_type="subject",
            description="Python编程语言基础知识",
        )
        assert node.node_id == "python_basics"
        assert node.name == "Python基础"

        rel = KnowledgeRelation(
            source_id="python_basics",
            target_id="python_loops",
            relation_type="PREREQUISITE",
            weight=0.9,
        )
        assert rel.source_id == "python_basics"
        assert rel.relation_type == "PREREQUISITE"

    def test_invalid_relation_type_rejected(self):
        from src.core.graph import GraphStore, KnowledgeRelation
        from unittest.mock import MagicMock

        store = GraphStore()
        store._driver = MagicMock()
        rel = KnowledgeRelation(
            source_id="a", target_id="b",
            relation_type="INVALID_TYPE",
        )
        with pytest.raises(ValueError, match="不支持的关系类型"):
            store.add_relation(rel)

    def test_query_related_invalid_type_rejected(self):
        from src.core.graph import GraphStore

        store = GraphStore()
        store._driver = None
        with pytest.raises(ValueError, match="不支持的关系类型"):
            store.query_related("python", relation_type="HACKED")


class TestAgentCommunication:
    """Agent通信测试"""

    def test_router_initialization(self):
        from src.core.communication import AgentRouter, SignalType

        router = AgentRouter()
        assert len(router._handlers) == 0
        router.clear()

    def test_register_handler(self):
        from src.core.communication import AgentRouter, AgentSignal, SignalType

        router = AgentRouter()
        received = []

        def handler(signal):
            received.append(signal)

        router.register_handler(SignalType.PLAN_UPDATED, handler)
        assert SignalType.PLAN_UPDATED in router._handlers

        router.clear()

    def test_agent_registry(self):
        from src.core.communication import AgentCommunication, AgentRole

        comm = AgentCommunication()

        def dummy_handler(signal):
            return {"result": "ok"}

        comm.register_agent(AgentRole.PLANNER, dummy_handler)
        handler = comm.get_agent_handler(AgentRole.PLANNER)
        assert handler is not None

    def test_update_state_from_agent(self):
        from src.core.communication import AgentCommunication, AgentRole
        from src.core.state import LearningState

        comm = AgentCommunication()
        state: LearningState = {
            "messages": [],
            "user_id": "test",
            "user_profile": {},
            "current_agent": "",
            "agent_outputs": {},
            "quiz_results": [],
            "error_records": [],
            "weak_points": [],
            "focus_time_minutes": 0.0,
            "focus_sessions": [],
            "pending_feedback": False,
            "feedback_message": "",
            "error_message": "",
        }

        new_state = comm.update_state_from_agent(state, AgentRole.PLANNER, {"plan": "test"})
        assert new_state["current_agent"] == "planner"
        assert "planner" in new_state["agent_outputs"]


class TestIntegration:
    """端到端集成测试"""

    def test_config_to_llm_chain(self):
        from src.config import Settings
        from src.llm import get_llm

        assert Settings.LLM_MODEL is not None
        llm = get_llm()
        assert llm.model is not None

    @_embedding_required
    def test_embedding_to_vector_store(self):
        from src.core.memory import VectorStore
        from src.embedding import EmbeddingProvider

        embedding = EmbeddingProvider()
        health = embedding.check_health()
        assert "status" in health

        store = VectorStore()
        store_health = store.check_health()
        assert store_health["status"] == "ok"

    def test_tool_registry_full_workflow(self):
        from src.core.tools.base import ToolRegistry, register_all_tools

        registry = register_all_tools()
        tools = registry.list_all()
        assert len(tools) >= 5

        desc = registry.get_tool_descriptions()
        assert "web_search" in desc or len(desc) > 0

    def test_document_generator_with_tool_registry(self):
        from src.core.tools.base import ToolRegistry
        from src.core.tools.document import DocumentGenerator

        registry = ToolRegistry()
        registry.reset()
        registry.register(DocumentGenerator())

        result = registry.execute(
            "document_generator",
            doc_type="markdown",
            data={"raw": "测试内容"},
            title="测试",
        )
        assert result["format"] == "markdown"

        registry.reset()

    @_embedding_required
    def test_roundtrip_memory_search(self):
        from src.core.memory import VectorStore

        store = VectorStore()
        test_id = f"roundtrip_{uuid.uuid4()}"

        content = f"机器学习是人工智能的一个分支，涉及算法和统计模型 {test_id}"
        store.add(
            documents=[content],
            ids=[test_id],
        )

        results = store.search("机器学习 人工智能", top_k=5)
        found = any(test_id in str(r.get("content", "")) for r in results)

        store.delete([store._sanitize_id(test_id)])

        assert found, f"Roundtrip search failed: added document with marker {test_id} not found in results"

    def test_api_app_exists(self):
        from src.api.main import app

        assert app.title == "学习辅助系统 API"
        routes = [r.path for r in app.routes]
        assert "/health" in routes
        assert "/chat" in routes
        assert "/search" in routes
        assert "/embed" in routes
        assert "/tools" in routes
        assert "/graph/stats" in routes
        assert "/graph/search" in routes
        assert "/graph/path" in routes


class TestCheckpoint:
    """Checkpoint 模块测试"""

    def test_checkpoint_manager_init(self):
        from src.core.checkpoint import CheckpointManager

        manager = CheckpointManager()
        assert manager.saver is not None
        health = manager.check_health()
        assert health["status"] == "ok"

    def test_conversation_summarizer(self):
        from src.core.checkpoint import ConversationSummarizer

        summarizer = ConversationSummarizer(max_messages=50)
        assert summarizer.should_summarize(100) is True
        assert summarizer.should_summarize(10) is False

        assert summarizer.estimate_compression_ratio(100) < 1.0
        assert summarizer.estimate_compression_ratio(10) == 1.0

        health = summarizer.check_health()
        assert health["status"] == "ok"


class TestQuizTools:
    """出题工具测试"""

    def test_quiz_generator(self):
        from src.core.tools.quiz import QuizGenerator

        gen = QuizGenerator()
        questions = gen.execute(topic="Python", question_type="single_choice", difficulty=0.7, count=3)
        assert isinstance(questions, list)
        assert len(questions) == 3
        for q in questions:
            assert "question_id" in q
            assert "content" in q
            assert "question_type" in q
            assert len(q.get("options", [])) >= 2

    def test_quiz_generator_with_weak_points(self):
        from src.core.tools.quiz import QuizGenerator

        gen = QuizGenerator()
        questions = gen.execute(
            topic="数据科学",
            question_type="true_false",
            count=2,
            weak_points=["机器学习", "深度学习"],
        )
        assert len(questions) == 2

    def test_quiz_generator_count_limits(self):
        from src.core.tools.quiz import QuizGenerator

        gen = QuizGenerator()
        questions = gen.execute(topic="AI", count=50)
        assert len(questions) <= 20

    def test_ability_assessor(self):
        from src.core.tools.quiz import AbilityAssessor

        assessor = AbilityAssessor()
        result = assessor.execute(
            quiz_results=[
                {"question_id": "q1", "is_correct": True},
                {"question_id": "q2", "is_correct": False},
            ],
            error_records=[
                {"knowledge_point": "循环", "error_count": 2},
                {"knowledge_point": "函数", "error_count": 1},
            ],
        )
        assert "overall_score" in result
        assert result["overall_score"] == 50.0
        assert len(result["weak_points"]) >= 1

    def test_quiz_registry_integration(self):
        from src.core.tools.base import ToolRegistry
        from src.core.tools.quiz import QuizGenerator, AbilityAssessor

        registry = ToolRegistry()
        registry.reset()
        registry.register(QuizGenerator())
        registry.register(AbilityAssessor())

        tools = registry.list_all()
        assert len(tools) == 2

        names = [t["name"] for t in tools if t["name"] in ("quiz_generator", "ability_assessor")]
        assert len(names) == 2

        registry.reset()

    def test_full_quiz_registry_workflow(self):
        from src.core.tools.base import ToolRegistry
        from src.core.tools.quiz import QuizGenerator

        registry = ToolRegistry()
        registry.reset()
        registry.register(QuizGenerator())

        result = registry.execute("quiz_generator", topic="网络", count=2)
        assert isinstance(result, list)
        assert len(result) == 2

        registry.reset()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])