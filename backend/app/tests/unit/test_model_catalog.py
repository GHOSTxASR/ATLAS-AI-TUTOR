"""Model discovery must reflect what the provider offers *today*.

The catalogue used to be a hardcoded table. It went stale silently: it still
listed ``google/gemini-2.0-flash-exp:free`` after OpenRouter retired it, while
hiding hundreds of models the user could actually pick, including free ones.
"""

from __future__ import annotations

import httpx
import pytest

from app.models import model_catalog
from app.models.model_catalog import get_models


@pytest.fixture(autouse=True)
def _clear_cache():
    model_catalog.clear_cache()
    yield
    model_catalog.clear_cache()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "catalog-data"))
    from app.config import get_settings

    get_settings.cache_clear()
    return get_settings()


def _patch_transport(monkeypatch, handler):
    """Route every AsyncClient in the catalog module through `handler`."""
    real_init = httpx.AsyncClient.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)


OPENROUTER_BODY = {
    "data": [
        {
            "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "name": "NVIDIA Nemotron 3 Ultra",
            "context_length": 1000000,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "anthropic/claude-sonnet-4",
            "name": "Claude Sonnet 4",
            "context_length": 200000,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        },
        {
            "id": "openai/text-embedding-3-small",
            "name": "Embedding",
            "pricing": {"prompt": "0.00000002", "completion": "0"},
        },
    ]
}


async def test_live_list_replaces_the_static_table(settings, monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, json=OPENROUTER_BODY))

    catalog = await get_models(settings, "openrouter", refresh=True)

    assert catalog.source == "live"
    ids = [m.id for m in catalog.models]
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in ids
    # The retired hardcoded entry must not appear just because it was in code.
    assert "google/gemini-2.0-flash-exp:free" not in ids


async def test_free_models_are_flagged_and_sorted_first(settings, monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, json=OPENROUTER_BODY))

    catalog = await get_models(settings, "openrouter", refresh=True)

    assert catalog.models[0].free is True
    assert catalog.models[0].context_length == 1_000_000
    assert sum(1 for m in catalog.models if m.free) == 1


async def test_non_chat_models_are_excluded(settings, monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, json=OPENROUTER_BODY))

    catalog = await get_models(settings, "openrouter", refresh=True)

    assert not any("embedding" in m.id for m in catalog.models)


async def test_provider_failure_falls_back_without_raising(settings, monkeypatch):
    """A dead provider must still leave the Settings page usable."""
    _patch_transport(monkeypatch, lambda req: httpx.Response(500, text="boom"))

    catalog = await get_models(settings, "openrouter", refresh=True)

    assert catalog.source == "fallback"
    assert catalog.error
    assert catalog.models, "fallback list must not be empty"


async def test_missing_key_explains_itself(settings, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "app.models.model_catalog.resolve_api_key", lambda *a, **k: ""
    )

    catalog = await get_models(settings, "openai", refresh=True)

    assert catalog.source == "fallback"
    assert "API key" in (catalog.error or "")


async def test_results_are_cached_until_refreshed(settings, monkeypatch):
    calls: list[str] = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=OPENROUTER_BODY)

    _patch_transport(monkeypatch, handler)

    await get_models(settings, "openrouter", refresh=True)
    await get_models(settings, "openrouter")
    assert len(calls) == 1, "second read should come from cache"

    await get_models(settings, "openrouter", refresh=True)
    assert len(calls) == 2, "refresh must re-query the provider"


async def test_gemini_keeps_only_chat_capable_models(settings, monkeypatch):
    body = {
        "models": [
            {
                "name": "models/gemini-3.7-flash",
                "displayName": "Gemini 3.7 Flash",
                "supportedGenerationMethods": ["generateContent"],
                "inputTokenLimit": 1048576,
            },
            {
                "name": "models/gemini-embedding-001",
                "displayName": "Embedding",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }
    monkeypatch.setattr("app.models.model_catalog.resolve_api_key", lambda *a, **k: "key")
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, json=body))

    catalog = await get_models(settings, "gemini", refresh=True)

    assert [m.id for m in catalog.models] == ["gemini-3.7-flash"]
    assert catalog.models[0].context_length == 1048576
