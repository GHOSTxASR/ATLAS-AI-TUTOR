from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_db
from app.dependencies import get_settings_dependency
from app.schemas.graph import (
    GraphEdgeCreate,
    GraphEnrichRequest,
    GraphNodeCreate,
    GraphNodeUpdate,
)
from app.services.graph_service import GraphService

router = APIRouter(prefix="/api/v1/profiles/{profile_id}/graph", tags=["graph"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_graph_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> GraphService:
    return GraphService(session=session, settings=settings)


@router.get("", response_model=dict)
async def get_graph(
    profile_id: str,
    service: GraphService = Depends(get_graph_service),
):
    data = await service.get_graph_data(profile_id=profile_id)
    return envelope(data=data.model_dump())


@router.post("/nodes", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_node(
    profile_id: str,
    data: GraphNodeCreate,
    service: GraphService = Depends(get_graph_service),
):
    node = await service.create_node(profile_id=profile_id, data=data)
    return envelope(data=node.model_dump())


@router.patch("/nodes/{node_id}", response_model=dict)
async def update_node(
    profile_id: str,
    node_id: str,
    data: GraphNodeUpdate,
    service: GraphService = Depends(get_graph_service),
):
    node = await service.update_node(profile_id=profile_id, node_id=node_id, data=data)
    return envelope(data=node.model_dump())


@router.delete("/nodes/{node_id}", response_model=dict)
async def delete_node(
    profile_id: str,
    node_id: str,
    service: GraphService = Depends(get_graph_service),
):
    deleted = await service.delete_node(profile_id=profile_id, node_id=node_id)
    return envelope(data={"deleted": deleted})


@router.post("/edges", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_edge(
    profile_id: str,
    data: GraphEdgeCreate,
    service: GraphService = Depends(get_graph_service),
):
    edge = await service.create_edge(profile_id=profile_id, data=data)
    return envelope(data=edge.model_dump())


@router.delete("/edges", response_model=dict)
async def delete_edge(
    profile_id: str,
    source: str = Query(..., description="Source node ID"),
    target: str = Query(..., description="Target node ID"),
    service: GraphService = Depends(get_graph_service),
):
    deleted = await service.delete_edge(profile_id=profile_id, source=source, target=target)
    return envelope(data={"deleted": deleted})


@router.post("/enrich", response_model=dict)
async def enrich_graph(
    profile_id: str,
    data: GraphEnrichRequest,
    service: GraphService = Depends(get_graph_service),
):
    graph = await service.enrich_from_text(profile_id=profile_id, data=data)
    return envelope(data=graph.model_dump())


@router.get("/search", response_model=dict)
async def search_nodes(
    profile_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    service: GraphService = Depends(get_graph_service),
):
    results = await service.search_nodes(profile_id=profile_id, query=q)
    return envelope(data=[n.model_dump() for n in results])


@router.get("/path", response_model=dict)
async def get_concept_path(
    profile_id: str,
    source_id: str = Query(..., description="Starting concept node ID"),
    target_id: str = Query(..., description="Target concept node ID"),
    service: GraphService = Depends(get_graph_service),
):
    path_res = await service.find_concept_path(
        profile_id=profile_id, source_id=source_id, target_id=target_id
    )
    return envelope(data=path_res.model_dump())
