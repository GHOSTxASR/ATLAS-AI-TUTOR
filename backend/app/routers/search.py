from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.db.repositories.profile_repo import ProfileRepository
from app.dependencies import get_settings_dependency
from app.exceptions import AtlasError
from app.rag.retriever import MultiSourceRetriever
from app.schemas.search import (
    GlobalCategory,
    GlobalSearchRequest,
    SearchRequest,
    SearchResultItem,
)
from app.services.global_search_service import GlobalSearchService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/search", tags=["search"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_global_search_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> GlobalSearchService:
    return GlobalSearchService(session=session, settings=settings)


@router.post("", response_model=dict, status_code=status.HTTP_200_OK)
async def semantic_search(
    profile_id: str,
    payload: SearchRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
):
    profile_repo = ProfileRepository(session)
    profile = await profile_repo.get_by_id(profile_id)
    if not profile:
        raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    retriever = MultiSourceRetriever(settings=settings)
    results = await retriever.retrieve(
        profile_id=profile_id,
        query=payload.query,
        top_k=payload.top_k,
        sources=payload.sources,  # type: ignore
        doc_ids=payload.document_ids,
        file_type=payload.file_type,
        category=payload.category,
        roadmap_node_id=payload.roadmap_node_id,
    )

    items = [
        SearchResultItem(
            id=r.id,
            source_type=r.source_type,
            source_id=r.source_id,
            profile_id=r.profile_id,
            text=r.text,
            score=r.score,
            metadata=r.metadata,
        ).model_dump()
        for r in results
    ]

    response_data = {
        "query": payload.query,
        "total": len(items),
        "results": items,
    }
    return envelope(data=response_data)


@router.post("/global", response_model=dict, status_code=status.HTTP_200_OK)
async def global_search_post(
    profile_id: str,
    payload: GlobalSearchRequest,
    service: GlobalSearchService = Depends(get_global_search_service),
):
    res = await service.global_search(profile_id=profile_id, request=payload)
    return envelope(data=res.model_dump())


@router.get("/global", response_model=dict, status_code=status.HTTP_200_OK)
async def global_search_get(
    profile_id: str,
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(5, ge=1, le=20, description="Max items per category"),
    include_semantic: bool = Query(True, description="Include semantic vector matches"),
    categories: list[GlobalCategory] | None = Query(None, description="Categories filter"),
    service: GlobalSearchService = Depends(get_global_search_service),
):
    req = GlobalSearchRequest(
        query=q,
        categories=categories,
        limit_per_category=limit,
        include_semantic=include_semantic,
    )
    res = await service.global_search(profile_id=profile_id, request=req)
    return envelope(data=res.model_dump())
