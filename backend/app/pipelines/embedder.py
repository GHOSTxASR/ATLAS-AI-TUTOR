from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx

from app.config import Settings, get_settings
from app.db.models import ChunkEmbeddingQueue, Document
from app.db.repositories.embedding_repo import EmbeddingRepository
from app.models.provider_factory import resolve_api_key
from app.models.model_catalog import (
    DEFAULT_EMBEDDING_MODELS,
    GEMINI_EMBEDDING_BASE_URL,
    GEMINI_EMBEDDING_DIMENSION,
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_PROVIDER,
    OPENAI_COMPATIBLE_EMBEDDING_URLS,
    PROVIDERS_WITHOUT_EMBEDDINGS,
)
from app.models.resilience import retry_async
from app.utils.file_utils import sha256_text

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.api import ClientAPI
    _CHROMADB_AVAILABLE = True
except ImportError:
    _CHROMADB_AVAILABLE = False
    ClientAPI = Any  # type: ignore

try:
    import fastembed  # noqa: F401
    _LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    _LOCAL_EMBEDDINGS_AVAILABLE = False


# Global singleton ChromaDB client to avoid SQLite file locks in embedded mode
_CHROMA_CLIENT: ClientAPI | None = None
_CHROMA_CLIENT_PATH: str | None = None


