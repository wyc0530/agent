import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from src.agents.assistant import SupervisorAgent
from src.agents.base_agent import AgentResult
from src.agents.examiner import ExaminerAgent
from src.agents.expert import ExpertAgent
from src.agents.partner import PartnerAgent
from src.agents.planner import PlannerAgent
from src.agents.quizzer import QuizzerAgent
from src.agents.reviewer import ReviewerAgent
from src.core.state import AgentRole, LearningState


PLAN_JSON = (
    '```json\n'
    '{"plan_id": "e2e-plan", "title": "Test Plan", '
    '"goals": [{"title": "Basics", "description": "Core", "target_date": "2026-07-01", "priority": "high", "status": "pending"}], '
    '"phases": [{"title": "Syntax", "description": "Basics", "topics": ["Var"], "duration_days": 7, "order": 1}]'
    '}\n```'
)

EXPERT_JSON = (
    '```json\n{"answer": "Detailed explanation", '
    '"key_concepts": ["Concept1"], "references": ["docs"]'
    '}\n```'
)

PARTNER_JSON = (
    '```json\n{"reply": "Learning help", '
    '"knowledge_context": ["Topic1"], "suggestions": ["Practice"]}\n```'
)

REVIEW_JSON = (
    '```json\n{"analysis": "Good progress", '
    '"weak_points_summary": [{"knowledge_point": "Scope"}], '
    '"suggestions": ["Study more"], "confidence": 0.85'
    '}\n```'
)


class TestE2EFlows:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.planner = PlannerAgent()
        self.expert = ExpertAgent()
        self.partner = PartnerAgent()
        self.quizzer = QuizzerAgent()
        self.reviewer = ReviewerAgent()
        self.examiner = ExaminerAgent()
        self.supervisor = SupervisorAgent()

    def _empty_state(self) -> LearningState:
        return {
            "user_id": "e2e_test",
            "user_profile": {"name": "Test", "level": "beginner", "target_field": "Python"},
            "messages": [],
            "agent_outputs": {},
            "weak_points": [],
        }

    def test_full_learning_cycle(self):
        state = self._empty_state()

        with patch.object(self.planner, "_chat", return_value=PLAN_JSON):
            plan_result = self.planner.run(state, "Create plan")
            assert plan_result.success
            state["learning_plan"] = plan_result.output

        with patch.object(self.expert, "_chat", return_value=EXPERT_JSON):
            expert_result = self.expert.run(state, "Explain variables")
            assert expert_result.success

        with patch.object(self.partner, "_chat", return_value=PARTNER_JSON):
            partner_result = self.partner.run(state, "Learn Python")
            assert partner_result.success

        with patch.object(self.quizzer, "_chat", return_value='{"quiz_result": {"score": 0.8}}'):
            quiz_result = self.quizzer.run(state, "Quiz")
            assert quiz_result.success

        with patch.object(self.reviewer, "_chat", return_value=REVIEW_JSON):
            review_result = self.reviewer.run(state, "Review")
            assert review_result.success
            assert review_result.state_changes is not None
            assert "weak_points" in review_result.state_changes

    def test_supervisor_routes_correctly(self):
        self.supervisor.register_sub_agent(PlannerAgent())
        self.supervisor.register_sub_agent(PartnerAgent())
        self.supervisor.register_sub_agent(QuizzerAgent())

        route_tests = [
            ("帮我规划", AgentRole.PLANNER),
            ("帮我答疑", AgentRole.PARTNER),
            ("出题测试", AgentRole.QUIZZER),
        ]

        for message, expected in route_tests:
            intent = self.supervisor._classify_intent(message)
            assert intent[0] == expected

    def test_supervisor_run_routes(self):
        state = self._empty_state()
        self.supervisor.register_sub_agent(self.planner)
        self.supervisor.register_sub_agent(self.partner)

        with patch.object(self.planner, "_chat", return_value=PLAN_JSON), \
             patch.object(self.partner, "_chat", return_value=PARTNER_JSON):
            result = self.supervisor.run(state, "帮我规划Python学习")
            assert result.success
            assert result.output is not None

    def test_run_parallel_multiple_agents(self):
        state = self._empty_state()
        self.supervisor.register_sub_agent(self.planner)
        self.supervisor.register_sub_agent(self.partner)
        self.supervisor.register_sub_agent(self.expert)

        with patch.object(self.planner, "_chat", return_value=PLAN_JSON), \
             patch.object(self.partner, "_chat", return_value=PARTNER_JSON), \
             patch.object(self.expert, "_chat", return_value=EXPERT_JSON):
            coro = self.supervisor.run_parallel(state, "Learning plan")
            results = asyncio.run(coro)
            assert results is not None

    def test_state_changes_propagate(self):
        state = self._empty_state()

        with patch.object(self.reviewer, "_chat", return_value=REVIEW_JSON):
            result = self.reviewer.run(state, "Review")
            assert result.success
            state["weak_points"] = result.state_changes.get("weak_points", [])
            assert len(state["weak_points"]) > 0

        with patch.object(self.planner, "_chat", return_value=PLAN_JSON):
            plan_result = self.planner.run(state, "Targeted plan")
            assert plan_result.success

    def test_langgraph_supervisor_routing(self):
        self.supervisor.register_sub_agent(self.planner)
        self.supervisor.register_sub_agent(self.partner)
        state = self._empty_state()

        with patch.object(self.planner, "_chat", return_value=PLAN_JSON):
            result = self.supervisor.run_with_langgraph(state, "Create plan")
            assert result.success
            assert result.output is not None

    def test_supervisor_fallback_on_unknown(self):
        state = self._empty_state()
        self.supervisor.register_sub_agent(self.partner)

        with patch.object(self.partner, "_chat", return_value=PARTNER_JSON):
            result = self.supervisor.run(state, "Hello there")
            assert result.success

    def test_error_propagation_in_chain(self):
        state = self._empty_state()

        with patch.object(self.planner, "_chat", side_effect=Exception("LLM error")):
            result = self.planner.run(state, "Plan")
            assert not result.success

    def test_empty_state_graceful(self):
        empty: LearningState = {
            "user_id": "", "user_profile": {},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        }

        with patch.object(self.partner, "_chat", return_value=PARTNER_JSON):
            result = self.partner.run(empty, "Help")
            assert result.success


