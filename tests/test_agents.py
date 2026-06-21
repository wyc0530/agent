import os
import sys
import uuid

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_LLM_KEY = os.getenv("LLM_API_KEY", "")
_LLM_AVAILABLE = bool(_LLM_KEY) and _LLM_KEY not in ("your-openai-api-key-here", "sk-your-api-key-here")
_llm_required = pytest.mark.skipif(not _LLM_AVAILABLE, reason="未配置有效的LLM API Key")


def _make_state(user_id: str = "test_user", **overrides):
    from src.core.state import LearningState

    profile = {
        "name": "测试同学",
        "level": "中等",
        "target_field": "计算机科学",
        "available_time": 10,
        "preference": "综合学习",
    }
    base = {
        "messages": [],
        "user_id": user_id,
        "user_profile": profile,
        "weak_points": [{"knowledge_point": "递归", "error_rate": 0.7, "need_review": True}],
        "error_records": [
            {"knowledge_point": "递归", "error_type": "概念不清", "error_count": 3},
            {"knowledge_point": "链表", "error_type": "实现错误", "error_count": 1},
        ],
        "quiz_results": [
            {"question_id": "q1", "is_correct": False, "knowledge_point": "递归"},
            {"question_id": "q2", "is_correct": True, "knowledge_point": "链表"},
        ],
        "focus_time_minutes": 45,
        "focus_sessions": [
            {"start_time": "2026-01-01T10:00:00", "duration_minutes": 25, "topic": "递归"},
            {"start_time": "2026-01-01T10:30:00", "duration_minutes": 20, "topic": "链表"},
        ],
    }
    base.update(overrides)
    return LearningState(**base)


class TestBaseAgent:
    def test_agent_result_model(self):
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole

        r = AgentResult(agent_role=AgentRole.PLANNER, success=True, output={"key": "value"})
        assert r.success is True
        assert r.output["key"] == "value"

        r2 = AgentResult(agent_role=AgentRole.PARTNER, success=False, error="test error")
        assert r2.success is False
        assert r2.error == "test error"


class TestPlannerAgent:
    def test_init_and_registration(self):
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        assert agent.role.value == "planner"
        assert len(agent.description) > 0

    def test_build_prompt_with_state(self):
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "测试同学" in prompt
        assert "递归" in prompt

    @_llm_required
    def test_run_generates_plan(self):
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        state = _make_state()
        result = agent.run(state, "帮我制定一个学习Python的学习计划")

        if not result.success:
            pytest.skip(f"LLM API 暂时不可用: {result.error}")

        assert result.agent_role.value == "planner"
        assert "plan_text" in result.output
        assert len(result.output["plan_text"]) > 50

    def test_build_prompt_with_existing_plan(self):
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        state = _make_state(learning_plan={
            "title": "Python学习计划",
            "phases": [
                {"phase_name": "基础", "phase_description": "入门", "order": 1}
            ],
            "goals": [],
        })
        prompt = agent._build_system_prompt(state)
        assert "Python学习计划" in prompt
        assert "阶段数: 1" in prompt


class TestExpertAgent:
    def test_init(self):
        from src.agents.expert import ExpertAgent

        agent = ExpertAgent()
        assert agent.role.value == "expert"

    def test_build_prompt(self):
        from src.agents.expert import ExpertAgent

        agent = ExpertAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "学习资料" in prompt

    @_llm_required
    def test_run_recommends(self):
        from src.agents.expert import ExpertAgent

        agent = ExpertAgent()
        state = _make_state()
        result = agent.run(state, "Python基础语法")

        if not result.success:
            pytest.skip(f"LLM API 暂时不可用: {result.error}")

        assert result.agent_role.value == "expert"
        assert "ai_recommendation" in result.output or "document" in result.output

    def test_build_prompt_with_existing_plan(self):
        from src.agents.expert import ExpertAgent

        agent = ExpertAgent()
        state = _make_state(learning_plan={
            "title": "CS计划",
            "phases": [
                {"phase_name": "数据结构", "phase_description": "栈队列树", "order": 1},
                {"phase_name": "算法", "phase_description": "排序搜索", "order": 2},
            ],
            "goals": [],
        })
        prompt = agent._build_system_prompt(state)
        assert "数据结构" in prompt

    def test_document_generation_mocked(self):
        from unittest.mock import MagicMock
        from src.agents.expert import ExpertAgent

        agent = ExpertAgent()
        agent._chat = MagicMock(return_value="模拟AI推荐内容")
        agent._doc_gen.execute = MagicMock(return_value={"title": "Mock Doc", "content": "test"})
        agent._searcher.execute = MagicMock(return_value=[])
        state = _make_state()
        result = agent.run(state, "测试主题")
        assert result.success


