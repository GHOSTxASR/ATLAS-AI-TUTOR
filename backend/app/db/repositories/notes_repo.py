from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Note


class NotesRepository:
    """Repository handling persistence and querying of study notes in SQLite."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        profile_id: str,
        title: str,
        content: str,
        note_type: str = "lesson_note",
        source: str = "ai_generated",
        roadmap_node_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        """Create and persist a new note."""
        note = Note(
            id=str(uuid4()),
            profile_id=profile_id,
            roadmap_node_id=roadmap_node_id,
            title=title,
            content=content,
            note_type=note_type,
            source=source,
            tags_json=json.dumps(tags or []),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note

    async def get_by_id(self, note_id: str) -> Note | None:
        """Get a single note by primary ID."""
        stmt = select(Note).where(Note.id == note_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: str,
        note_type: str | None = None,
        roadmap_node_id: str | None = None,
        query: str | None = None,
    ) -> Sequence[Note]:
        """List notes for a profile with optional filtering by type, roadmap node, or search query."""
        stmt = select(Note).where(Note.profile_id == profile_id)

        if note_type:
            stmt = stmt.where(Note.note_type == note_type)
        if roadmap_node_id:
            stmt = stmt.where(Note.roadmap_node_id == roadmap_node_id)
        if query:
            q_pattern = f"%{query.strip()}%"
            stmt = stmt.where((Note.title.ilike(q_pattern)) | (Note.content.ilike(q_pattern)))

        stmt = stmt.order_by(Note.updated_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, note: Note, **kwargs: Any) -> Note:
        """Update fields on a note."""
        for key, value in kwargs.items():
            if hasattr(note, key) and value is not None:
                if key == "tags" and isinstance(value, list):
                    setattr(note, "tags_json", json.dumps(value))
                else:
                    setattr(note, key, value)
        note.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        """Delete a note from the database."""
        await self.session.delete(note)
        await self.session.commit()

    async def delete_by_profile_id(self, profile_id: str) -> int:
        """Delete all notes for a profile."""
        stmt = delete(Note).where(Note.profile_id == profile_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount


# Alias for backward compatibility
NotesRepo = NotesRepository