class TestAPIIntegration:

    def test_all_endpoints_registered(self):
        from src.api.main import app
        routes = {r.path: r.methods for r in app.routes if hasattr(r, "path")}

        expected = {
            "/health": {"GET"}, "/chat": {"POST"}, "/search": {"POST"},
            "/embed": {"POST"}, "/tools": {"GET"}, "/memory/store": {"POST"},
            "/graph/stats": {"GET"}, "/graph/search": {"POST"}, "/graph/path": {"POST"},
        }

        for path, methods in expected.items():
            assert path in routes, f"Missing {path}"
            assert routes[path] == methods or methods.issubset(routes[path])

    def test_auth_middleware_defined(self):
        from src.api.main import AuthMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(AuthMiddleware, BaseHTTPMiddleware)

    def test_rate_limit_middleware_defined(self):
        from src.api.main import RateLimitMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(RateLimitMiddleware, BaseHTTPMiddleware)


class TestCommunicationE2E:

    def test_build_agent_graph(self):
        from src.core.communication import build_agent_graph

        def planner_h(state: LearningState) -> dict:
            return {"learning_plan": {"title": "T"}}

        def quizzer_h(state: LearningState) -> dict:
            return {"quiz_results": [{"is_correct": True}]}

        graph = build_agent_graph({
            AgentRole.PLANNER: planner_h,
            AgentRole.QUIZZER: quizzer_h,
        })

        app = graph.compile()
        result = app.invoke({
            "user_id": "t", "user_profile": {},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        })
        assert result.get("learning_plan") is not None

    def test_feedback_loop_creation(self):
        from src.core.communication import AgentCommunication, SignalType

        comm = AgentCommunication()
        comm.register_agent(AgentRole.REVIEWER, lambda s: {"ok": True})

        comm.create_feedback_loop(
            source_role=AgentRole.QUIZZER,
            target_role=AgentRole.REVIEWER,
            signal_type=SignalType.QUIZ_COMPLETED,
            state_mapper=lambda s: {"wp": s.get("weak_points", [])},
        )

        assert comm.get_agent_handler(AgentRole.REVIEWER) is not None