class TestPartnerAgent:
    def test_init(self):
        from src.agents.partner import PartnerAgent

        agent = PartnerAgent()
        assert agent.role.value == "partner"

    def test_build_prompt(self):
        from src.agents.partner import PartnerAgent

        agent = PartnerAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "45 分钟" in prompt or "45" in prompt

    @_llm_required
    def test_run_answers_question(self):
        from src.agents.partner import PartnerAgent

        agent = PartnerAgent()
        state = _make_state()
        result = agent.run(state, "什么是递归？")

        if not result.success:
            pytest.skip(f"LLM API 暂时不可用: {result.error}")

        assert result.agent_role.value == "partner"
        assert "answer" in result.output
        assert len(result.output["answer"]) > 20

    def test_rag_retrieval_mocked(self):
        from unittest.mock import MagicMock
        from src.agents.partner import PartnerAgent

        agent = PartnerAgent()
        agent._chat = MagicMock(return_value="模拟学习伙伴回答")
        agent._retriever.retrieve = MagicMock(return_value=[
            {"id": "doc1", "content": "递归是一种编程技巧", "score": 0.95},
        ])
        state = _make_state()
        result = agent.run(state, "什么是递归")
        assert result.success


class TestQuizzerAgent:
    def test_init(self):
        from src.agents.quizzer import QuizzerAgent

        agent = QuizzerAgent()
        assert agent.role.value == "quizzer"

    def test_difficulty_adjustment_up(self):
        from src.agents.quizzer import QuizzerAgent

        agent = QuizzerAgent()
        agent._difficulty_cache["test"] = 0.5
        agent._adjust_difficulty("test", 0.9, 0.5)
        assert agent._difficulty_cache["test"] > 0.5

    def test_difficulty_adjustment_down(self):
        from src.agents.quizzer import QuizzerAgent

        agent = QuizzerAgent()
        agent._difficulty_cache["test"] = 0.5
        agent._adjust_difficulty("test", 0.3, 0.5)
        assert agent._difficulty_cache["test"] < 0.5

    def test_run_generates_quiz(self):
        from src.agents.quizzer import QuizzerAgent

        agent = QuizzerAgent()
        state = _make_state()
        result = agent.run(state, "递归")

        assert result.success is True
        assert result.agent_role.value == "quizzer"
        assert "questions" in result.output
        assert len(result.output["questions"]) > 0
        assert "assessment" in result.output

    def test_rl_strategy_description(self):
        from src.agents.quizzer import QuizzerAgent

        assert "挑战" in QuizzerAgent._get_strategy_description(0.9)
        assert "进阶" in QuizzerAgent._get_strategy_description(0.6)
        assert "巩固" in QuizzerAgent._get_strategy_description(0.3)


class TestReviewerAgent:
    def test_init(self):
        from src.agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        assert agent.role.value == "reviewer"

    def test_build_prompt_includes_errors(self):
        from src.agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "递归" in prompt

    @_llm_required
    def test_run_analyzes_errors(self):
        from src.agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        state = _make_state()
        result = agent.run(state, "帮我分析我的错题")

        if not result.success:
            pytest.skip(f"LLM API 暂时不可用: {result.error}")

        assert result.agent_role.value == "reviewer"
        assert "analysis" in result.output


class TestExaminerAgent:
    def test_init(self):
        from src.agents.examiner import ExaminerAgent

        agent = ExaminerAgent()
        assert agent.role.value == "examiner"

    def test_build_prompt(self):
        from src.agents.examiner import ExaminerAgent

        agent = ExaminerAgent()
        state = _make_state()
        prompt = agent._build_system_prompt(state)
        assert "考研" in prompt or "备考" in prompt or "考试" in prompt

    @_llm_required
    def test_run_generates_guidance(self):
        from src.agents.examiner import ExaminerAgent

        agent = ExaminerAgent()
        state = _make_state()
        result = agent.run(state, "我准备考研计算机，请给我备考建议")

        if not result.success:
            pytest.skip(f"LLM API 暂时不可用: {result.error}")

        assert result.agent_role.value == "examiner"
        assert "exam_guidance" in result.output

    def test_build_prompt_with_existing_plan(self):
        from src.agents.examiner import ExaminerAgent

        agent = ExaminerAgent()
        state = _make_state(learning_plan={
            "title": "考研备战",
            "phases": [
                {"phase_name": "一轮复习", "phase_description": "全面复习", "order": 1},
                {"phase_name": "二轮冲刺", "phase_description": "真题练习", "order": 2},
            ],
            "goals": [],
        })
        prompt = agent._build_system_prompt(state)
        assert "考研备战" in prompt
        assert "阶段数: 2" in prompt


