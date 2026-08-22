from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class MemoryContextSummary(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    learning_style: str | None = None
    recent_notes: list[str] = Field(default_factory=list)


class RoadmapContextSummary(BaseModel):
    roadmap_title: str | None = None
    mode: str | None = None
    active_topic: str | None = None
    mastery_score: float = 0.0
    status: str = "not_started"
    prerequisites: list[str] = Field(default_factory=list)
    next_topics: list[str] = Field(default_factory=list)


class KnowledgeGraphContextSummary(BaseModel):
    matched_concept: str | None = None
    concept_description: str | None = None
    mastery_score: float = 0.0
    mention_count: int = 0
    prerequisite_concepts: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    connected_documents: list[str] = Field(default_factory=list)


class SyllabusContextSummary(BaseModel):
    syllabus_title: str | None = None
    current_chapter: str | None = None
    covered_subtopics: list[str] = Field(default_factory=list)


class UnifiedLearningContext(BaseModel):
    profile_id: str
    profile_name: str
    profile_type: str
    mode: str
    system_prompt: str
    memory: MemoryContextSummary
    roadmap: RoadmapContextSummary
    graph: KnowledgeGraphContextSummary
    syllabus: SyllabusContextSummary
    citations: list[dict[str, Any]] = Field(default_factory=list)
    total_tokens: int = 0
