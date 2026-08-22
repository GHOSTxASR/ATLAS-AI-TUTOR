from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal["mcq", "numerical", "short_answer"]
QuizMode = Literal["practice", "timed_assessment"]
AssessmentType = Literal["topic_assessment", "chapter_test", "comprehensive_exam", "diagnostic_test"]
DifficultyLevel = Literal["easy", "medium", "hard", "adaptive"]
ErrorClassification = Literal[
    "correct",
    "conceptual_misunderstanding",
    "calculation_error",
    "incomplete_answer",
    "misread_question",
]


class QuizOption(BaseModel):
    id: str = Field(..., description="Option key, e.g. A, B, C, D")
    text: str = Field(..., description="Option choice text")


class QuizQuestion(BaseModel):
    id: str
    question_type: QuestionType
    prompt: str
    options: list[QuizOption] | None = None
    target_value: float | None = None
    tolerance: float | None = 0.05
    rubric: str | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    topic_title: str | None = None
    difficulty: DifficultyLevel = "medium"


class QuizQuestionPublic(BaseModel):
    id: str
    question_type: QuestionType
    prompt: str
    options: list[QuizOption] | None = None
    topic_title: str | None = None
    difficulty: DifficultyLevel = "medium"


class QuizGenerateRequest(BaseModel):
    roadmap_node_id: str | None = Field(None, description="Optional roadmap node ID to generate questions for")
    topic_title: str | None = Field(None, description="Optional topic or chapter title if node ID not provided")
    question_types: list[QuestionType] | None = Field(
        default_factory=lambda: ["mcq", "numerical", "short_answer"],
        description="Types of questions to generate",
    )
    mode: QuizMode = Field("practice", description="practice or timed_assessment")
    question_count: int = Field(5, ge=1, le=25, description="Number of questions to generate")
    time_limit_seconds: int | None = Field(None, ge=30, le=7200, description="Time limit for timed assessment mode")
    difficulty: DifficultyLevel = Field("medium", description="Difficulty level: easy, medium, hard, adaptive")


class AssessmentGenerateRequest(BaseModel):
    assessment_type: AssessmentType = Field("topic_assessment", description="Assessment format")
    roadmap_node_ids: list[str] | None = Field(None, description="List of roadmap node IDs covered")
    chapter_title: str | None = Field(None, description="Chapter title for chapter test")
    topic_titles: list[str] | None = Field(None, description="Custom list of topic titles")
    difficulty: DifficultyLevel = Field("medium", description="Difficulty level: easy, medium, hard, adaptive")
    question_count: int = Field(6, ge=1, le=30, description="Number of questions")
    time_limit_seconds: int | None = Field(None, ge=30, le=7200, description="Optional time limit")


class QuizUserAnswer(BaseModel):
    question_id: str
    user_answer: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizUserAnswer] = Field(default_factory=list)


class QuestionResult(BaseModel):
    question_id: str
    question_type: str
    prompt: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    score: float = Field(..., ge=0.0, le=1.0)
    error_category: ErrorClassification = "correct"
    feedback: str = ""
    explanation: str = ""
    remediation_advice: str = ""


class MasteryNodeUpdate(BaseModel):
    node_id: str
    node_title: str
    previous_mastery: float
    new_mastery: float
    status: str
    unlocked: bool = True


class QuizResponse(BaseModel):
    id: str
    profile_id: str
    roadmap_node_id: str | None = None
    mode: str
    total_questions: int
    time_limit_seconds: int | None = None
    difficulty: str = "medium"
    questions: list[QuizQuestionPublic]


class QuizResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    roadmap_node_id: str | None = None
    mode: str
    started_at: datetime
    completed_at: datetime | None = None
    score: float = 0.0
    letter_grade: str = "N/A"
    total_questions: int
    correct_count: int = 0
    time_limit_seconds: int | None = None
    question_results: list[QuestionResult] = Field(default_factory=list)
    mastery_updates: list[MasteryNodeUpdate] = Field(default_factory=list)
    strengths_recorded: list[str] = Field(default_factory=list)
    weaknesses_recorded: list[str] = Field(default_factory=list)
    unlocked_nodes: list[str] = Field(default_factory=list)
    overall_feedback: str = ""
    mastery_delta: float = 0.0


class QuizAttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    roadmap_node_id: str | None = None
    # Resolved from the roadmap node so history can be labelled by subject
    # rather than by a fragment of the attempt id.
    topic_title: str | None = None
    mode: str
    started_at: datetime
    completed_at: datetime | None = None
    score: float | None = None
    total_questions: int
    correct_count: int | None = None