class TestSupervisorAgent:
    def test_init(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.planner import PlannerAgent

        sv = SupervisorAgent()
        planner = PlannerAgent()
        sv.register_sub_agent(planner)

        assert sv.role.value == "assistant"
        assert len(sv._agents) == 1

    def test_classify_intent_plan(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("帮我制定一个学习计划")
        assert AgentRole.PLANNER in roles

    def test_classify_intent_question(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("什么是动态规划")
        assert AgentRole.PARTNER in roles

    def test_classify_intent_quiz(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("给我出几道题目")
        assert AgentRole.QUIZZER in roles

    def test_classify_intent_exam(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("考研怎么准备")
        assert AgentRole.EXAMINER in roles

    def test_classify_intent_fallback(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("你好")
        assert AgentRole.PARTNER in roles

    def test_empty_message(self):
        from src.agents.assistant import SupervisorAgent

        sv = SupervisorAgent()
        state = _make_state()
        result = sv.run(state, "")
        assert result.success is True
        assert "reply" in result.output

    def test_aggregate_results(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.base_agent import AgentResult
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        results = [
            AgentResult(agent_role=AgentRole.PLANNER, output={"plan_text": "Plan A"}),
            AgentResult(agent_role=AgentRole.EXPERT, output={"ai_recommendation": "Rec B"}),
        ]
        text = sv.aggregate_results(results)
        assert "Plan A" in text or "Rec B" in text

    def test_run_parallel_async(self):
        import asyncio
        from unittest.mock import MagicMock
        from src.agents.assistant import SupervisorAgent
        from src.agents.planner import PlannerAgent
        from src.agents.partner import PartnerAgent
        from src.agents.base_agent import AgentResult

        async def _run():
            sv = SupervisorAgent()
            planner = PlannerAgent()
            partner = PartnerAgent()
            planner._chat = MagicMock(return_value='{"title": "test", "goals": [], "phases": []}')
            partner._chat = MagicMock(return_value="模拟回答")
            sv.register_sub_agent(planner)
            sv.register_sub_agent(partner)
            state = _make_state()
            results = await sv.run_parallel(state, "帮我制定计划并解答问题")
            assert len(results) >= 1
            for r in results:
                assert isinstance(r, AgentResult)

        asyncio.run(_run())

    def test_classify_intent_quiz_avoid_false_positive(self):
        from src.agents.assistant import SupervisorAgent
        from src.core.state import AgentRole

        sv = SupervisorAgent()
        roles = sv._classify_intent("检测报告怎么写")
        assert AgentRole.QUIZZER not in roles, "非测验消息不应路由到Quizzer"


class TestAgentIntegration:
    def test_all_agents_health_check(self):
        from src.agents.planner import PlannerAgent
        from src.agents.expert import ExpertAgent
        from src.agents.partner import PartnerAgent
        from src.agents.quizzer import QuizzerAgent
        from src.agents.reviewer import ReviewerAgent
        from src.agents.examiner import ExaminerAgent
        from src.agents.assistant import SupervisorAgent

        agents = [
            PlannerAgent(),
            ExpertAgent(),
            PartnerAgent(),
            QuizzerAgent(),
            ReviewerAgent(),
            ExaminerAgent(),
            SupervisorAgent(),
        ]

        for a in agents:
            health = a.check_health()
            assert "role" in health, f"{a.role.value} 健康检查缺少 role"
            assert "llm_available" in health, f"{a.role.value} 健康检查缺少 llm_available"

    def test_full_supervisor_routing(self):
        from src.agents.assistant import SupervisorAgent
        from src.agents.planner import PlannerAgent
        from src.agents.partner import PartnerAgent
        from src.agents.quizzer import QuizzerAgent
        from src.agents.reviewer import ReviewerAgent
        from src.agents.examiner import ExaminerAgent
        from src.agents.expert import ExpertAgent

        sv = SupervisorAgent()
        sv.register_sub_agent(PlannerAgent())
        sv.register_sub_agent(ExpertAgent())
        sv.register_sub_agent(PartnerAgent())
        sv.register_sub_agent(QuizzerAgent())
        sv.register_sub_agent(ReviewerAgent())
        sv.register_sub_agent(ExaminerAgent())

        assert len(sv._agents) == 6

        state = _make_state()
        result = sv.run(state, "给我出几道关于递归的题目")
        assert result.agent_role.value == "quizzer"
        assert result.success

    def test_state_changes_propagation(self):
        from unittest.mock import MagicMock
        from src.agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        agent._chat = MagicMock(return_value='{"weak_points_summary": ["递归", "动态规划"], "error_categories": [], "review_suggestions": [], "feedback_for_planner": "test"}')
        state = _make_state()
        result = agent.run(state, "分析错题")
        assert result.success
        assert "weak_points" in result.state_changes

    def test_error_recovery(self):
        from unittest.mock import MagicMock
        from src.agents.planner import PlannerAgent

        agent = PlannerAgent()
        agent._chat = MagicMock(return_value='{"title": "默认计划", "goals": [], "phases": []}')
        state = _make_state()
        state["user_profile"] = None
        result = agent.run(state, "test")
        assert result.success, f"Agent should handle None profile gracefully: {result.error}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])