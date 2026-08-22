from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


def camel_to_snake(name: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _utcnow() -> datetime:
    """Naive UTC timestamp with microsecond precision.

    Naive to match the existing columns (and rows written by
    ``CURRENT_TIMESTAMP``, which is also UTC), so old and new values remain
    directly comparable.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        snake_name = camel_to_snake(cls.__name__)
        if not snake_name.endswith("s"):
            snake_name += "s"
        return snake_name

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Python-side defaults give microsecond precision. SQL `CURRENT_TIMESTAMP`
    # resolves only to the second, so every row written within the same second
    # shared one timestamp and any `ORDER BY created_at` (chat history, session
    # lists) had an undefined order. `server_default` stays for raw inserts.
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class Profile(Base):
    """User learning profile."""
    name: Mapped[str] = mapped_column(String, nullable=False)
    profile_type: Mapped[str] = mapped_column(String, nullable=False)


class ChatSession(Base):
    """A chat thread/session."""
    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)


class ChatMessage(Base):
    """A single message within a chat session."""
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)


class Document(Base):
    """An uploaded learning document owned by a profile.

    Milestone 08 covers upload, storage, and text extraction only. Chunking,
    embedding, and vector indexing (status values beyond ``extracted``) are
    introduced in later milestones.
    """
    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    extracted_text_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now())
    indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    is_syllabus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    roadmap_node_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ChunkEmbeddingQueue(Base):
    """Queue table for asynchronous document chunk embedding."""

    __tablename__ = "chunk_embedding_queue"

    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class EmbeddingCache(Base):
    """Cache of text content hash to embedding vector for deduplication."""

    __tablename__ = "embedding_cache"

    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    vector_json: Mapped[str] = mapped_column(String, nullable=False)


class MemoryRecord(Base):
    """A persistent long-term memory about a learner's strengths, weaknesses, or preferences."""

    __tablename__ = "memory_records"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String, nullable=False, default="")
    content: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0)
    source: Mapped[str] = mapped_column(String, nullable=False, default="chat")
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Roadmap(Base):
    """Learning roadmap graph DAG container."""

    __tablename__ = "roadmaps"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="strict")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    nodes: Mapped[list[RoadmapNode]] = relationship(
        "RoadmapNode", back_populates="roadmap", cascade="all, delete-orphan", order_by="RoadmapNode.order_index"
    )
    edges: Mapped[list[RoadmapEdge]] = relationship(
        "RoadmapEdge", back_populates="roadmap", cascade="all, delete-orphan"
    )


class RoadmapNode(Base):
    """Individual concept, chapter, or topic node within a roadmap DAG."""

    __tablename__ = "roadmap_nodes"

    roadmap_id: Mapped[str] = mapped_column(
        String, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    node_type: Mapped[str] = mapped_column(String, nullable=False, default="topic")
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started", index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("roadmap_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_spent_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)

    roadmap: Mapped[Roadmap] = relationship("Roadmap", back_populates="nodes")


class RoadmapEdge(Base):
    """Directed dependency or sequential edge between roadmap nodes."""

    __tablename__ = "roadmap_edges"

    roadmap_id: Mapped[str] = mapped_column(
        String, ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_node_id: Mapped[str] = mapped_column(
        String, ForeignKey("roadmap_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_node_id: Mapped[str] = mapped_column(
        String, ForeignKey("roadmap_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String, nullable=False, default="sequential")

    roadmap: Mapped[Roadmap] = relationship("Roadmap", back_populates="edges")


class AnalyticsEvent(Base):
    """Event log for tracking study sessions, topic progress, quizzes, and learning velocity."""

    __tablename__ = "analytics_events"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, default="roadmap_node")
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)


class QuizAttempt(Base):
    """Assessment and quiz session record evaluating learner topic mastery."""

    __tablename__ = "quiz_attempts"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    roadmap_node_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("roadmap_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String, nullable=False, default="practice")
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    questions_json: Mapped[str] = mapped_column(String, nullable=False)


class Note(Base):
    """Study note generated automatically by AI or created by the learner."""

    __tablename__ = "notes"

    profile_id: Mapped[str] = mapped_column(
        String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    roadmap_node_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("roadmap_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    note_type: Mapped[str] = mapped_column(String, nullable=False, default="lesson_note", index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="ai_generated")
    tags_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

