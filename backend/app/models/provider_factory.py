from __future__ import annotations

import os

from app.config import Settings
from app.models.abstraction import BaseModelClient
from app.security.keystore import KeyStore
from app.security.redaction import register_secret

# ─────────────────────────────────────────────────────────────
# Provider registry
# For OpenAI-compatible providers we reuse the OpenAI client
# with a different base_url and API key env var.
# ─────────────────────────────────────────────────────────────
OPENAI_COMPATIBLE_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "label": "OpenAI",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "label": "Groq (free tier available)",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "label": "DeepSeek",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "default_model": "mistral-large-latest",
        "label": "Mistral AI",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        # A specific model id here goes stale the moment OpenRouter retires it
        # (the previous default, google/gemini-2.0-flash-exp:free, no longer
        # exists). `openrouter/auto` routes to a currently-available model, so
        # it stays valid; the live model list covers deliberate choices.
        "default_model": "openrouter/auto",
        "label": "OpenRouter (many free models)",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "label": "Together AI",
    },
}


def resolve_api_key(settings: Settings, provider: str, env_key: str) -> str:
    """Resolve an API key for a provider.

    Precedence: process environment variable (power-user/dev override) then
    the local encrypted keystore (set via the Settings UI/API).
    """
    if env_key:
        env_value = os.getenv(env_key, "")
        if env_value:
            # Teach the redaction layer about env-supplied keys too; KeyStore
            # registers its own on read.
            register_secret(env_value)
            return env_value
    return KeyStore(settings).get(provider) or ""


def register_known_secrets(settings: Settings) -> int:
    """Pre-register every configured API key so redaction works from startup.

    Without this, a key could appear in a log line emitted before anything had
    cause to resolve it.
    """
    registered = 0
    for provider in get_all_providers():
        env_key = provider.get("env_key", "")
        if resolve_api_key(settings, provider["id"], env_key):
            registered += 1
    return registered


def get_all_providers() -> list[dict[str, str]]:
    """Return a list of all supported providers for the settings UI."""
    providers = []

    # Gemini (native)
    providers.append({
        "id": "gemini",
        "label": "Google Gemini (free tier available)",
        "env_key": "GEMINI_API_KEY",
        "default_model": "gemini-3.7-flash",
        "docs_url": "https://aistudio.google.com/app/apikey",
    })

    # OpenAI-compatible providers
    for provider_id, info in OPENAI_COMPATIBLE_PROVIDERS.items():
        docs_urls = {
            "openai": "https://platform.openai.com/api-keys",
            "groq": "https://console.groq.com/keys",
            "deepseek": "https://platform.deepseek.com/api_keys",
            "mistral": "https://console.mistral.ai/api-keys",
            "openrouter": "https://openrouter.ai/keys",
            "together": "https://api.together.xyz/settings/api-keys",
        }
        providers.append({
            "id": provider_id,
            "label": info["label"],
            "env_key": info["env_key"],
            "default_model": info["default_model"],
            "docs_url": docs_urls.get(provider_id, ""),
        })

    # Anthropic (native)
    providers.append({
        "id": "anthropic",
        "label": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "docs_url": "https://console.anthropic.com/settings/keys",
    })

    # Ollama (local, no key)
    providers.append({
        "id": "ollama",
        "label": "Ollama (local, free)",
        "env_key": "",
        "default_model": "llama3.1",
        "docs_url": "https://ollama.com/download",
    })

    return providers


def get_model_client(settings: Settings, api_key_override: str = "") -> BaseModelClient:
    """Create and return the appropriate model client based on settings.

    Keys come from the environment or the encrypted keystore. Pass
    ``api_key_override`` to build a client around a key that has not been saved
    yet -- "Test Connection" uses this so it verifies the key the user is
    looking at rather than the last one they stored. The override is used for
    this client only and is never persisted.
    """
    provider = settings.model.provider.lower()

    def _key(provider_id: str, env_key: str) -> str:
        if api_key_override:
            register_secret(api_key_override)
            return api_key_override
        return resolve_api_key(settings, provider_id, env_key)

    # --- Google Gemini (native client) ---
    if provider == "gemini":
        from app.models.gemini_client import GeminiClient

        api_key = _key("gemini", "GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "No Gemini API key configured. Set it on the Settings page, or set the "
                "GEMINI_API_KEY environment variable. Get a free key at "
                "https://aistudio.google.com/app/apikey"
            )
        return GeminiClient(
            api_key=api_key,
            default_model=settings.model.chat_model,
        )

    # --- Anthropic (native client) ---
    if provider == "anthropic":
        from app.models.anthropic_client import AnthropicClient

        api_key = _key("anthropic", "ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "No Anthropic API key configured. Set it on the Settings page, or set the "
                "ANTHROPIC_API_KEY environment variable. Get a key at "
                "https://console.anthropic.com/settings/keys"
            )
        return AnthropicClient(
            api_key=api_key,
            default_model=settings.model.chat_model,
        )

    # --- Ollama (local, no key) ---
    if provider == "ollama":
        from app.models.ollama_client import OllamaClient

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaClient(
            base_url=base_url,
            default_model=settings.model.chat_model,
        )

    # --- OpenAI-compatible providers ---
    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        from app.models.openai_client import OpenAIClient

        info = OPENAI_COMPATIBLE_PROVIDERS[provider]
        api_key = _key(provider, info["env_key"])
        if not api_key:
            raise ValueError(
                f"No {info['label']} API key configured. Set it on the Settings page, or set the "
                f"{info['env_key']} environment variable."
            )
        return OpenAIClient(
            api_key=api_key,
            base_url=info["base_url"],
            default_model=settings.model.chat_model or info["default_model"],
        )

    # --- Unknown provider ---
    supported = ", ".join(
        ["gemini", "anthropic", "ollama"] + list(OPENAI_COMPATIBLE_PROVIDERS.keys())
    )
    raise ValueError(
        f"Unknown model provider: '{provider}'. Supported providers: {supported}"
    )
