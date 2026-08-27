"""The keyless path: Atlas has to index and search before anything is configured.

Every earlier embedding backend needed either an API key or a running daemon,
so a fresh clone could not index a single document until the user had signed up
somewhere. These tests pin the behaviour that fixes that.
"""

from __future__ import annotations

import pytest

from app.models.model_catalog import (
    LOCAL_EMBEDDING_DIMENSION,
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_PROVIDER,
)
from app.pipelines.embedder import (
    _LOCAL_EMBEDDINGS_AVAILABLE,
    DocumentEmbedder,
    provider_can_embed,
)

requires_fastembed = pytest.mark.skipif(
    not _LOCAL_EMBEDDINGS_AVAILABLE, reason="fastembed is not installed"
)


def _embedder(monkeypatch, tmp_path, **env) -> DocumentEmbedder:
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "local-embed"))
    # The developer's own .env is loaded into the environment, so every key
    # that could steer provider resolution is pinned explicitly.
    for name in (
        "ATLAS_EMBEDDING_PROVIDER",
        "ATLAS_MODEL_PROVIDER",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("ATLAS_EMBEDDING_BACKEND", "auto")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from app.config import get_settings

    get_settings.cache_clear()
    return DocumentEmbedder(settings=get_settings())


def test_fresh_install_with_no_keys_uses_local_embeddings(monkeypatch, tmp_path):
    """The whole point: nothing configured, and embeddings still work."""
    embedder = _embedder(monkeypatch, tmp_path)

    assert embedder.provider == LOCAL_EMBEDDING_PROVIDER
    assert embedder.embedding_model == LOCAL_EMBEDDING_MODEL


def test_provider_without_embeddings_api_falls_back(monkeypatch, tmp_path):
    """OpenRouter can chat but cannot embed; that should not disable search."""
    embedder = _embedder(
        monkeypatch, tmp_path,
        ATLAS_MODEL_PROVIDER="openrouter",
        OPENROUTER_API_KEY="sk-test-not-a-real-key",
    )

    assert embedder.provider == LOCAL_EMBEDDING_PROVIDER


def test_explicit_choice_is_never_silently_replaced(monkeypatch, tmp_path):
    """A provider the user named stays named, even with no key to serve it.

    Falling back here would hide a misconfiguration behind results that look
    fine but came from a different model than the one asked for.
    """
    embedder = _embedder(
        monkeypatch, tmp_path, ATLAS_EMBEDDING_PROVIDER="openai"
    )

    assert embedder.provider == "openai"


def test_configured_provider_with_a_key_is_left_alone(monkeypatch, tmp_path):
    embedder = _embedder(
        monkeypatch, tmp_path,
        ATLAS_MODEL_PROVIDER="gemini",
        GEMINI_API_KEY="test-key-not-real",
    )

    assert embedder.provider == "gemini"


def test_fallback_does_not_inherit_the_old_provider_model(monkeypatch, tmp_path):
    """A model name left over from another provider must not follow the fallback.

    Someone configures Gemini, the key is later removed, and embeddings fall
    back to local -- but `embedding_model` still says "gemini-embedding-001",
    which the local backend has never heard of. Inheriting it turns a working
    fallback into a crash.
    """
    embedder = _embedder(
        monkeypatch, tmp_path, ATLAS_EMBEDDING_MODEL="gemini-embedding-001"
    )

    assert embedder.provider == LOCAL_EMBEDDING_PROVIDER
    assert embedder.embedding_model == LOCAL_EMBEDDING_MODEL


def test_hash_backend_still_wins_when_requested(monkeypatch, tmp_path):
    """The offline test backend is explicit and must not be overridden."""
    embedder = _embedder(monkeypatch, tmp_path, ATLAS_EMBEDDING_BACKEND="hash")

    assert embedder.provider != LOCAL_EMBEDDING_PROVIDER


def test_provider_can_embed_knows_who_cannot(monkeypatch, tmp_path):
    embedder = _embedder(monkeypatch, tmp_path)
    settings = embedder.settings

    assert provider_can_embed(settings, LOCAL_EMBEDDING_PROVIDER) is True
    assert provider_can_embed(settings, "ollama") is True
    assert provider_can_embed(settings, "anthropic") is False
    assert provider_can_embed(settings, "openrouter") is False
    assert provider_can_embed(settings, "") is False


@requires_fastembed
@pytest.mark.asyncio
async def test_local_vectors_are_semantically_real(monkeypatch, tmp_path):
    """Guards against a backend that returns well-shaped nonsense.

    The hash backend produces vectors of exactly the right shape that mean
    nothing, and that shipped once. Shape alone therefore proves nothing: the
    check is that related sentences land closer together than unrelated ones.
    """
    embedder = _embedder(monkeypatch, tmp_path)

    vectors = await embedder.generate_embeddings([
        "Newton's second law relates force, mass and acceleration.",
        "F = ma describes how an applied force produces acceleration.",
        "Mitochondria generate ATP through oxidative phosphorylation.",
    ])

    assert len(vectors) == 3
    assert all(len(v) == LOCAL_EMBEDDING_DIMENSION for v in vectors)

    def cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        return dot / (na * nb)

    related = cosine(vectors[0], vectors[1])
    unrelated = cosine(vectors[0], vectors[2])
    assert related > unrelated, f"related={related:.3f} unrelated={unrelated:.3f}"


@requires_fastembed
@pytest.mark.asyncio
async def test_local_embeddings_are_stable(monkeypatch, tmp_path):
    """The same text must embed identically, or the cache would be wrong."""
    embedder = _embedder(monkeypatch, tmp_path)
    text = "Gradient descent minimises a loss function iteratively."

    first = await embedder.generate_embeddings([text])
    second = await embedder.generate_embeddings([text])

    assert first[0] == pytest.approx(second[0], abs=1e-6)