def embedding_namespace(model: str) -> str:
    """Collection-name-safe slug for an embedding model.

    Vector collections are namespaced by the model that produced them. Mixing
    models in one collection is never valid - dimensions differ, and even at
    equal dimensions the vector spaces are unrelated - so a model change simply
    starts a new collection instead of corrupting or erroring against the old.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", model or "unknown").strip("_").lower()
    return slug or "unknown"


def get_chroma_client(chroma_dir: Path) -> ClientAPI | None:
    """Return a singleton PersistentClient for the given directory."""
    global _CHROMA_CLIENT, _CHROMA_CLIENT_PATH
    if not _CHROMADB_AVAILABLE:
        return None

    path_str = str(chroma_dir.resolve())
    if _CHROMA_CLIENT is None or _CHROMA_CLIENT_PATH != path_str:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        _CHROMA_CLIENT = chromadb.PersistentClient(path=path_str)
        _CHROMA_CLIENT_PATH = path_str
    return _CHROMA_CLIENT


class EmbeddingUnavailableError(RuntimeError):
    """Raised when no real embedding backend can serve the active provider.

    Deliberately fatal: silently substituting meaningless vectors used to make
    document search return random passages while appearing to work.
    """


# Opt-in offline backend for development and tests. Never selected implicitly.
HASH_BACKEND_NAME = "hash"
HASH_BACKEND_MODEL = "hash-dev-1536"


# The ONNX model is a few hundred milliseconds to load and ~130MB to fetch the
# very first time, so it is held for the life of the process rather than
# rebuilt per request.
_LOCAL_MODEL: Any = None
_LOCAL_MODEL_NAME: str | None = None


def get_local_embedding_model(model_name: str) -> Any:
    """Return the process-wide local embedding model, loading it on first use."""
    global _LOCAL_MODEL, _LOCAL_MODEL_NAME
    if _LOCAL_MODEL is None or _LOCAL_MODEL_NAME != model_name:
        from fastembed import TextEmbedding

        logger.info("Loading local embedding model %s (first run downloads it)", model_name)
        _LOCAL_MODEL = TextEmbedding(model_name=model_name)
        _LOCAL_MODEL_NAME = model_name
    return _LOCAL_MODEL


def provider_can_embed(settings: Settings, provider: str) -> bool:
    """Whether `provider` could actually produce embeddings right now.

    Both halves matter: some providers have no embeddings API at all, and the
    ones that do still need a key.
    """
    if not provider or provider in PROVIDERS_WITHOUT_EMBEDDINGS:
        return False
    if provider in (LOCAL_EMBEDDING_PROVIDER, "ollama"):
        return True  # Runs locally; there is no key to check.

    from app.models.provider_factory import OPENAI_COMPATIBLE_PROVIDERS

    env_keys = {
        "gemini": "GEMINI_API_KEY",
        **{pid: info["env_key"] for pid, info in OPENAI_COMPATIBLE_PROVIDERS.items()},
    }
    return bool(resolve_api_key(settings, provider, env_keys.get(provider, "OPENAI_API_KEY")))


def generate_deterministic_embedding(text: str, dim: int = 1536) -> list[float]:
    """Deterministic pseudo-random unit vector derived from text.

    NOT used for indexing or retrieval. These vectors carry no semantic
    meaning, so using them silently produced nonsense search results. Retained
    only as a test fixture for shape/among-vector plumbing.
    """
    # Seed a PRNG with the sha256 hash of the text
    h = hashlib.sha256(text.encode("utf-8")).digest()
    seed = struct.unpack(">Q", h[:8])[0]

    # Simple linear congruential generator
    a = 6364136223846793005
    c = 1442695040888963407
    m = 2**64

    vector: list[float] = []
    state = seed
    for _ in range(dim):
        state = (a * state + c) % m
        # Map to range [-1.0, 1.0]
        val = ((state / m) * 2.0) - 1.0
        vector.append(val)

    # Normalize to unit length
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class DocumentEmbedder:
    """Generates batch embeddings and stores vectors in local persistent ChromaDB."""

    DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
    DEFAULT_DIMENSION = 1536
    _hash_backend_warned = False

    def __init__(
        self,
        settings: Settings | None = None,
        repo: EmbeddingRepository | None = None,
    ):
        self.settings = settings or get_settings()
        self.repo = repo
        self.chroma_dir = self.settings.paths.chroma_dir
        self.use_hash_backend = (
            getattr(self.settings.model, "embedding_backend", "auto") == HASH_BACKEND_NAME
        )
        # Deliberately the embedding provider, not the chat one: everything
        # downstream in this class keys off self.provider, so splitting the
        # two is a matter of resolving it here.
        self.provider_was_inferred = False
        self.provider = self._resolve_provider()
        self.embedding_model = self._resolve_embedding_model()
        if self.use_hash_backend and not DocumentEmbedder._hash_backend_warned:
            DocumentEmbedder._hash_backend_warned = True
            logger.warning(
                "ATLAS_EMBEDDING_BACKEND=%s: using deterministic pseudo-embeddings. "
                "Semantic search results will be meaningless. Do not use this outside "
                "offline development or tests.",
                HASH_BACKEND_NAME,
            )

    def _resolve_provider(self) -> str:
        """Pick who serves embeddings, defaulting to this machine.

        An explicit ``embedding_provider`` is always honoured, including when
        it cannot serve -- a chosen provider that fails should say so rather
        than quietly become something else.

        The fallback covers the case where nothing was chosen: a fresh install
        follows the chat provider, which defaults to OpenAI and has no key, so
        indexing a document used to fail before the app had ever been
        configured. Falling back to local embeddings makes the app work out of
        the box, and it also rescues chat providers with no embeddings API of
        their own (OpenRouter, Groq, Anthropic, DeepSeek).
        """
        configured = self.settings.model.effective_embedding_provider

        if self.use_hash_backend or self.settings.model.embedding_provider:
            return configured
        if provider_can_embed(self.settings, configured):
            return configured
        if not _LOCAL_EMBEDDINGS_AVAILABLE:
            return configured

        self.provider_was_inferred = True
        logger.info(
            "No embeddings backend configured for '%s'; using local embeddings (%s).",
            configured or "unset",
            LOCAL_EMBEDDING_MODEL,
        )
        return LOCAL_EMBEDDING_PROVIDER

    def _resolve_embedding_model(self) -> str:
        """Pick the embedding model for the active provider.

        The global ``embedding_model`` setting defaults to an OpenAI model
        name, which is meaningless to Gemini or Ollama. Treat that default as
        "unset" for non-OpenAI providers and use the provider's own default;
        an explicitly customised value is always honoured.
        """
        if self.use_hash_backend:
            # Distinct name so these vectors land in their own collection and
            # can never be compared against real embeddings.
            return HASH_BACKEND_MODEL

        configured = (self.settings.model.embedding_model or "").strip()
        provider_default = DEFAULT_EMBEDDING_MODELS.get(self.provider, self.DEFAULT_EMBEDDING_MODEL)

        # A provider we inferred rather than one the user picked means the
        # configured model name was chosen for somebody else. Carrying
        # "gemini-embedding-001" over to the local backend just fails.
        if self.provider_was_inferred:
            return provider_default
        if not configured:
            return provider_default

        # A name that is some *other* provider's default is a leftover from
        # before the provider changed, not a deliberate choice. Switching to
        # local embeddings while "gemini-embedding-001" is still configured
        # otherwise crashes on a model the backend has never heard of.
        stale_defaults = {
            name for provider, name in DEFAULT_EMBEDDING_MODELS.items()
            if provider != self.provider
        }
        if configured in stale_defaults:
            return provider_default
        return configured

    def _get_chroma(self) -> ClientAPI | None:
        return get_chroma_client(self.chroma_dir)

    def get_collection_name(self, profile_id: str) -> str:
        return f"{profile_id}_documents_{embedding_namespace(self.embedding_model)}"

    def get_or_create_collection(self, profile_id: str) -> Any:
        client = self._get_chroma()
        if client is None:
            raise RuntimeError("ChromaDB is not installed or available.")
        name = self.get_collection_name(profile_id)
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def format_vector_id(self, doc_id: str, chunk_index: int, model: str) -> str:
        return f"doc:{doc_id}:chunk:{chunk_index}:model:{model}"

    async def _call_openai_embeddings(
        self, texts: list[str], api_key: str, base_url: str = "https://api.openai.com/v1"
    ) -> list[list[float]]:
        """Call an OpenAI-compatible embeddings endpoint with shared retry/backoff."""
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        ) as client:

            async def _request() -> list[list[float]]:
                resp = await client.post(
                    "/embeddings",
                    json={"input": texts, "model": self.embedding_model},
                )
                resp.raise_for_status()
                data = resp.json()
                # Sort by index: the API does not guarantee response order.
                items = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in items]

            return await retry_async(_request, provider=self.provider)

    async def _call_gemini_embeddings(self, texts: list[str], api_key: str) -> list[list[float]]:
        """Embed via Gemini's batchEmbedContents endpoint.

        The key goes in a header so it can never surface in an error message.
        """
        model_path = f"models/{self.embedding_model}"
        url = f"{GEMINI_EMBEDDING_BASE_URL}/{model_path}:batchEmbedContents"
        payload = {
            "requests": [
                {
                    "model": model_path,
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": GEMINI_EMBEDDING_DIMENSION,
                }
                for text in texts
            ]
        }

        async with httpx.AsyncClient(
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        ) as client:

            async def _request() -> list[list[float]]:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return [item["values"] for item in data.get("embeddings", [])]

            return await retry_async(_request, provider="gemini")

    async def _call_local_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Embed on this machine with a small ONNX model.

        fastembed is synchronous and CPU-bound, so it runs off the event loop.
        """

        def _run() -> list[list[float]]:
            model = get_local_embedding_model(self.embedding_model)
            return [vector.tolist() for vector in model.embed(texts)]

        return await asyncio.to_thread(_run)

    async def _call_ollama_embeddings(self, texts: list[str], base_url: str = "http://localhost:11434") -> list[list[float]]:
        """Call the Ollama embedding endpoint once per text."""
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0),
        ) as client:
            for text in texts:

                async def _request(payload_text: str = text) -> list[float]:
                    resp = await client.post(
                        "/api/embeddings",
                        json={"model": self.embedding_model, "prompt": payload_text},
                    )
                    resp.raise_for_status()
                    return resp.json()["embedding"]

                vectors.append(await retry_async(_request, provider="ollama"))
        return vectors

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, checking cache and falling back gracefully."""
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        # Check cache if repository is provided
        for i, text in enumerate(texts):
            if self.repo:
                text_hash = sha256_text(text)
                cached = await self.repo.get_cached_embedding(text_hash, self.embedding_model)
                if cached:
                    results[i] = cached
                    continue
            missing_indices.append(i)
            missing_texts.append(text)

        if missing_texts:
            computed_vectors = await self._embed_uncached(missing_texts)

            # A short reply would silently pair chunk N with another chunk's
            # vector once zipped, corrupting the index without any error.
            if len(computed_vectors) != len(missing_texts):
                raise EmbeddingUnavailableError(
                    f"{self.provider} returned {len(computed_vectors)} embeddings "
                    f"for {len(missing_texts)} inputs; refusing to index misaligned vectors."
                )

            for idx, vec in zip(missing_indices, computed_vectors):
                results[idx] = vec
                if self.repo:
                    text_hash = sha256_text(texts[idx])
                    await self.repo.cache_embedding(text_hash, self.embedding_model, vec)

        if any(v is None for v in results):
            raise EmbeddingUnavailableError("Embedding generation produced an incomplete result set.")
        return [v for v in results if v is not None]

    async def _embed_uncached(self, texts: list[str]) -> list[list[float]]:
        """Generate real embeddings, or raise.

        There is deliberately no fallback to synthetic vectors: doing so made
        retrieval return arbitrary passages and poisoned both the cache and
        ChromaDB with vectors that carry no meaning.
        """
        from app.models.provider_factory import OPENAI_COMPATIBLE_PROVIDERS

        if self.use_hash_backend:
            return [generate_deterministic_embedding(t, self.DEFAULT_DIMENSION) for t in texts]

        if self.provider == LOCAL_EMBEDDING_PROVIDER:
            if not _LOCAL_EMBEDDINGS_AVAILABLE:
                raise EmbeddingUnavailableError(
                    "Local embeddings need the 'fastembed' package, which is not "
                    "installed. Run: pip install -r requirements.txt"
                )
            return await self._call_local_embeddings(texts)

        if self.provider in PROVIDERS_WITHOUT_EMBEDDINGS:
            supported = ", ".join(sorted(DEFAULT_EMBEDDING_MODELS))
            raise EmbeddingUnavailableError(
                f"'{self.provider}' has no embeddings API, so documents cannot be indexed "
                f"while it is the active provider. Switch to one of: {supported}."
            )

        if self.provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return await self._call_ollama_embeddings(texts, base_url=base_url)

        provider_env_keys = {
            "gemini": "GEMINI_API_KEY",
            **{pid: info["env_key"] for pid, info in OPENAI_COMPATIBLE_PROVIDERS.items()},
        }
        env_key = provider_env_keys.get(self.provider, "OPENAI_API_KEY")
        api_key = resolve_api_key(self.settings, self.provider, env_key)
        if not api_key:
            raise EmbeddingUnavailableError(
                f"No API key configured for '{self.provider}', so documents cannot be embedded. "
                "Set it on the Settings page."
            )

        if self.provider == "gemini":
            return await self._call_gemini_embeddings(texts, api_key)

        base_url = OPENAI_COMPATIBLE_EMBEDDING_URLS.get(self.provider)
        if not base_url:
            raise EmbeddingUnavailableError(
                f"No embeddings backend is configured for provider '{self.provider}'."
            )
        return await self._call_openai_embeddings(texts, api_key, base_url=base_url)

    async def embed_and_index_chunks(
        self,
        profile_id: str,
        document: Document,
        chunks: Sequence[ChunkEmbeddingQueue],
    ) -> int:
        """Embed a sequence of queue chunks and index them into ChromaDB."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        vectors = await self.generate_embeddings(texts)

        vector_ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        documents: list[str] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for chunk, vector in zip(chunks, vectors):
            v_id = self.format_vector_id(document.id, chunk.chunk_index, self.embedding_model)
            meta: dict[str, Any] = {
                "profile_id": str(profile_id),
                "doc_id": str(document.id),
                "chunk_id": str(chunk.id),
                "chunk_index": int(chunk.chunk_index),
                "source_filename": str(document.filename),
                "page_number": int(chunk.page_number) if chunk.page_number is not None else -1,
                "char_offset_start": int(chunk.char_offset_start) if chunk.char_offset_start is not None else 0,
                "char_offset_end": int(chunk.char_offset_end) if chunk.char_offset_end is not None else 0,
                "file_type": str(document.file_type),
                "is_syllabus": bool(document.is_syllabus),
                "roadmap_node_id": str(document.roadmap_node_id or ""),
                "embedding_model": str(self.embedding_model),
                "embedding_dim": int(len(vector)),
                "created_at": now_iso,
            }
            if chunk.section_title:
                meta["section_title"] = str(chunk.section_title)

            vector_ids.append(v_id)
            metadatas.append(meta)
            documents.append(chunk.text)

        if _CHROMADB_AVAILABLE:
            collection = self.get_or_create_collection(profile_id)
            # Execute ChromaDB upsert in thread pool to avoid blocking async event loop
            await asyncio.to_thread(
                collection.upsert,
                ids=vector_ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents,
            )

        return len(vector_ids)

    async def delete_document_vectors(self, profile_id: str, document_id: str) -> None:
        """Delete all vectors for a document from ChromaDB."""
        if not _CHROMADB_AVAILABLE:
            return
        try:
            collection = self.get_or_create_collection(profile_id)
            await asyncio.to_thread(collection.delete, where={"doc_id": str(document_id)})
        except Exception as e:
            logger.warning(f"Error deleting vectors for document {document_id} from ChromaDB: {e}")

    async def query_similar_chunks(
        self,
        profile_id: str,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform semantic similarity query on profile document collection."""
        if not _CHROMADB_AVAILABLE:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        query_vectors = await self.generate_embeddings([query])
        collection = self.get_or_create_collection(profile_id)

        kwargs: dict[str, Any] = {
            "query_embeddings": query_vectors,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        return await asyncio.to_thread(collection.query, **kwargs)


# Backward compatibility alias
Embedder = DocumentEmbedder
