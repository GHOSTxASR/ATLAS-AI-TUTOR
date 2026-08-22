from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.analytics import (
    AnalyticsEventCreate,
    AnalyticsEventResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/analytics", tags=["analytics"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_analytics_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> AnalyticsService:
    return AnalyticsService(session=session, settings=settings)


@router.get("/overview", response_model=dict)
async def get_overview(
    profile_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    overview = await service.get_overview(profile_id=profile_id)
    return envelope(data=overview.model_dump())


@router.get("/heatmap", response_model=dict)
async def get_heatmap(
    profile_id: str,
    days: int = Query(30, ge=7, le=365, description="Number of days to include"),
    service: AnalyticsService = Depends(get_analytics_service),
):
    items = await service.get_heatmap(profile_id=profile_id, days=days)
    return envelope(data=[i.model_dump() for i in items])


@router.get("/mastery", response_model=dict)
async def get_mastery(
    profile_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    mastery = await service.get_mastery_distribution(profile_id=profile_id)
    return envelope(data=mastery.model_dump())


@router.get("/velocity", response_model=dict)
async def get_velocity(
    profile_id: str,
    days: int = Query(14, ge=7, le=90, description="Number of days for velocity analysis"),
    service: AnalyticsService = Depends(get_analytics_service),
):
    velocity = await service.get_learning_velocity(profile_id=profile_id, days=days)
    return envelope(data=[v.model_dump() for v in velocity])


@router.get("/weaknesses", response_model=dict)
async def get_weaknesses(
    profile_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
):
    weaknesses = await service.get_weaknesses(profile_id=profile_id)
    return envelope(data=[w.model_dump() for w in weaknesses])


@router.post("/events", response_model=dict, status_code=status.HTTP_201_CREATED)
async def log_event(
    profile_id: str,
    data: AnalyticsEventCreate,
    service: AnalyticsService = Depends(get_analytics_service),
):
    event = await service.log_event(profile_id=profile_id, data=data)
    return envelope(data=AnalyticsEventResponse.model_validate(event).model_dump())
