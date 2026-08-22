from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.notes import (
    NoteCreate,
    NoteGenerateRequest,
    NoteUpdate,
)
from app.services.notes_service import NotesService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/notes", tags=["notes"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_notes_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> NotesService:
    return NotesService(session=session, settings=settings)


@router.post("/generate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_note(
    profile_id: str,
    data: NoteGenerateRequest,
    service: NotesService = Depends(get_notes_service),
):
    note = await service.generate_note(profile_id=profile_id, request=data)
    return envelope(data=note.model_dump())


@router.get("", response_model=dict)
async def list_notes(
    profile_id: str,
    note_type: str | None = Query(None, description="Filter by note modality"),
    roadmap_node_id: str | None = Query(None, description="Filter by roadmap node ID"),
    q: str | None = Query(None, description="Search note title or content"),
    service: NotesService = Depends(get_notes_service),
):
    notes = await service.list_notes(
        profile_id=profile_id,
        note_type=note_type,
        roadmap_node_id=roadmap_node_id,
        query=q,
    )
    return envelope(data=[n.model_dump() for n in notes])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_user_note(
    profile_id: str,
    data: NoteCreate,
    service: NotesService = Depends(get_notes_service),
):
    note = await service.create_user_note(profile_id=profile_id, data=data)
    return envelope(data=note.model_dump())


@router.get("/{note_id}", response_model=dict)
async def get_note(
    profile_id: str,
    note_id: str,
    service: NotesService = Depends(get_notes_service),
):
    note = await service.get_note(profile_id=profile_id, note_id=note_id)
    return envelope(data=note.model_dump())


@router.patch("/{note_id}", response_model=dict)
async def update_note(
    profile_id: str,
    note_id: str,
    data: NoteUpdate,
    service: NotesService = Depends(get_notes_service),
):
    note = await service.update_note(profile_id=profile_id, note_id=note_id, data=data)
    return envelope(data=note.model_dump())


@router.delete("/{note_id}", response_model=dict)
async def delete_note(
    profile_id: str,
    note_id: str,
    service: NotesService = Depends(get_notes_service),
):
    deleted = await service.delete_note(profile_id=profile_id, note_id=note_id)
    return envelope(data={"deleted": deleted})
