from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from app.rag.vector_store import VectorSearchResult


@dataclass
class Citation:
    """A citation mapping an in-text marker e.g. [1] to its source chunk metadata."""

    index: int
    source_type: str
    source_id: str
    filename: str
    page_number: int | None
    char_offset_start: int
    char_offset_end: int
    snippet: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "filename": self.filename,
            "page_number": self.page_number,
            "char_offset_start": self.char_offset_start,
            "char_offset_end": self.char_offset_end,
            "snippet": self.snippet,
            "score": round(self.score, 4),
        }


class CitationTracker:
    """Tracks and formats source citations for RAG context and model responses."""

    @staticmethod
    def create_citations(chunks: Sequence[VectorSearchResult]) -> list[Citation]:
        """Convert a list of retrieved/reranked chunks into numbered citations."""
        citations: list[Citation] = []
        for i, chunk in enumerate(chunks, start=1):
            meta = chunk.metadata or {}
            filename = meta.get("source_filename") or meta.get("title") or chunk.source_id
            page = meta.get("page_number")
            if page == -1:
                page = None

            snippet = chunk.text.strip()
            if len(snippet) > 150:
                snippet = snippet[:147] + "..."

            citations.append(
                Citation(
                    index=i,
                    source_type=chunk.source_type,
                    source_id=chunk.source_id,
                    filename=str(filename),
                    page_number=int(page) if page is not None else None,
                    char_offset_start=int(meta.get("char_offset_start", 0) or 0),
                    char_offset_end=int(meta.get("char_offset_end", 0) or 0),
                    snippet=snippet,
                    score=chunk.score,
                )
            )
        return citations

    @staticmethod
    def format_source_label(citation: Citation) -> str:
        """Create a human-readable header label for a citation item."""
        idx = citation.index
        stype = citation.source_type

        if stype == "document":
            page_str = f", Page {citation.page_number}" if citation.page_number else ""
            return f"[Source {idx}: {citation.filename}{page_str}] (ID: {citation.source_id})"
        elif stype == "memory":
            return f"[Source {idx}: Memory ({citation.filename})] (ID: {citation.source_id})"
        elif stype == "note":
            return f"[Source {idx}: Note: {citation.filename}] (ID: {citation.source_id})"
        elif stype == "graph_node":
            return f"[Source {idx}: Concept: {citation.filename}] (ID: {citation.source_id})"
        else:
            return f"[Source {idx}: {citation.filename}] (ID: {citation.source_id})"

    @staticmethod
    def extract_cited_indices(response_text: str) -> list[int]:
        """Parse all unique [1], [2], etc. citation markers from response text."""
        matches = re.findall(r"\[(\d+)\]", response_text)
        return sorted(list({int(m) for m in matches}))