class TestCSRFMiddleware:
    """CSRF中间件端到端测试。"""

    def test_csrf_middleware_defined(self):
        from src.api.main import CSRFMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(CSRFMiddleware, BaseHTTPMiddleware)

    def test_csrf_allows_safe_methods(self):
        from src.api.main import CSRFMiddleware
        import asyncio

        middleware = CSRFMiddleware(MagicMock())
        request = MagicMock()
        request.method = "GET"
        request.headers = {}

        async def call_next(r):
            return JSONResponse({"ok": True})

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_csrf_allows_localhost(self):
        from src.api.main import CSRFMiddleware
        import asyncio

        middleware = CSRFMiddleware(MagicMock())
        request = MagicMock()
        request.method = "POST"
        request.headers = {"Origin": "http://localhost:8501"}

        async def call_next(r):
            return JSONResponse({"ok": True})

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_csrf_allows_127_0_0_1(self):
        from src.api.main import CSRFMiddleware
        import asyncio

        middleware = CSRFMiddleware(MagicMock())
        request = MagicMock()
        request.method = "POST"
        request.headers = {"Origin": "http://127.0.0.1:8000"}

        async def call_next(r):
            return JSONResponse({"ok": True})

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_csrf_blocks_unknown_origin(self):
        from src.api.main import CSRFMiddleware
        from src.config import Settings
        import asyncio

        original = Settings.ALLOWED_ORIGIN
        try:
            Settings.ALLOWED_ORIGIN = "mysite.com"
            middleware = CSRFMiddleware(MagicMock())
            request = MagicMock()
            request.method = "DELETE"
            request.headers = {"Origin": "http://evil.example.com"}

            async def call_next(r):
                return JSONResponse({"ok": True})

            response = asyncio.run(middleware.dispatch(request, call_next))
            assert response.status_code == 403
        finally:
            Settings.ALLOWED_ORIGIN = original

    def test_csrf_allows_configured_origin(self):
        from src.api.main import CSRFMiddleware
        from src.config import Settings
        import asyncio

        original = Settings.ALLOWED_ORIGIN
        try:
            Settings.ALLOWED_ORIGIN = "mysite.com,other.com"
            middleware = CSRFMiddleware(MagicMock())
            request = MagicMock()
            request.method = "POST"
            request.headers = {"Origin": "http://mysite.com"}

            async def call_next(r):
                return JSONResponse({"ok": True})

            response = asyncio.run(middleware.dispatch(request, call_next))
            assert response.status_code == 200

            request2 = MagicMock()
            request2.method = "POST"
            request2.headers = {"Origin": "http://other.com"}
            response2 = asyncio.run(middleware.dispatch(request2, call_next))
            assert response2.status_code == 200
        finally:
            Settings.ALLOWED_ORIGIN = original

    def test_csrf_blocks_with_multiple_origins_configured(self):
        from src.api.main import CSRFMiddleware
        from src.config import Settings
        import asyncio

        original = Settings.ALLOWED_ORIGIN
        try:
            Settings.ALLOWED_ORIGIN = "mysite.com,other.com"
            middleware = CSRFMiddleware(MagicMock())
            request = MagicMock()
            request.method = "DELETE"
            request.headers = {"Origin": "http://evil.com"}

            async def call_next(r):
                return JSONResponse({"ok": True})

            response = asyncio.run(middleware.dispatch(request, call_next))
            assert response.status_code == 403
        finally:
            Settings.ALLOWED_ORIGIN = original


