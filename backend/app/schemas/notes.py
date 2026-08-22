from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

NoteType = Literal["lesson_note", "revision_note", "cheat_sheet", "summary"]
NoteSource = Literal["ai_generated", "user_written"]


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Note title")
    content: str = Field(..., min_length=1, description="Markdown body content")
    note_type: NoteType = Field("lesson_note", description="Note modality")
    roadmap_node_id: str | None = Field(None, description="Optional roadmap node ID link")
    tags: list[str] = Field(default_factory=list, description="Tag list")


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    note_type: NoteType | None = None
    tags: list[str] | None = None


class NoteGenerateRequest(BaseModel):
    topic_title: str | None = Field(None, description="Topic or concept to generate note for")
    roadmap_node_id: str | None = Field(None, description="Optional roadmap node ID")
    note_type: NoteType = Field("lesson_note", description="lesson_note, revision_note, cheat_sheet, summary")
    custom_instructions: str | None = Field(None, description="Additional custom guidance or focus areas")
    document_ids: list[str] | None = Field(None, description="Specific document IDs to ground the note in")


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    roadmap_node_id: str | None = None
    title: str
    content: str
    note_type: NoteType
    source: NoteSource
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NoteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    roadmap_node_id: str | None = None
    title: str
    note_type: NoteType
    source: NoteSource
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
