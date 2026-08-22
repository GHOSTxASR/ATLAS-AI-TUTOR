"""Live model discovery.

Provider line-ups change constantly - free tiers appear and disappear, model
ids are renamed and retired. A hardcoded catalogue is stale the moment it ships
(it still advertised ``google/gemini-2.0-flash-exp:free`` while OpenRouter had
moved on and gained hundreds of models, including free ones like
``nvidia/nemotron-3-ultra-550b-a55b:free``).

Each provider is queried for its current list. The static table survives only as
a last resort when the network or the key is unavailable, and the response says
which source was used so the UI can be honest about it. Whatever happens, the
user can still type a model id by hand.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.models.provider_factory import OPENAI_COMPATIBLE_PROVIDERS, resolve_api_key
from app.models.resilience import provider_error_from

logger = logging.getLogger(__name__)

# Model lists change far slower than they are viewed; this keeps the Settings
# page snappy without pinning a stale list for the session.
CACHE_TTL_SECONDS = 600
FETCH_TIMEOUT_SECONDS = 12.0

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

# Ids that are not chat models. Provider "list models" endpoints happily return
# embedding, speech and image endpoints alongside the chat ones.
_NON_CHAT_PATTERNS = re.compile(
    r"(embed|embedding|tts|whisper|audio|speech|transcribe|dall-e|image|"
    r"moderation|rerank|guard|vision-only|codestral-embed)",
    re.IGNORECASE,
)

# Last-resort list, used only when a live lookup is impossible. Deliberately
# short: it exists to keep the UI usable offline, not to be authoritative.
FALLBACK_MODELS: dict[str, list[str]] = {
    "gemini": ["gemini-3.7-flash", "gemini-3.5-flash"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"],
    "ollama": ["llama3.1", "mistral", "phi3", "qwen2.5"],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "mistral": ["mistral-large-latest", "mistral-small-latest"],
    "openrouter": ["openrouter/auto"],
    "together": ["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
}


@dataclass
class ModelInfo:
    id: str
    label: str = ""
    free: bool = False
    context_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label or self.id,
            "free": self.free,
            "context_length": self.context_length,
        }


@dataclass
class ModelCatalog:
    provider: str
    models: list[ModelInfo] = field(default_factory=list)
    source: str = "fallback"  # "live" | "fallback"
    error: str | None = None
    fetched_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "models": [m.to_dict() for m in self.models],
            "source": self.source,
            "error": self.error,
            "free_count": sum(1 for m in self.models if m.free),
        }


_cache: dict[str, ModelCatalog] = {}


def _is_chat_model(model_id: str) -> bool:
    return not _NON_CHAT_PATTERNS.search(model_id)


def _fallback(provider: str, error: str | None) -> ModelCatalog:
    ids = FALLBACK_MODELS.get(provider, [])
    return ModelCatalog(
        provider=provider,
        models=[ModelInfo(id=i, label=i) for i in ids],
        source="fallback",
        error=error,
        fetched_at=time.time(),
    )


# ── Per-provider lookups ──────────────────────────────────────────────


async def _fetch_openai_compatible(
    provider: str, base_url: str, api_key: str
) -> list[ModelInfo]:
    """`GET /models` - the shape shared by OpenAI, Groq, DeepSeek, Mistral,
    Together and OpenRouter. OpenRouter additionally returns pricing and
    context length, which is how free models are identified."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
        resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    out: list[ModelInfo] = []
    for entry in payload.get("data", []):
        model_id = entry.get("id")
        if not model_id or not _is_chat_model(model_id):
            continue

        pricing = entry.get("pricing") or {}
        free = model_id.endswith(":free") or (
            _is_zero(pricing.get("prompt")) and _is_zero(pricing.get("completion"))
        )
        out.append(
            ModelInfo(
                id=model_id,
                label=entry.get("name") or model_id,
                free=free,
                context_length=entry.get("context_length"),
            )
        )
    return out


