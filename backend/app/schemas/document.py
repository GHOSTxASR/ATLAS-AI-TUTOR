from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentFileType = Literal["pdf", "docx", "txt", "image"]

DocumentStatus = Literal[
    "pending",
    "extracting",
    "extracted",
    "pending_ocr",
    "chunking",
    "queuing",
    "indexing",
    "indexed",
    "error",
]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    filename: str
    file_type: DocumentFileType
    status: DocumentStatus
    page_count: int | None
    chunk_count: int
    word_count: int | None
    is_syllabus: bool
    roadmap_node_id: str | None
    uploaded_at: datetime
    indexed_at: datetime | None
    error_message: str | None


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: DocumentStatus
    page_count: int | None
    word_count: int | None
    chunk_count: int
    error_message: str | None
