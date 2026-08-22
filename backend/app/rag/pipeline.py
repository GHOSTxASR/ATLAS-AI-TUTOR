from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.rag.context_assembler import AssembledContext, ContextAssembler
from app.rag.reranker import Reranker
from app.rag.retriever import MultiSourceRetriever
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Full RAG Orchestrator: Multi-source retrieval -> Relevance scoring & MMR -> Context assembly."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.vector_store = VectorStore(settings=self.settings)
        self.retriever = MultiSourceRetriever(settings=self.settings, vector_store=self.vector_store)
        self.reranker = Reranker(lambda_param=0.7)
        self.assembler = ContextAssembler(max_context_tokens=4000)

    async def retrieve_and_assemble(
        self,
        profile_id: str,
        query: str,
        sources: list[str] | None = None,
        doc_ids: list[str] | None = None,
        top_k_retrieve: int = 15,
        top_k_final: int = 8,
        topic_context: str | None = None,
        file_type: str | None = None,
        category: str | None = None,
        learner_profile_context: str | None = None,
        roadmap_node_id: str | None = None,
        max_context_tokens: int | None = None,
    ) -> AssembledContext:
        """Run the end-to-end RAG pipeline for a given query.

        ``topic_context`` is a human-readable topic *title* used to frame the
        prompt. ``roadmap_node_id`` is the metadata filter. Passing the former
        as the latter matched no stored vector, so retrieval silently returned
        nothing whenever a roadmap topic was active.
        """
        # 1. Multi-source vector retrieval
        candidates = await self.retriever.retrieve(
            profile_id=profile_id,
            query=query,
            top_k=top_k_retrieve,
            sources=sources,
            doc_ids=doc_ids,
            file_type=file_type,
            category=category,
            roadmap_node_id=roadmap_node_id,
        )

        # Callers that build a larger prompt around this block pass the budget
        # left over for retrieved context.
        assembler = self.assembler
        if max_context_tokens is not None:
            assembler = ContextAssembler(max_context_tokens=max(200, max_context_tokens))

        if not candidates:
            return assembler.assemble(
                [], topic_context=topic_context, learner_profile_context=learner_profile_context
            )

        # 2. Rerank and diversify with MMR
        diversified_chunks = self.reranker.rerank_and_diversify(
            query=query,
            candidates=candidates,
            top_k=top_k_final,
        )

        # 3. Assemble formatted context and citations
        return assembler.assemble(
            chunks=diversified_chunks,
            topic_context=topic_context,
            learner_profile_context=learner_profile_context,
        )
