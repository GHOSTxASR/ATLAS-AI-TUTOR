from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AnalyticsEventCreate(BaseModel):
    event_type: str = Field(..., description="Type of study or interaction event")
    entity_type: str = Field("roadmap_node", description="Entity type: roadmap_node, document, session, quiz, model, note")
    entity_id: str | None = Field(None, description="Optional ID of associated entity")
    value: float | None = Field(None, description="Numeric payload such as study minutes, score, latency")
    metadata_json: str | None = Field(None, description="Optional JSON string with event context")


class AnalyticsEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    event_type: str
    entity_type: str
    entity_id: str | None
    value: float | None
    metadata_json: str | None
    occurred_at: datetime


class ChapterProgressItem(BaseModel):
    chapter_title: str
    total_topics: int = 0
    completed_topics: int = 0
    completion_percentage: float = 0.0
    average_mastery: float = 0.0


class StudyTimeBreakdown(BaseModel):
    roadmap_minutes: int = 0
    chat_minutes: int = 0
    quiz_minutes: int = 0
    notes_minutes: int = 0
    total_minutes: int = 0


class AnalyticsOverviewResponse(BaseModel):
    completion_percentage: float = Field(0.0, description="Overall roadmap completion percentage")
    total_topics: int = 0
    completed_topics: int = 0
    in_progress_topics: int = 0
    not_started_topics: int = 0
    average_mastery: float = Field(0.0, description="Average mastery score from 0.0 to 1.0")
    total_study_minutes: int = 0
    active_streak_days: int = 0
    total_sessions: int = 0
    total_documents: int = 0
    total_notes: int = 0
    total_quizzes_taken: int = 0
    average_quiz_score: float = 0.0
    study_time_breakdown: StudyTimeBreakdown = Field(default_factory=StudyTimeBreakdown)
    chapter_progress: list[ChapterProgressItem] = Field(default_factory=list)


class ActivityHeatmapItem(BaseModel):
    date: str
    minutes: int = 0
    events_count: int = 0


class MasteryTierTopic(BaseModel):
    id: str
    title: str
    mastery_score: float
    status: str


class MasteryDistributionResponse(BaseModel):
    mastered_count: int = 0       # score >= 0.8
    proficient_count: int = 0     # 0.5 <= score < 0.8
    needs_practice_count: int = 0 # 0.0 < score < 0.5
    unstarted_count: int = 0      # score == 0.0
    mastered_topics: list[MasteryTierTopic] = Field(default_factory=list)
    proficient_topics: list[MasteryTierTopic] = Field(default_factory=list)
    needs_practice_topics: list[MasteryTierTopic] = Field(default_factory=list)
    unstarted_topics: list[MasteryTierTopic] = Field(default_factory=list)


class LearningVelocityPoint(BaseModel):
    date: str
    topics_completed: int = 0
    study_minutes: int = 0


class WeaknessConcept(BaseModel):
    id: str | None = None
    title: str
    subject: str = ""
    source: str  # "roadmap_node" | "memory_record"
    mastery_score: float | None = None
    reason: str
