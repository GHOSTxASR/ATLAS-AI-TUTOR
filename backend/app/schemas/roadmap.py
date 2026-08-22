from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

RoadmapMode = Literal["strict", "adaptive", "hybrid"]
NodeStatus = Literal["not_started", "in_progress", "completed", "skipped", "flagged"]
NodeType = Literal["subject", "chapter", "topic", "bridge"]
EdgeType = Literal["sequential", "prerequisite", "bridge"]


class RoadmapCreate(BaseModel):
    document_id: str | None = Field(None, description="ID of syllabus document to build roadmap from")
    mode: RoadmapMode = Field("strict", description="Roadmap generation mode: strict, adaptive, or hybrid")
    title: str | None = Field(None, description="Optional custom title for the roadmap")
    syllabus_text: str | None = Field(None, description="Optional raw syllabus text instead of document ID")


class RoadmapNodeUpdate(BaseModel):
    status: NodeStatus | None = None
    mastery_score: float | None = Field(None, ge=0.0, le=1.0)
    time_spent_minutes: int | None = Field(None, ge=0)


class RoadmapNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    roadmap_id: str
    profile_id: str
    title: str
    description: str | None = None
    node_type: str
    status: str
    parent_id: str | None = None
    order_index: int
    mastery_score: float
    time_spent_minutes: int
    ai_generated: bool
    completed_at: datetime | None = None
    unlocked: bool = True


class RoadmapEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    roadmap_id: str
    from_node_id: str
    to_node_id: str
    edge_type: str


class RoadmapProgress(BaseModel):
    total_nodes: int = 0
    completed_nodes: int = 0
    in_progress_nodes: int = 0
    completion_percentage: float = 0.0
    average_mastery: float = 0.0


class RoadmapSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    title: str
    mode: str
    version: int
    is_active: bool
    source_document_id: str | None = None
    created_at: datetime
    node_count: int = 0


class RoadmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    title: str
    mode: str
    version: int
    is_active: bool
    source_document_id: str | None = None
    created_at: datetime
    nodes: list[RoadmapNodeResponse] = Field(default_factory=list)
    edges: list[RoadmapEdgeResponse] = Field(default_factory=list)
    progress: RoadmapProgress | None = None


# Alias
RoadmapDetailResponse = RoadmapResponse