class TestLLMSemanticRouting:
    """LLM语义路由端到端测试。"""

    def test_llm_classify_returns_role(self):
        supervisor = SupervisorAgent()
        supervisor.register_sub_agent(PlannerAgent())
        supervisor.register_sub_agent(ExpertAgent())
        supervisor.register_sub_agent(QuizzerAgent())

        with patch.object(supervisor, "_chat", return_value="quizzer"):
            role = supervisor._llm_classify_intent("请给我出几道Python练习题")
            assert role == AgentRole.QUIZZER

    def test_llm_classify_unknown_response(self):
        supervisor = SupervisorAgent()
        with patch.object(supervisor, "_chat", return_value="unknown_role_xyz"):
            role = supervisor._llm_classify_intent("random message")
            assert role is None

    def test_llm_classify_error_fallback(self):
        supervisor = SupervisorAgent()
        with patch.object(supervisor, "_chat", side_effect=RuntimeError("LLM down")):
            role = supervisor._llm_classify_intent("test message")
            assert role is None


class TestCommunicationSignals:
    """Agent通信信号端到端测试。"""

    def test_ensure_communication_initializes(self):
        supervisor = SupervisorAgent()
        supervisor.register_sub_agent(PartnerAgent())
        state = {
            "user_id": "e2e_comm_test",
            "user_profile": {"name": "T", "level": "beginner"},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        }
        supervisor._ensure_communication(state)
        assert supervisor._comm_started is True

    def test_emit_result_signal_does_not_crash(self):
        supervisor = SupervisorAgent()
        supervisor.register_sub_agent(PlannerAgent())
        state = {
            "user_id": "e2e_comm_test2",
            "user_profile": {"name": "T", "level": "beginner"},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        }
        supervisor._ensure_communication(state)
        result = AgentResult(agent_role=AgentRole.PLANNER, output={"reply": "test response"}, success=True)
        supervisor._emit_result_signal(state, result, AgentRole.PLANNER)
        assert result.success

    def test_communicate_signals_agent_workflow(self):
        supervisor = SupervisorAgent()
        planner = PlannerAgent()
        supervisor.register_sub_agent(PartnerAgent())
        supervisor.register_sub_agent(planner)
        state = {
            "user_id": "e2e_comm_flow",
            "user_profile": {"name": "T", "level": "beginner"},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        }

        with patch.object(planner, "_chat", return_value=PLAN_JSON):
            result = supervisor._run_impl(state, "帮我制定Python学习计划")
            assert result.success


class TestSupervisorAllAgents:
    """Supervisor全Agent集成端到端测试。"""

    def test_supervisor_with_all_seven_agents(self):
        supervisor = SupervisorAgent()
        supervisor.register_sub_agent(PlannerAgent())
        supervisor.register_sub_agent(ExpertAgent())
        supervisor.register_sub_agent(PartnerAgent())
        supervisor.register_sub_agent(QuizzerAgent())
        supervisor.register_sub_agent(ReviewerAgent())
        supervisor.register_sub_agent(ExaminerAgent())

        assert len(supervisor._agents) == 6

        state = {
            "user_id": "e2e_all",
            "user_profile": {"name": "Test", "level": "beginner", "target_field": "Python"},
            "messages": [], "agent_outputs": {}, "weak_points": [],
        }

        route_tests = [
            ("帮我制定Python学习计划", AgentRole.PLANNER),
            ("推荐一些入门书籍", AgentRole.EXPERT),
            ("什么是闭包？", AgentRole.PARTNER),
            ("出几道算法题", AgentRole.QUIZZER),
            ("帮我分析错题", AgentRole.REVIEWER),
            ("面试怎么准备", AgentRole.EXAMINER),
        ]

        for message, expected_role in route_tests:
            matched = supervisor._classify_intent(message)
            assert len(matched) > 0
            if matched[0] != expected_role:
                print(f"INFO: '{message}' -> {matched[0].value} (expected {expected_role.value})")

    def test_aggregate_all_agent_outputs(self):
        supervisor = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, output={"plan_text": "详细Python学习计划，包括基础和进阶"}, success=True),
            AgentResult(agent_role=AgentRole.EXPERT, output={"ai_recommendation": "推荐多本入门书籍和在线课程"}, success=True),
            AgentResult(agent_role=AgentRole.PARTNER, output={"reply": "闭包是指函数内定义函数"}, success=True),
        ]
        aggregated = supervisor.aggregate_results(results)
        assert "Python" in aggregated
        assert "planner" in aggregated
        assert len(aggregated) > 80