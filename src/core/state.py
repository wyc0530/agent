import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Optional

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class AgentRole(str, Enum):
    ASSISTANT = "assistant"
    PLANNER = "planner"
    EXPERT = "expert"
    PARTNER = "partner"
    QUIZZER = "quizzer"
    REVIEWER = "reviewer"
    EXAMINER = "examiner"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LearningGoal(BaseModel):
    """学习目标"""
    title: str = Field(description="目标标题")
    description: str = Field(default="", description="目标描述")
    target_date: Optional[str] = Field(default=None, description="目标日期")
    priority: Priority = Field(default=Priority.MEDIUM, description="优先级")
    status: str = Field(default="pending", description="状态")


class LearningPhase(BaseModel):
    """学习阶段"""
    phase_id: str = Field(default_factory=lambda: str(_uuid.uuid4())[:8], description="阶段ID")
    title: str = Field(description="阶段名称")
    description: str = Field(default="", description="阶段描述")
    topics: list[str] = Field(default_factory=list, description="学习主题")
    duration_days: int = Field(default=7, description="预计天数")
    order: int = Field(default=0, description="顺序")


class LearningPlan(BaseModel):
    """学习规划方案"""
    plan_id: str = Field(default="", description="规划ID")
    title: str = Field(description="规划标题")
    goals: list[LearningGoal] = Field(default_factory=list)
    phases: list[LearningPhase] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CourseMaterial(BaseModel):
    """课程资料"""
    title: str = Field(description="资料标题")
    url: str = Field(default="", description="链接")
    source: str = Field(default="", description="来源")
    description: str = Field(default="", description="描述")
    relevance_score: float = Field(default=0.0, description="相关性评分")
    content_type: str = Field(default="article", description="内容类型")


class LearningContent(BaseModel):
    """学习内容"""
    topic: str = Field(description="主题")
    outline: list[str] = Field(default_factory=list, description="学习大纲")
    materials: list[CourseMaterial] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list, description="重点")


class QuizQuestion(BaseModel):
    """题目"""
    question_id: str = Field(description="题目ID")
    content: str = Field(description="题目内容")
    question_type: str = Field(default="single_choice", description="题型")
    options: list[str] = Field(default_factory=list, description="选项")
    answer: str = Field(default="", description="答案")
    explanation: str = Field(default="", description="解析")
    difficulty: float = Field(default=0.5, description="难度 0-1")
    knowledge_point: str = Field(default="", description="知识点")
    tags: list[str] = Field(default_factory=list)


class QuizResult(BaseModel):
    """答题结果"""
    question_id: str
    user_answer: str = ""
    is_correct: bool = False
    time_spent_seconds: float = 0.0
    answered_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ErrorRecord(BaseModel):
    """错题记录"""
    question: QuizQuestion
    user_answer: str
    error_count: int = Field(default=1)
    first_error_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_error_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    knowledge_point: str = ""
    mastered: bool = Field(default=False)


class WeakPoint(BaseModel):
    """薄弱点"""
    knowledge_point: str = Field(description="知识点")
    error_rate: float = Field(default=0.0, description="错误率")
    error_count: int = Field(default=0)
    total_attempts: int = Field(default=0)
    need_review: bool = Field(default=True)
    last_reviewed_at: Optional[str] = None


class AbilityReport(BaseModel):
    """能力测评报告"""
    overall_score: float = Field(default=0.0, description="综合评分")
    knowledge_coverage: dict[str, float] = Field(default_factory=dict, description="各知识点掌握度")
    weak_points: list[WeakPoint] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list, description="建议关注点")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentOutput(BaseModel):
    """Agent输出记录"""
    agent_role: AgentRole
    output_type: str = ""
    content: str = ""
    structured_data: Optional[dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class LearningState(TypedDict, total=False):
    """全局学习状态 - 所有Agent共享和传递的核心数据结构"""

    messages: Annotated[list, add_messages]

    user_id: str
    user_profile: dict[str, Any]

    current_agent: str
    agent_outputs: dict[str, AgentOutput]

    learning_plan: Optional[dict[str, Any]]
    learning_content: Optional[dict[str, Any]]
    current_topic: str

    quiz_questions: list[dict[str, Any]]
    quiz_results: list[dict[str, Any]]
    error_records: list[dict[str, Any]]
    weak_points: list[dict[str, Any]]
    ability_report: Optional[dict[str, Any]]

    focus_time_minutes: float
    focus_sessions: list[dict[str, Any]]

    pending_feedback: bool
    feedback_message: str

    error_message: str