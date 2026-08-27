from __future__ import annotations

import os
from typing import Any

from app.config import Settings, project_root, get_settings
from app.exceptions import AtlasError
from app.models.model_catalog import (
    FALLBACK_MODELS,
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_PROVIDER,
    PROVIDERS_WITHOUT_EMBEDDINGS,
    get_models,
    indexed_embedding_models,
)
from app.models.provider_factory import get_all_providers, get_model_client
from app.models.resilience import provider_error_from
from app.security.keystore import KeyStore



#: Backends that can embed but cannot chat, so they have no place in
#: get_all_providers() and still need to be offerable for embeddings.
EMBEDDING_ONLY_PROVIDERS: list[dict[str, object]] = [
    {
        "id": LOCAL_EMBEDDING_PROVIDER,
        "label": "On this device (no API key)",
        "env_key": "",
        "default_model": LOCAL_EMBEDDING_MODEL,
        "docs_url": "",
        "key_set": True,
    }
]


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
            # Empty when embeddings follow chat; the UI needs to tell the two
            # states apart to show "same as chat" rather than a stale pick.
            "embedding_provider": self.settings.model.embedding_provider.lower(),
            # What is actually serving embeddings, which is not always what was
            # configured: with nothing set, or a chat provider that cannot
            # embed, this resolves to the local backend. The page should say so
            # rather than report a provider that is not doing the work.
            "active_embedding_provider": self._resolved_embedding_provider(),
            "providers_without_embeddings": sorted(PROVIDERS_WITHOUT_EMBEDDINGS),
            "embedding_only_providers": EMBEDDING_ONLY_PROVIDERS,
        }

    def _resolved_embedding_provider(self) -> str:
        """Ask the embedder who it would actually use.

        Constructing it is cheap -- resolution is pure config, and the ONNX
        model is only loaded when something is embedded.
        """
        from app.pipelines.embedder import DocumentEmbedder

        try:
            return DocumentEmbedder(settings=self.settings).provider
        except Exception:
            return self.settings.model.effective_embedding_provider

    async def list_models(
        self, provider: str | None = None, *, refresh: bool = False
    ) -> dict[str, Any]:
        """Current models for a provider, fetched live where possible."""
        p = (provider or self.settings.model.provider).strip().lower()
        catalog = await get_models(self.settings, p, refresh=refresh)
        return catalog.to_dict()

    async def list_embedding_models(
        self, provider: str | None = None, *, refresh: bool = False
    ) -> dict[str, Any]:
        """Embedding models for a provider, plus what is already indexed.

        Switching embedding model starts a fresh vector collection, so the
        response reports which models the existing index was built with; the UI
        uses that to warn before documents silently stop being searchable.
        """
        # Defaults to the embedding provider, not the chat one, so opening
        # Settings shows the models that would actually be used.
        p = (provider or self.settings.model.effective_embedding_provider).strip().lower()
        catalog = await get_models(self.settings, p, purpose="embedding", refresh=refresh)

        from dataclasses import replace

        from app.pipelines.embedder import DocumentEmbedder

        # Resolve for the provider being *previewed*, not the saved one, or
        # selecting Gemini would suggest OpenAI's default embedding model.
        preview = replace(
            self.settings,
            model=replace(self.settings.model, provider=p, embedding_provider=p),
        )
        active = DocumentEmbedder(settings=preview).embedding_model
        indexed = indexed_embedding_models(self.settings)

        payload = catalog.to_dict()
        payload["active_model"] = active
        payload["indexed_models"] = indexed
        payload["reindex_required"] = bool(indexed) and active not in indexed
        return payload

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

    async def test_connection(
        self, provider: str | None = None, api_key: str = ""
    ) -> dict[str, Any]:
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
            client = get_model_client(test_settings, api_key_override=api_key.strip())
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

    def set_provider(
        self,
        provider: str,
        api_key: str,
        model: str,
        embedding_model: str = "",
        embedding_provider: str = "",
    ) -> dict[str, object]:
        # Invalidate the cached settings so all services pick up the new config
        get_settings.cache_clear()

        provider = provider.strip().lower()
        model = model.strip()

        all_providers = get_all_providers()
        provider_info = next((p for p in all_providers if p["id"] == provider), None)
        if not provider_info:
            raise AtlasError(
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

        self._persist_env_choice("ATLAS_MODEL_PROVIDER", provider)
        os.environ["ATLAS_MODEL_PROVIDER"] = provider

        self._persist_env_choice("ATLAS_CHAT_MODEL", model)
        os.environ["ATLAS_CHAT_MODEL"] = model

        # Embeddings may run on a different provider from chat. An empty value
        # means "follow the chat provider", so it is written through as empty
        # rather than skipped -- otherwise clearing the split would be
        # impossible once it had been set once.
        embedding_provider = (embedding_provider or "").strip().lower()
        if embedding_provider and embedding_provider not in {p["id"] for p in all_providers}:
            raise AtlasError(
                status_code=422,
                code="INVALID_PROVIDER",
                message=f"Unknown embedding provider: {embedding_provider}",
                details={"embedding_provider": embedding_provider},
            )
        self._persist_env_choice("ATLAS_EMBEDDING_PROVIDER", embedding_provider)
        if embedding_provider:
            os.environ["ATLAS_EMBEDDING_PROVIDER"] = embedding_provider
        else:
            os.environ.pop("ATLAS_EMBEDDING_PROVIDER", None)

        # Previously read from config but never writable from the UI.
        embedding_model = (embedding_model or "").strip()
        if embedding_model:
            self._persist_env_choice("ATLAS_EMBEDDING_MODEL", embedding_model)
            os.environ["ATLAS_EMBEDDING_MODEL"] = embedding_model

        # Clear cache again after env vars are updated so next get_settings()
        # picks up the new environment values
        get_settings.cache_clear()

        return {
            "provider": provider,
            "model": model,
            "embedding_model": embedding_model,
            "embedding_provider": embedding_provider,
            "key_persisted": bool(api_key and env_key),
            "message": f"Switched to {provider_info['label']}.",
        }

    def delete_api_key(self, provider: str) -> None:
        provider = provider.strip().lower()
        all_providers = get_all_providers()
        provider_info = next((p for p in all_providers if p["id"] == provider), None)
        if not provider_info:
            raise AtlasError(
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

        legacy_key = key.replace("ATLAS_", "LEARNINGOS_", 1)
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                new_lines.append(f"{key}={value}")
                found = True
            elif legacy_key != key and stripped.startswith(f"{legacy_key}="):
                # Superseded by the renamed key; drop it so .env has one answer.
                continue
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}")

        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
