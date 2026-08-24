"""Embeddings may run on a provider other than the one serving chat.

Tying them together meant choosing a chat provider without an embeddings API
(OpenRouter, Groq, Anthropic, DeepSeek) silently took document search down with
it, with no way to keep one without the other.
"""

from __future__ import annotations

import pytest

from app.pipelines.embedder import DocumentEmbedder, EmbeddingUnavailableError


def _settings(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "split-data"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from app.config import get_settings

    get_settings.cache_clear()
    return get_settings()


def test_embedding_provider_defaults_to_the_chat_provider(monkeypatch, tmp_path):
    """An unset value must behave exactly as it did before the split.

    Set to empty rather than deleted: the developer's own .env is loaded into
    the environment, so deleting the variable let a real local setting decide
    the result and the test passed or failed depending on whose machine it ran
    on.
    """
    settings = _settings(
        monkeypatch, tmp_path, ATLAS_MODEL_PROVIDER="openai", ATLAS_EMBEDDING_PROVIDER=""
    )
    assert settings.model.embedding_provider == ""
    assert settings.model.effective_embedding_provider == "openai"


def test_embedding_provider_overrides_the_chat_provider(monkeypatch, tmp_path):
    settings = _settings(
        monkeypatch,
        tmp_path,
        ATLAS_MODEL_PROVIDER="openrouter",
        ATLAS_EMBEDDING_PROVIDER="gemini",
    )
    assert settings.model.provider == "openrouter"
    assert settings.model.effective_embedding_provider == "gemini"


def test_embedder_follows_the_embedding_provider(monkeypatch, tmp_path):
    """The chat provider has no embeddings API; the embedding provider does."""
    settings = _settings(
        monkeypatch,
        tmp_path,
        ATLAS_MODEL_PROVIDER="openrouter",
        ATLAS_EMBEDDING_PROVIDER="gemini",
        ATLAS_EMBEDDING_BACKEND="auto",
        ATLAS_EMBEDDING_MODEL="",
    )
    embedder = DocumentEmbedder(settings=settings)
    assert embedder.provider == "gemini"
    assert embedder.embedding_model == "gemini-embedding-001"


async def test_chat_provider_without_embeddings_no_longer_blocks_indexing(
    monkeypatch, tmp_path
):
    """Regression: this combination used to raise regardless of the split."""
    settings = _settings(
        monkeypatch,
        tmp_path,
        ATLAS_MODEL_PROVIDER="openrouter",
        ATLAS_EMBEDDING_PROVIDER="gemini",
        ATLAS_EMBEDDING_BACKEND="auto",
    )
    embedder = DocumentEmbedder(settings=settings)
    monkeypatch.setattr(
        "app.pipelines.embedder.resolve_api_key", lambda *a, **k: "test-key"
    )

    async def _fake(texts, api_key):
        return [[0.1] * 8 for _ in texts]

    monkeypatch.setattr(embedder, "_call_gemini_embeddings", _fake)
    vectors = await embedder.generate_embeddings(["chunk one", "chunk two"])
    assert len(vectors) == 2


async def test_still_raises_when_the_embedding_provider_itself_cannot_embed(
    monkeypatch, tmp_path
):
    """Splitting must not let an impossible combination through silently."""
    settings = _settings(
        monkeypatch,
        tmp_path,
        ATLAS_MODEL_PROVIDER="gemini",
        ATLAS_EMBEDDING_PROVIDER="groq",
        ATLAS_EMBEDDING_BACKEND="auto",
    )
    embedder = DocumentEmbedder(settings=settings)
    with pytest.raises(EmbeddingUnavailableError) as excinfo:
        await embedder.generate_embeddings(["text"])
    assert "no embeddings API" in str(excinfo.value)
