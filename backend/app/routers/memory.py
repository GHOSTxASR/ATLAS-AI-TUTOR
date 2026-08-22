from __future__ import annotations


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.memory import MemoryCreate, MemoryResponse, MemoryUpdate
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/memory", tags=["memory"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_memory_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> MemoryService:
    return MemoryService(session=session, settings=settings)


@router.get("", response_model=dict)
async def list_memories(
    profile_id: str,
    category: str | None = Query(None, description="Filter by memory category"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score"),
    service: MemoryService = Depends(get_memory_service),
):
    memories = await service.list_memories(
        profile_id=profile_id, category=category, min_confidence=min_confidence
    )
    return envelope(data=[MemoryResponse.model_validate(m).model_dump() for m in memories])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_memory(
    profile_id: str,
    data: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.create_memory(profile_id=profile_id, data=data)
    return envelope(data=MemoryResponse.model_validate(memory).model_dump())


@router.get("/{memory_id}", response_model=dict)
async def get_memory(
    profile_id: str,
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.get_memory(profile_id=profile_id, memory_id=memory_id)
    return envelope(data=MemoryResponse.model_validate(memory).model_dump())


@router.patch("/{memory_id}", response_model=dict)
async def update_memory(
    profile_id: str,
    memory_id: str,
    data: MemoryUpdate,
    service: MemoryService = Depends(get_memory_service),
):
    memory = await service.update_memory(profile_id=profile_id, memory_id=memory_id, data=data)
    return envelope(data=MemoryResponse.model_validate(memory).model_dump())


@router.delete("/{memory_id}", response_model=dict)
async def delete_memory(
    profile_id: str,
    memory_id: str,
    service: MemoryService = Depends(get_memory_service),
):
    await service.delete_memory(profile_id=profile_id, memory_id=memory_id)
    return envelope(data={"success": True})
