from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.roadmap import (
    RoadmapCreate,
    RoadmapNodeUpdate,
)
from app.services.roadmap_service import RoadmapService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/roadmaps", tags=["roadmap"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_roadmap_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> RoadmapService:
    return RoadmapService(session=session, settings=settings)


@router.get("", response_model=dict)
async def list_roadmaps(
    profile_id: str,
    service: RoadmapService = Depends(get_roadmap_service),
):
    roadmaps = await service.list_roadmaps(profile_id=profile_id)
    return envelope(data=[r.model_dump() for r in roadmaps])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_roadmap(
    profile_id: str,
    data: RoadmapCreate,
    service: RoadmapService = Depends(get_roadmap_service),
):
    roadmap = await service.generate_roadmap(profile_id=profile_id, data=data)
    return envelope(data=roadmap.model_dump())


@router.get("/active", response_model=dict)
async def get_active_roadmap(
    profile_id: str,
    service: RoadmapService = Depends(get_roadmap_service),
):
    roadmap = await service.get_active_roadmap(profile_id=profile_id)
    return envelope(data=roadmap.model_dump())


@router.get("/{roadmap_id}", response_model=dict)
async def get_roadmap(
    profile_id: str,
    roadmap_id: str,
    service: RoadmapService = Depends(get_roadmap_service),
):
    roadmap = await service.get_roadmap_by_id(profile_id=profile_id, roadmap_id=roadmap_id)
    return envelope(data=roadmap.model_dump())


@router.patch("/{roadmap_id}/nodes/{node_id}", response_model=dict)
async def update_roadmap_node(
    profile_id: str,
    roadmap_id: str,
    node_id: str,
    data: RoadmapNodeUpdate,
    service: RoadmapService = Depends(get_roadmap_service),
):
    updated_node = await service.update_node_status(
        profile_id=profile_id, roadmap_id=roadmap_id, node_id=node_id, data=data
    )
    return envelope(data=updated_node.model_dump())


@router.post("/{roadmap_id}/regenerate", response_model=dict)
async def regenerate_roadmap(
    profile_id: str,
    roadmap_id: str,
    service: RoadmapService = Depends(get_roadmap_service),
):
    roadmap = await service.regenerate_roadmap(profile_id=profile_id, roadmap_id=roadmap_id)
    return envelope(data=roadmap.model_dump())
