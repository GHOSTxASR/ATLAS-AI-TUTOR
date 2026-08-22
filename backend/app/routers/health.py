from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_settings_dependency

router = APIRouter(prefix="/api/v1", tags=["health"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


@router.get("/health")
async def health(settings: Settings = Depends(get_settings_dependency)):
    return envelope(
        {
            "status": "ok",
            "name": settings.app.name,
            "version": settings.app.version,
            "environment": settings.app.environment,
        }
    )


@router.get("/health/storage")
async def storage_health(settings: Settings = Depends(get_settings_dependency)):
    paths = settings.paths
    return envelope(
        {
            "status": "ok",
            "data_dir": str(paths.data_dir),
            "sqlite_dir": str(paths.sqlite_dir),
            "chroma_dir": str(paths.chroma_dir),
            "graph_dir": str(paths.graph_dir),
            "profiles_dir": str(paths.profiles_dir),
        }
    )

