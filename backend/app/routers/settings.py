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
    service: SettingsService = Depends(get_settings_service),
):
    """List available models for the specified or active provider."""
    models = service.list_models(provider=provider)
    return envelope(data={"provider": provider or "active", "models": models})


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
    )
    return envelope(data=data)


@router.delete("/apikey", response_model=dict)
async def delete_api_key(provider: str, service: SettingsService = Depends(get_settings_service)):
    """Remove a stored API key for the given provider."""
    service.delete_api_key(provider)
    return envelope(data={"success": True})
