from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query

from app.config import Settings
from app.dependencies import get_settings_dependency
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


def get_settings_service(settings: Settings = Depends(get_settings_dependency)) -> SettingsService:
    return SettingsService(settings)


@router.get("/providers", response_model=dict)
async def list_providers(service: SettingsService = Depends(get_settings_service)):
    """List all supported AI providers with their configuration status."""
    return envelope(data=service.list_providers())


@router.get("/models", response_model=dict)
async def list_models(
    provider: str | None = Query(None, description="Provider ID to query"),
    refresh: bool = Query(False, description="Bypass the cached list and re-query the provider"),
    service: SettingsService = Depends(get_settings_service),
):
    """List models the provider currently offers.

    Fetched live so retired models disappear and new ones (including new free
    tiers) show up without a release. Falls back to a small static list when
    the provider cannot be reached; `source` says which was used.
    """
    return envelope(data=await service.list_models(provider=provider, refresh=refresh))


@router.get("/embedding-models", response_model=dict)
async def list_embedding_models(
    provider: str | None = Query(None, description="Provider ID to query"),
    refresh: bool = Query(False, description="Bypass the cached list and re-query the provider"),
    service: SettingsService = Depends(get_settings_service),
):
    """List embedding models the provider currently offers.

    Also reports which models the existing vector index was built with, so the
    UI can warn that switching requires reprocessing documents.
    """
    return envelope(data=await service.list_embedding_models(provider=provider, refresh=refresh))


@router.post("/test-connection", response_model=dict)
async def test_connection(
    body: dict[str, Any] | None = None,
    service: SettingsService = Depends(get_settings_service),
):
    """Test connection with the specified or active provider."""
    provider = (body or {}).get("provider") if body else None
    result = await service.test_connection(provider=provider)
    return envelope(data=result)


@router.post("/provider", response_model=dict)
async def set_provider(body: dict[str, str], service: SettingsService = Depends(get_settings_service)):
    """Update the active provider, model, and (optionally) API key.

    Body: {"provider": "gemini", "api_key": "...", "model": "gemini-2.0-flash"}
    The API key, if provided, is encrypted at rest and never echoed back.
    """
    data = service.set_provider(
        provider=body.get("provider", ""),
        api_key=body.get("api_key", ""),
        model=body.get("model", ""),
        embedding_model=body.get("embedding_model", ""),
    )
    return envelope(data=data)


@router.delete("/apikey", response_model=dict)
async def delete_api_key(provider: str, service: SettingsService = Depends(get_settings_service)):
    """Remove a stored API key for the given provider."""
    service.delete_api_key(provider)
    return envelope(data={"success": True})
