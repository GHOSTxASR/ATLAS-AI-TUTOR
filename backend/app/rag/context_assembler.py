from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from app.pipelines.chunker import DocumentChunker
from app.rag.citation_tracker import Citation, CitationTracker
from app.rag.vector_store import VectorSearchResult

logger = logging.getLogger(__name__)


@dataclass
class AssembledContext:
    """Structured context ready for LLM prompt injection and client attribution."""

    context_block: str
    system_prompt: str
    citations: list[Citation]
    total_tokens: int
    chunk_count: int


class ContextAssembler:
    """Assembles retrieved and reranked knowledge chunks into a token-budgeted prompt block."""

    BASE_SYSTEM_PROMPT = (
        "You are LearningOS, an expert AI learning tutor. "
        "Your goal is to help the student learn effectively, clarify concepts, and solve problems. "
        "Be concise, clear, and encouraging. Use step-by-step explanations and examples when helpful."
    )

    RAG_INSTRUCTIONS = (
        "Ground your explanations in the verified <CONTEXT> provided below. "
        "Always cite your sources using bracketed numbers matching the source index, such as [1] or [2]. "
        "If the context does not contain enough information to answer completely, answer to the best of your ability "
        "and mention what is not covered in the provided materials."
    )

    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
        self.chunker = DocumentChunker()

    def assemble(
        self,
        chunks: Sequence[VectorSearchResult],
        topic_context: str | None = None,
        base_prompt: str | None = None,
        learner_profile_context: str | None = None,
    ) -> AssembledContext:
        """Assemble chunks and learner memory into a formatted prompt block within token limits."""
        system_parts = [base_prompt or self.BASE_SYSTEM_PROMPT]
        if learner_profile_context:
            system_parts.append(learner_profile_context)

        if not chunks:
            if topic_context:
                system_parts.append(f"Current Study Topic: {topic_context}")
            full_prompt = "\n\n".join(system_parts)
            return AssembledContext(
                context_block="",
                system_prompt=full_prompt,
                citations=[],
                total_tokens=self.chunker.count_tokens(full_prompt),
                chunk_count=0,
            )

        citations = CitationTracker.create_citations(chunks)
        selected_citations: list[Citation] = []
        formatted_sections: list[str] = []
        accumulated_tokens = 0

        for cit, chunk in zip(citations, chunks):
            label = CitationTracker.format_source_label(cit)
            section = f"{label}\n{chunk.text.strip()}"
            section_tokens = self.chunker.count_tokens(section)

            if formatted_sections and (accumulated_tokens + section_tokens > self.max_context_tokens):
                # Hit token budget limit
                break

            formatted_sections.append(section)
            selected_citations.append(cit)
            accumulated_tokens += section_tokens

        context_body = "\n\n".join(formatted_sections)
        context_block = f"<CONTEXT>\n{context_body}\n</CONTEXT>"

        # Construct full system prompt
        system_parts.append(self.RAG_INSTRUCTIONS)
        if topic_context:
            system_parts.append(f"Current Study Topic: {topic_context}")
        system_parts.append(context_block)

        full_system_prompt = "\n\n".join(system_parts)
        total_tokens = self.chunker.count_tokens(full_system_prompt)

        return AssembledContext(
            context_block=context_block,
            system_prompt=full_system_prompt,
            citations=selected_citations,
            total_tokens=total_tokens,
            chunk_count=len(selected_citations),
        )
