from __future__ import annotations

import os
from typing import Any

from app.config import Settings, project_root, get_settings
from app.exceptions import LearningOSError
from app.models.model_catalog import FALLBACK_MODELS, get_models
from app.models.provider_factory import get_all_providers, get_model_client
from app.models.resilience import provider_error_from
from app.security.keystore import KeyStore



class SettingsService:
    """Owns provider/model selection and API key persistence.

    API keys are never written to `.env` or `settings.toml`. They are
    encrypted at rest via `KeyStore` (Fernet) and only the active provider
    and model name are persisted to `.env` so the backend knows what to use
    on the next startup.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.keystore = KeyStore(settings)

    def list_providers(self) -> dict[str, object]:
        enriched: list[dict[str, object]] = []
        for provider in get_all_providers():
            env_key = provider.get("env_key", "")
            has_env_key = bool(env_key and os.getenv(env_key))
            has_stored_key = bool(self.keystore.get(provider["id"]))
            enriched.append(
                {
                    **provider,
                    "key_set": has_env_key or has_stored_key or env_key == "",
                    "active": self.settings.model.provider.lower() == provider["id"],
                }
            )

        return {
            "providers": enriched,
            "active_provider": self.settings.model.provider.lower(),
            "active_model": self.settings.model.chat_model,
        }

    async def list_models(
        self, provider: str | None = None, *, refresh: bool = False
    ) -> dict[str, Any]:
        """Current models for a provider, fetched live where possible."""
        p = (provider or self.settings.model.provider).strip().lower()
        catalog = await get_models(self.settings, p, refresh=refresh)
        return catalog.to_dict()

    def _model_for_provider(self, provider: str) -> str:
        """Chat model to use when talking to ``provider``.

        Keeps the configured model when it belongs to the active provider,
        otherwise falls back to that provider's own default.
        """
        if provider == self.settings.model.provider.strip().lower():
            return self.settings.model.chat_model

        info = next((p for p in get_all_providers() if p["id"] == provider), None)
        if info and info.get("default_model"):
            return str(info["default_model"])
        catalog = FALLBACK_MODELS.get(provider)
        return catalog[0] if catalog else self.settings.model.chat_model

    async def test_connection(self, provider: str | None = None) -> dict[str, Any]:
        """Test connectivity to a specific provider by making a lightweight API call."""
        p = (provider or self.settings.model.provider).strip().lower()
        try:
            # Build temporary settings with the target provider so we test the
            # right one. The chat model must move with it: testing OpenAI while
            # Gemini is active previously sent a Gemini model name to OpenAI.
            from dataclasses import replace

            test_model_settings = replace(
                self.settings.model,
                provider=p,
                chat_model=self._model_for_provider(p),
            )
            test_settings = replace(self.settings, model=test_model_settings)
            client = get_model_client(test_settings)
            try:
                # Make a minimal chat request to verify the key works
                from app.models.abstraction import ChatMessage as LLMMessage
                await client.chat_complete(
                    messages=[LLMMessage(role="user", content="Say 'ok'")],
                    model=test_settings.model.chat_model,
                    max_tokens=5,
                )
                return {"status": "ok", "provider": p, "model_info": {"provider": p, "model": test_settings.model.chat_model}}
            finally:
                await client.close()
        except Exception as e:
            # str(e) on a raw httpx error contains the request URL, which for
            # key-in-query providers is the API key itself.
            return {"status": "error", "provider": p, "error": provider_error_from(e, p).message}

    def set_provider(self, provider: str, api_key: str, model: str) -> dict[str, object]:
        # Invalidate the cached settings so all services pick up the new config
        get_settings.cache_clear()

        provider = provider.strip().lower()
        model = model.strip()

        all_providers = get_all_providers()
        provider_info = next((p for p in all_providers if p["id"] == provider), None)
        if not provider_info:
            raise LearningOSError(
                status_code=422,
                code="INVALID_PROVIDER",
                message=f"Unknown provider: {provider}",
                details={"provider": provider},
            )

        env_key = provider_info.get("env_key", "")
        model = model or provider_info.get("default_model", "")

        if api_key and env_key:
            # Persist encrypted for future restarts, and set it for the
            # current process so it can be used immediately.
            self.keystore.set(provider, api_key)
            os.environ[env_key] = api_key

        self._persist_env_choice("LEARNINGOS_MODEL_PROVIDER", provider)
        os.environ["LEARNINGOS_MODEL_PROVIDER"] = provider

        self._persist_env_choice("LEARNINGOS_CHAT_MODEL", model)
        os.environ["LEARNINGOS_CHAT_MODEL"] = model

        # Clear cache again after env vars are updated so next get_settings()
        # picks up the new environment values
        get_settings.cache_clear()

        return {
            "provider": provider,
            "model": model,
            "key_persisted": bool(api_key and env_key),
            "message": f"Switched to {provider_info['label']}.",
        }

    def delete_api_key(self, provider: str) -> None:
        provider = provider.strip().lower()
        all_providers = get_all_providers()
        provider_info = next((p for p in all_providers if p["id"] == provider), None)
        if not provider_info:
            raise LearningOSError(
                status_code=422,
                code="INVALID_PROVIDER",
                message=f"Unknown provider: {provider}",
                details={"provider": provider},
            )
        self.keystore.delete(provider)
        env_key = provider_info.get("env_key", "")
        if env_key:
            os.environ.pop(env_key, None)
        # Invalidate cached settings so services pick up the key removal
        get_settings.cache_clear()

    @staticmethod
    def _persist_env_choice(key: str, value: str) -> None:
        """Set or update a non-secret key/value pair in the repo-root `.env` file."""
        env_path = project_root() / ".env"
        env_content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        lines = env_content.splitlines()

        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
