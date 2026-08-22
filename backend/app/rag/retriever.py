from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.rag.vector_store import VectorSearchResult, VectorStore

logger = logging.getLogger(__name__)


class MultiSourceRetriever:
    """Retrieves relevant context across documents, memories, notes, chat history, and knowledge graph."""

    def __init__(self, settings: Settings | None = None, vector_store: VectorStore | None = None):
        self.settings = settings or get_settings()
        self.vector_store = vector_store or VectorStore(settings=self.settings)

    async def retrieve(
        self,
        profile_id: str,
        query: str,
        top_k: int = 10,
        sources: list[str] | None = None,
        doc_ids: list[str] | None = None,
        file_type: str | None = None,
        category: str | None = None,
        roadmap_node_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Perform semantic search across all or selected sources with metadata filtering."""
        query = query.strip()
        if not query:
            return []

        return await self.vector_store.query_all(
            profile_id=profile_id,
            query=query,
            sources=sources,
            top_k=top_k,
            doc_ids=doc_ids,
            file_type=file_type,
            category=category,
            roadmap_node_id=roadmap_node_id,
        )

    async def retrieve_documents(
        self,
        profile_id: str,
        query: str,
        top_k: int = 10,
        doc_ids: list[str] | None = None,
        file_type: str | None = None,
        is_syllabus: bool | None = None,
        roadmap_node_id: str | None = None,
    ) -> list[VectorSearchResult]:
        """Query document chunks specifically with filters."""
        return await self.vector_store.query_documents(
            profile_id=profile_id,
            query=query,
            top_k=top_k,
            doc_ids=doc_ids,
            file_type=file_type,
            is_syllabus=is_syllabus,
            roadmap_node_id=roadmap_node_id,
        )