def _is_zero(value: Any) -> bool:
    if value is None:
        return False
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


async def _fetch_gemini(api_key: str) -> list[ModelInfo]:
    """Gemini reports which methods each model supports; keep the chat ones."""
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS, headers={"x-goog-api-key": api_key}
    ) as client:
        resp = await client.get(f"{GEMINI_BASE_URL}/models?pageSize=1000")
        resp.raise_for_status()
        payload = resp.json()

    out: list[ModelInfo] = []
    for entry in payload.get("models", []):
        methods = entry.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        model_id = str(entry.get("name", "")).removeprefix("models/")
        if not model_id:
            continue
        out.append(
            ModelInfo(
                id=model_id,
                label=entry.get("displayName") or model_id,
                context_length=entry.get("inputTokenLimit"),
            )
        )
    return out


async def _fetch_anthropic(api_key: str) -> list[ModelInfo]:
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    ) as client:
        resp = await client.get(f"{ANTHROPIC_BASE_URL}/v1/models?limit=1000")
        resp.raise_for_status()
        payload = resp.json()

    return [
        ModelInfo(id=e["id"], label=e.get("display_name") or e["id"])
        for e in payload.get("data", [])
        if e.get("id")
    ]


async def _fetch_ollama(base_url: str) -> list[ModelInfo]:
    """Locally pulled models, so this is the only truly authoritative list."""
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
        resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
        resp.raise_for_status()
        payload = resp.json()

    return [
        ModelInfo(id=e["name"], label=e["name"], free=True)
        for e in payload.get("models", [])
        if e.get("name")
    ]


# ── Entry point ───────────────────────────────────────────────────────


async def get_models(
    settings: Settings, provider: str, *, refresh: bool = False
) -> ModelCatalog:
    """Current models for `provider`, live where possible.

    Never raises: a failure degrades to the static list with `source` set to
    "fallback" and `error` explaining why, so the Settings page always renders
    and manual entry always remains available.
    """
    provider = (provider or "").strip().lower()

    cached = _cache.get(provider)
    if cached and not refresh and (time.time() - cached.fetched_at) < CACHE_TTL_SECONDS:
        return cached

    try:
        models = await _dispatch(settings, provider)
    except Exception as exc:
        message = provider_error_from(exc, provider).message
        logger.warning("Live model lookup failed for %s: %s", provider, message)
        result = _fallback(provider, message)
        _cache[provider] = result
        return result

    if not models:
        result = _fallback(provider, "The provider returned no chat models.")
        _cache[provider] = result
        return result

    # Free first, then alphabetically - free tiers are what users hunt for.
    models.sort(key=lambda m: (not m.free, m.id.lower()))
    result = ModelCatalog(
        provider=provider, models=models, source="live", fetched_at=time.time()
    )
    _cache[provider] = result
    return result


async def _dispatch(settings: Settings, provider: str) -> list[ModelInfo]:
    import os

    if provider == "ollama":
        return await _fetch_ollama(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    if provider == "gemini":
        key = resolve_api_key(settings, "gemini", "GEMINI_API_KEY")
        if not key:
            raise ValueError("Add a Gemini API key to load the live model list.")
        return await _fetch_gemini(key)

    if provider == "anthropic":
        key = resolve_api_key(settings, "anthropic", "ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Add an Anthropic API key to load the live model list.")
        return await _fetch_anthropic(key)

    info = OPENAI_COMPATIBLE_PROVIDERS.get(provider)
    if not info:
        raise ValueError(f"Unknown provider: {provider}")

    key = resolve_api_key(settings, provider, info["env_key"])
    # OpenRouter publishes its catalogue without authentication, so the list
    # works before the user has pasted a key.
    if not key and provider != "openrouter":
        raise ValueError(f"Add a {info['label']} API key to load the live model list.")

    return await _fetch_openai_compatible(provider, info["base_url"], key)


def clear_cache() -> None:
    """Drop cached catalogues. Intended for tests and key changes."""
    _cache.clear()
