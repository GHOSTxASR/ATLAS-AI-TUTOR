"""A multi-source retrieval must embed the query exactly once.

`query_all` fans out to five collections. Each branch used to call
`generate_embeddings([query])` itself, so a single chat turn spent five
identical calls of the provider's embeddings quota on the same string.
"""

from __future__ import annotations

import pytest

from app.pipelines.embedder import DocumentEmbedder
from app.rag.vector_store import VectorStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "reuse-data"))
    monkeypatch.setenv("ATLAS_EMBEDDING_BACKEND", "hash")

    from app.config import get_settings

    get_settings.cache_clear()
    return VectorStore(settings=get_settings())


@pytest.fixture
def embed_calls(monkeypatch):
    calls: list[list[str]] = []
    original = DocumentEmbedder._embed_uncached

    async def _counted(self, texts):
        calls.append(list(texts))
        return await original(self, texts)

    monkeypatch.setattr(DocumentEmbedder, "_embed_uncached", _counted)
    return calls


async def test_query_all_embeds_the_query_once(store, embed_calls):
    await store.query_all(profile_id="p1", query="What is entropy?")

    assert len(embed_calls) == 1, (
        f"expected a single embedding call, got {len(embed_calls)}: {embed_calls}"
    )
    assert embed_calls[0] == ["What is entropy?"]


async def test_every_source_receives_the_same_vector(store, embed_calls):
    """All five branches must search with one consistent query vector."""
    seen: list[list[float]] = []
    original = VectorStore._query_vectors

    async def _record(self, query, query_vector):
        vectors = await original(self, query, query_vector)
        seen.append(vectors[0])
        return vectors

    VectorStore._query_vectors = _record
    try:
        await store.query_all(profile_id="p1", query="thermodynamics")
    finally:
        VectorStore._query_vectors = original

    assert len(seen) == 5, "all five collections should have been queried"
    assert all(vector == seen[0] for vector in seen)
    assert len(embed_calls) == 1


async def test_single_source_query_still_embeds_normally(store, embed_calls):
    await store.query_documents(profile_id="p1", query="entropy")
    assert len(embed_calls) == 1
