from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryCategory = Literal[
    "strength",
    "weakness",
    "completed",
    "preference",
    "assessment",
    "fact",
    "context",
]

MemorySource = Literal["chat", "assessment", "manual"]


class MemoryCreate(BaseModel):
    category: MemoryCategory = Field(..., description="Classification category for this memory")
    content: str = Field(..., min_length=1, description="The memory statement or observation")
    subject: str = Field("", description="Topic/domain this memory applies to")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    source: MemorySource = Field("manual", description="Source origin of the memory")
    source_id: str | None = Field(None, description="Optional ID of originating message/quiz")


class MemoryUpdate(BaseModel):
    category: MemoryCategory | None = None
    content: str | None = Field(None, min_length=1)
    subject: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    is_active: bool | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    category: str
    subject: str
    content: str
    confidence: float
    source: str
    source_id: str | None
    is_active: bool
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime
