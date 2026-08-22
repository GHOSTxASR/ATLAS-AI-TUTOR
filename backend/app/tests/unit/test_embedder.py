from __future__ import annotations

import math

import pytest

from app.pipelines.embedder import (
    HASH_BACKEND_MODEL,
    DocumentEmbedder,
    EmbeddingUnavailableError,
    embedding_namespace,
    generate_deterministic_embedding,
)


def _embedder(monkeypatch, tmp_path, **env) -> DocumentEmbedder:
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "embedder-data"))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from app.config import get_settings

    get_settings.cache_clear()
    return DocumentEmbedder(settings=get_settings())


def test_deterministic_embedding_properties():
    text1 = "Learning algorithms and neural networks"
    text2 = "Learning algorithms and neural networks"
    text3 = "Completely different topic on organic chemistry"

    vec1 = generate_deterministic_embedding(text1, dim=1536)
    vec2 = generate_deterministic_embedding(text2, dim=1536)
    vec3 = generate_deterministic_embedding(text3, dim=1536)

    assert len(vec1) == 1536
    assert vec1 == vec2
    assert vec1 != vec3

    magnitude = math.sqrt(sum(x * x for x in vec1))
    assert math.isclose(magnitude, 1.0, rel_tol=1e-5)


def test_embedder_vector_id_formatting():
    embedder = DocumentEmbedder()
    v_id = embedder.format_vector_id("doc-123", 4, "text-embedding-3-small")
    assert v_id == "doc:doc-123:chunk:4:model:text-embedding-3-small"


def test_embedding_namespace_is_collection_safe():
    assert embedding_namespace("text-embedding-3-small") == "text_embedding_3_small"
    assert embedding_namespace("BAAI/bge-base-en-v1.5") == "baai_bge_base_en_v1_5"
    assert embedding_namespace("") == "unknown"


def test_collection_name_is_namespaced_by_embedding_model():
    """Vectors from different models must never share a collection."""
    embedder = DocumentEmbedder()
    name = embedder.get_collection_name("prof-abc")
    assert name.startswith("prof-abc_documents_")
    assert embedding_namespace(embedder.embedding_model) in name


# ── Model resolution ──────────────────────────────────────────────────


def test_gemini_provider_gets_a_gemini_embedding_model(monkeypatch, tmp_path):
    """The global default is an OpenAI model name; Gemini cannot use it."""
    embedder = _embedder(
        monkeypatch,
        tmp_path,
        LEARNINGOS_EMBEDDING_BACKEND="auto",
        LEARNINGOS_MODEL_PROVIDER="gemini",
        LEARNINGOS_EMBEDDING_MODEL="text-embedding-3-small",
    )
    assert embedder.embedding_model == "gemini-embedding-001"


def test_explicit_embedding_model_is_honoured(monkeypatch, tmp_path):
    embedder = _embedder(
        monkeypatch,
        tmp_path,
        LEARNINGOS_EMBEDDING_BACKEND="auto",
        LEARNINGOS_MODEL_PROVIDER="gemini",
        LEARNINGOS_EMBEDDING_MODEL="gemini-embedding-2",
    )
    assert embedder.embedding_model == "gemini-embedding-2"


# ── No silent fabrication ─────────────────────────────────────────────


def test_production_default_never_uses_hash_backend(monkeypatch, tmp_path):
    """Regression: fake vectors used to be the implicit fallback."""
    monkeypatch.delenv("LEARNINGOS_EMBEDDING_BACKEND", raising=False)
    embedder = _embedder(monkeypatch, tmp_path, LEARNINGOS_MODEL_PROVIDER="openai")
    assert embedder.use_hash_backend is False
    assert embedder.embedding_model != HASH_BACKEND_MODEL


async def test_provider_without_embeddings_api_raises(monkeypatch, tmp_path):
    """Anthropic/Groq/etc. have no embeddings endpoint - say so, don't fake it."""
    embedder = _embedder(
        monkeypatch,
        tmp_path,
        LEARNINGOS_EMBEDDING_BACKEND="auto",
        LEARNINGOS_MODEL_PROVIDER="anthropic",
    )
    with pytest.raises(EmbeddingUnavailableError) as excinfo:
        await embedder.generate_embeddings(["some chunk of text"])
    assert "no embeddings API" in str(excinfo.value)


async def test_missing_api_key_raises_instead_of_fabricating(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    embedder = _embedder(
        monkeypatch,
        tmp_path,
        LEARNINGOS_EMBEDDING_BACKEND="auto",
        LEARNINGOS_MODEL_PROVIDER="openai",
    )
    monkeypatch.setattr(
        "app.pipelines.embedder.resolve_api_key", lambda *args, **kwargs: ""
    )
    with pytest.raises(EmbeddingUnavailableError) as excinfo:
        await embedder.generate_embeddings(["some chunk of text"])
    assert "No API key configured" in str(excinfo.value)


async def test_short_provider_response_raises_rather_than_misaligning(monkeypatch, tmp_path):
    """A short reply would pair chunk N with another chunk's vector."""
    embedder = _embedder(
        monkeypatch,
        tmp_path,
        LEARNINGOS_EMBEDDING_BACKEND="auto",
        LEARNINGOS_MODEL_PROVIDER="openai",
    )

    async def _short(texts):
        return [[0.1] * 8]  # one vector for three inputs

    monkeypatch.setattr(embedder, "_embed_uncached", _short)

    with pytest.raises(EmbeddingUnavailableError) as excinfo:
        await embedder.generate_embeddings(["a", "b", "c"])
    assert "misaligned" in str(excinfo.value)


async def test_hash_backend_is_usable_when_explicitly_selected(monkeypatch, tmp_path):
    embedder = _embedder(monkeypatch, tmp_path, LEARNINGOS_EMBEDDING_BACKEND="hash")
    vectors = await embedder.generate_embeddings(["First sentence", "Second sentence"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    assert embedder.embedding_model == HASH_BACKEND_MODEL
