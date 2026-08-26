from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

RoleLiteral = Literal["user", "assistant", "system"]
LearningMode = Literal[
    "teaching",
    "revision",
    "summary",
    "general_knowledge",
    "quiz",
    "assessment",
]


class ChatSessionCreate(BaseModel):
    title: str | None = Field(None, description="Optional title, defaults to 'New Chat'")
    default_mode: LearningMode = Field("teaching", description="Default learning mode for session")
    roadmap_node_id: str | None = Field(
        None, description="Roadmap topic this thread is about, when opened from one"
    )


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(None, description="The new title")
    default_mode: LearningMode | None = Field(None, description="Updated learning mode")


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    title: str
    roadmap_node_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    role: RoleLiteral
    content: str = Field(..., min_length=1)
    mode: LearningMode = Field("teaching", description="Active learning mode for this turn")
    document_ids: list[str] | None = None
    roadmap_node_id: str | None = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: RoleLiteral
    content: str
    created_at: datetime
    updated_at: datetime


class TutorChatRequest(BaseModel):
    session_id: str | None = None
    content: str = Field(..., min_length=1, description="Learner prompt or question")
    mode: LearningMode = Field("teaching", description="Learning mode: teaching, revision, summary, general_knowledge")
    document_ids: list[str] | None = None
    roadmap_node_id: str | None = None


class TutorChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    mode: LearningMode
    citations: list[dict[str, Any]] = Field(default_factory=list)
