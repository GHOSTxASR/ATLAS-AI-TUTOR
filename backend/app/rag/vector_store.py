from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from app.config import Settings, get_settings
from app.pipelines.embedder import DocumentEmbedder, embedding_namespace, get_chroma_client

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Normalized vector search result across any collection."""

    id: str
    source_type: str  # "document", "memory", "note", "chat_summary", "graph_node"
    source_id: str
    profile_id: str
    text: str
    score: float  # Normalized similarity score (1.0 = exact match)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "profile_id": self.profile_id,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata,
        }


class VectorStore:
    """Local ChromaDB vector database manager supporting profile isolation, indexing, and filtering."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.embedder = DocumentEmbedder(settings=self.settings)
        self.chroma_dir = self.settings.paths.chroma_dir

    def _client(self):
        return get_chroma_client(self.chroma_dir)

    # ── Collection Names ──────────────────────────────────────────────

    @property
    def _ns(self) -> str:
        """Namespace suffix identifying the embedding model in use."""
        return embedding_namespace(self.embedder.embedding_model)

    def doc_col_name(self, profile_id: str) -> str:
        return f"{profile_id}_documents_{self._ns}"

    def memory_col_name(self, profile_id: str) -> str:
        return f"{profile_id}_memory_{self._ns}"

    def notes_col_name(self, profile_id: str) -> str:
        return f"{profile_id}_notes_{self._ns}"

    def chat_col_name(self, profile_id: str) -> str:
        return f"{profile_id}_chat_summaries_{self._ns}"

    def graph_col_name(self) -> str:
        return f"global_graph_nodes_{self._ns}"

    def get_collection(self, name: str):
        client = self._client()
        if client is None:
            raise RuntimeError("ChromaDB is not installed or unavailable.")
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Indexing Methods ──────────────────────────────────────────────

    async def index_document_chunks(
        self,
        profile_id: str,
        doc_id: str,
        chunks: Sequence[dict[str, Any]],
        filename: str,
        file_type: str,
        is_syllabus: bool = False,
        roadmap_node_id: str | None = None,
    ) -> int:
        """Index document chunks into {profile_id}_documents collection."""
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        vectors = await self.embedder.generate_embeddings(texts)

        ids: list[str] = []
        metas: list[dict[str, Any]] = []
        docs: list[str] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for chunk, vec in zip(chunks, vectors):
            c_idx = chunk["chunk_index"]
            v_id = f"doc:{doc_id}:chunk:{c_idx}:model:{self.embedder.embedding_model}"
            meta: dict[str, Any] = {
                "profile_id": str(profile_id),
                "doc_id": str(doc_id),
                "chunk_id": str(chunk.get("id", f"{doc_id}_{c_idx}")),
                "chunk_index": int(c_idx),
                "source_filename": str(filename),
                "page_number": int(chunk.get("page_number", -1) if chunk.get("page_number") is not None else -1),
                "char_offset_start": int(chunk.get("char_offset_start", 0) or 0),
                "char_offset_end": int(chunk.get("char_offset_end", 0) or 0),
                "file_type": str(file_type),
                "is_syllabus": bool(is_syllabus),
                "roadmap_node_id": str(roadmap_node_id or ""),
                "embedding_model": str(self.embedder.embedding_model),
                "embedding_dim": int(len(vec)),
                "created_at": now_iso,
            }
            if chunk.get("section_title"):
                meta["section_title"] = str(chunk["section_title"])

            ids.append(v_id)
            metas.append(meta)
            docs.append(chunk["text"])

        col = self.get_collection(self.doc_col_name(profile_id))
        await asyncio.to_thread(col.upsert, ids=ids, embeddings=vectors, metadatas=metas, documents=docs)
        return len(ids)

    async def index_memory(
        self,
        profile_id: str,
        memory_id: str,
        text: str,
        category: str = "fact",
        subject: str = "",
        confidence: float = 1.0,
        source: str = "chat",
        source_id: str | None = None,
        is_active: bool = True,
    ) -> str:
        """Index a memory record into {profile_id}_memory."""
        vectors = await self.embedder.generate_embeddings([text])
        v_id = f"memory:{memory_id}:model:{self.embedder.embedding_model}"
        meta: dict[str, Any] = {
            "profile_id": str(profile_id),
            "memory_id": str(memory_id),
            "category": str(category),
            "subject": str(subject),
            "confidence": float(confidence),
            "source": str(source),
            "source_id": str(source_id or ""),
            "is_active": bool(is_active),
            "embedding_model": str(self.embedder.embedding_model),
            "embedding_dim": int(len(vectors[0])),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        col = self.get_collection(self.memory_col_name(profile_id))
        await asyncio.to_thread(
            col.upsert,
            ids=[v_id],
            embeddings=vectors,
            metadatas=[meta],
            documents=[text],
        )
        return v_id

    async def index_note(
        self,
        profile_id: str,
        note_id: str,
        title: str,
        text: str,
        chunk_index: int = 0,
        tags: str = "",
        roadmap_node_id: str | None = None,
    ) -> str:
        """Index a user note chunk into {profile_id}_notes."""
        vectors = await self.embedder.generate_embeddings([text])
        v_id = f"note:{note_id}:chunk:{chunk_index}:model:{self.embedder.embedding_model}"
        meta: dict[str, Any] = {
            "profile_id": str(profile_id),
            "note_id": str(note_id),
            "chunk_index": int(chunk_index),
            "title": str(title),
            "tags": str(tags),
            "roadmap_node_id": str(roadmap_node_id or ""),
            "embedding_model": str(self.embedder.embedding_model),
            "embedding_dim": int(len(vectors[0])),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        col = self.get_collection(self.notes_col_name(profile_id))
        await asyncio.to_thread(
            col.upsert,
            ids=[v_id],
            embeddings=vectors,
            metadatas=[meta],
            documents=[text],
        )
        return v_id

    async def index_chat_summary(
        self,
        profile_id: str,
        summary_id: str,
        session_id: str,
        text: str,
        roadmap_node_id: str | None = None,
    ) -> str:
        """Index a chat summary into {profile_id}_chat_summaries."""
        vectors = await self.embedder.generate_embeddings([text])
        v_id = f"chat-summary:{summary_id}:model:{self.embedder.embedding_model}"
        meta: dict[str, Any] = {
            "profile_id": str(profile_id),
            "session_id": str(session_id),
            "summary_id": str(summary_id),
            "roadmap_node_id": str(roadmap_node_id or ""),
            "embedding_model": str(self.embedder.embedding_model),
            "embedding_dim": int(len(vectors[0])),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        col = self.get_collection(self.chat_col_name(profile_id))
        await asyncio.to_thread(
            col.upsert,
            ids=[v_id],
            embeddings=vectors,
            metadatas=[meta],
            documents=[text],
        )
        return v_id

    async def index_graph_node(
        self,
        node_id: str,
        label: str,
        description: str,
        node_type: str = "concept",
        profile_id: str | None = None,
    ) -> str:
        """Index a knowledge graph node into global_graph_nodes."""
        text = f"{label}: {description}" if description else label
        vectors = await self.embedder.generate_embeddings([text])
        v_id = f"graph-node:{node_id}:model:{self.embedder.embedding_model}"
        meta: dict[str, Any] = {
            "node_id": str(node_id),
            "label": str(label),
            "type": str(node_type),
            "profile_id": str(profile_id or ""),
            "embedding_model": str(self.embedder.embedding_model),
            "embedding_dim": int(len(vectors[0])),
        }

        col = self.get_collection(self.graph_col_name())
        await asyncio.to_thread(
            col.upsert,
            ids=[v_id],
            embeddings=vectors,
            metadatas=[meta],
            documents=[text],
        )
        return v_id

    # ── Retrieval & Filtering Methods ─────────────────────────────────

    def _normalize_chroma_results(
        self,
        raw: dict[str, Any],
        source_type: str,
        source_id_key: str,
        default_profile_id: str = "",
    ) -> list[VectorSearchResult]:
        """Convert raw ChromaDB query response into normalized VectorSearchResult objects."""
        results: list[VectorSearchResult] = []
        if not raw or not raw.get("ids") or not raw["ids"][0]:
            return results

        ids = raw["ids"][0]
        docs = raw["documents"][0] if raw.get("documents") else [""] * len(ids)
        metas = raw["metadatas"][0] if raw.get("metadatas") else [{}] * len(ids)
        distances = raw["distances"][0] if raw.get("distances") else [0.0] * len(ids)

        for v_id, text, meta, dist in zip(ids, docs, metas, distances):
            meta = meta or {}
            # Cosine distance in Chroma: distance = 1 - cosine_similarity. Convert to score in [0, 1]
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            source_id = str(meta.get(source_id_key, v_id))
            p_id = str(meta.get("profile_id", default_profile_id))

            results.append(
                VectorSearchResult(
                    id=v_id,
                    source_type=source_type,
                    source_id=source_id,
                    profile_id=p_id,
                    text=text,
                    score=score,
                    metadata=meta,
                )
            )

        return results

    async def _query_vectors(
        self, query: str, query_vector: list[float] | None
    ) -> list[list[float]]:
        """Embed `query`, or reuse a vector the caller already computed."""
        if query_vector is not None:
            return [query_vector]
        return await self.embedder.generate_embeddings([query])

    async def query_documents(
        self,
        profile_id: str,
        query: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
        doc_ids: list[str] | None = None,
        file_type: str | None = None,
        is_syllabus: bool | None = None,
        roadmap_node_id: str | None = None,
        query_vector: list[float] | None = None,
    ) -> list[VectorSearchResult]:
        """Query document chunks with optional metadata filtering."""
        query_vectors = await self._query_vectors(query, query_vector)

        # Build compound filter
        conditions: list[dict[str, Any]] = [{"profile_id": {"$eq": profile_id}}]
        if doc_ids:
            if len(doc_ids) == 1:
                conditions.append({"doc_id": {"$eq": doc_ids[0]}})
            else:
                conditions.append({"doc_id": {"$in": doc_ids}})
        if file_type:
            conditions.append({"file_type": {"$eq": file_type}})
        if is_syllabus is not None:
            conditions.append({"is_syllabus": {"$eq": is_syllabus}})
        if roadmap_node_id:
            conditions.append({"roadmap_node_id": {"$eq": roadmap_node_id}})
        if where:
            conditions.append(where)

        combined_where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        col = self.get_collection(self.doc_col_name(profile_id))
        raw = await asyncio.to_thread(
            col.query,
            query_embeddings=query_vectors,
            n_results=top_k,
            where=combined_where,
        )
        return self._normalize_chroma_results(raw, "document", "doc_id", profile_id)

    async def query_memory(
        self,
        profile_id: str,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        is_active: bool = True,
        query_vector: list[float] | None = None,
    ) -> list[VectorSearchResult]:
        """Query memory records with category and active filters."""
        query_vectors = await self._query_vectors(query, query_vector)
        conditions: list[dict[str, Any]] = [
            {"profile_id": {"$eq": profile_id}},
            {"is_active": {"$eq": is_active}},
        ]
        if category:
            conditions.append({"category": {"$eq": category}})

        combined_where = {"$and": conditions} if len(conditions) > 1 else conditions[0]
        col = self.get_collection(self.memory_col_name(profile_id))
        raw = await asyncio.to_thread(
            col.query,
            query_embeddings=query_vectors,
            n_results=top_k,
            where=combined_where,
        )
        return self._normalize_chroma_results(raw, "memory", "memory_id", profile_id)

    async def query_notes(
        self,
        profile_id: str,
        query: str,
        top_k: int = 5,
        roadmap_node_id: str | None = None,
        query_vector: list[float] | None = None,
    ) -> list[VectorSearchResult]:
        """Query user notes."""
        query_vectors = await self._query_vectors(query, query_vector)
        conditions: list[dict[str, Any]] = [{"profile_id": {"$eq": profile_id}}]
        if roadmap_node_id:
            conditions.append({"roadmap_node_id": {"$eq": roadmap_node_id}})

        combined_where = {"$and": conditions} if len(conditions) > 1 else conditions[0]
        col = self.get_collection(self.notes_col_name(profile_id))
        raw = await asyncio.to_thread(
            col.query,
            query_embeddings=query_vectors,
            n_results=top_k,
            where=combined_where,
        )
        return self._normalize_chroma_results(raw, "note", "note_id", profile_id)

    async def query_chat_summaries(
        self,
        profile_id: str,
        query: str,
        top_k: int = 3,
        query_vector: list[float] | None = None,
    ) -> list[VectorSearchResult]:
        """Query past conversation summaries."""
        query_vectors = await self._query_vectors(query, query_vector)
        col = self.get_collection(self.chat_col_name(profile_id))
        raw = await asyncio.to_thread(
            col.query,
            query_embeddings=query_vectors,
            n_results=top_k,
            where={"profile_id": {"$eq": profile_id}},
        )
        return self._normalize_chroma_results(raw, "chat_summary", "summary_id", profile_id)

    async def query_graph_nodes(
        self,
        query: str,
        top_k: int = 5,
        profile_id: str | None = None,
        node_type: str | None = None,
        query_vector: list[float] | None = None,
    ) -> list[VectorSearchResult]:
        """Query global or profile-associated graph concepts."""
        query_vectors = await self._query_vectors(query, query_vector)
        conditions: list[dict[str, Any]] = []
        if profile_id:
            conditions.append({"profile_id": {"$eq": profile_id}})
        if node_type:
            conditions.append({"type": {"$eq": node_type}})

        combined_where = None
        if len(conditions) == 1:
            combined_where = conditions[0]
        elif len(conditions) > 1:
            combined_where = {"$and": conditions}

        col = self.get_collection(self.graph_col_name())
        kwargs: dict[str, Any] = {
            "query_embeddings": query_vectors,
            "n_results": top_k,
        }
        if combined_where:
            kwargs["where"] = combined_where

        raw = await asyncio.to_thread(col.query, **kwargs)
        return self._normalize_chroma_results(raw, "graph_node", "node_id", profile_id or "")

    async def query_all(
        self,
        profile_id: str,
        query: str,
        sources: list[str] | None = None,
        top_k: int = 10,
        doc_ids: list[str] | None = None,
        file_type: str | None = None,
        category: str | None = None,
        roadmap_node_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Query multiple collections in parallel and aggregate results sorted by score."""
        active_sources = set(sources) if sources else {"document", "memory", "note", "chat_summary", "graph_node"}
        if not active_sources:
            return []

        # Embed the query once and share the vector. Each branch used to embed
        # it independently, so a single chat turn made five identical calls to
        # the provider's embeddings API.
        query_vector = (await self.embedder.generate_embeddings([query]))[0]

        tasks = []
        if "document" in active_sources:
            tasks.append(
                self.query_documents(
                    profile_id=profile_id,
                    query=query,
                    top_k=top_k,
                    doc_ids=doc_ids,
                    file_type=file_type,
                    roadmap_node_id=roadmap_node_id,
                    query_vector=query_vector,
                )
            )
        if "memory" in active_sources:
            tasks.append(
                self.query_memory(
                    profile_id=profile_id,
                    query=query,
                    top_k=min(top_k, 5),
                    category=category,
                    query_vector=query_vector,
                )
            )
        if "note" in active_sources:
            tasks.append(
                self.query_notes(
                    profile_id=profile_id,
                    query=query,
                    top_k=min(top_k, 5),
                    roadmap_node_id=roadmap_node_id,
                    query_vector=query_vector,
                )
            )
        if "chat_summary" in active_sources:
            tasks.append(
                self.query_chat_summaries(
                    profile_id=profile_id,
                    query=query,
                    top_k=min(top_k, 3),
                    query_vector=query_vector,
                )
            )
        if "graph_node" in active_sources:
            tasks.append(
                self.query_graph_nodes(
                    query=query,
                    top_k=min(top_k, 5),
                    profile_id=profile_id,
                    query_vector=query_vector,
                )
            )

        if not tasks:
            return []

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        aggregated: list[VectorSearchResult] = []

        for res in results_lists:
            if isinstance(res, list):
                aggregated.extend(res)
            elif isinstance(res, Exception):
                logger.warning(f"Error in multi-collection vector search branch: {res}")

        # Sort descending by similarity score
        aggregated.sort(key=lambda x: x.score, reverse=True)
        return aggregated[:top_k]

    # ── Deletion & Lifecycle Methods ──────────────────────────────────

    async def delete_by_doc_id(self, profile_id: str, doc_id: str) -> None:
        """Delete document vectors from {profile_id}_documents."""
        try:
            col = self.get_collection(self.doc_col_name(profile_id))
            await asyncio.to_thread(col.delete, where={"doc_id": {"$eq": str(doc_id)}})
        except Exception as e:
            logger.warning(f"Error deleting doc vectors {doc_id}: {e}")

    async def delete_by_memory_id(self, profile_id: str, memory_id: str) -> None:
        """Delete memory vector from {profile_id}_memory."""
        try:
            col = self.get_collection(self.memory_col_name(profile_id))
            await asyncio.to_thread(col.delete, where={"memory_id": {"$eq": str(memory_id)}})
        except Exception as e:
            logger.warning(f"Error deleting memory vector {memory_id}: {e}")

    async def delete_by_note_id(self, profile_id: str, note_id: str) -> None:
        """Delete note vectors from {profile_id}_notes."""
        try:
            col = self.get_collection(self.notes_col_name(profile_id))
            await asyncio.to_thread(col.delete, where={"note_id": {"$eq": str(note_id)}})
        except Exception as e:
            logger.warning(f"Error deleting note vectors {note_id}: {e}")

    async def delete_all_profile_data(self, profile_id: str) -> None:
        """Drop all vector collections belonging to a profile."""
        client = self._client()
        if client is None:
            return

        # Collections are namespaced per embedding model, so a profile can own
        # several. Match by prefix to catch every one, including collections
        # left behind by a previous embedding model.
        try:
            existing = await asyncio.to_thread(client.list_collections)
            names = [getattr(c, "name", c) for c in existing]
        except Exception:
            logger.warning("Could not enumerate Chroma collections for profile %s", profile_id)
            names = []

        for name in names:
            if str(name).startswith(f"{profile_id}_"):
                try:
                    await asyncio.to_thread(client.delete_collection, name=str(name))
                except Exception:
                    logger.debug("Could not delete collection %s", name, exc_info=True)

    async def count_vectors(self, collection_name: str) -> int:
        """Count items in a collection."""
        try:
            col = self.get_collection(collection_name)
            return await asyncio.to_thread(col.count)
        except Exception:
            return 0
