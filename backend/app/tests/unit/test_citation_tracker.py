from __future__ import annotations

from app.rag.citation_tracker import Citation, CitationTracker
from app.rag.vector_store import VectorSearchResult


def test_citation_tracker_create_citations():
    chunks = [
        VectorSearchResult(
            id="doc:1:chunk:0",
            source_type="document",
            source_id="doc-1",
            profile_id="p1",
            text="First sentence excerpt.",
            score=0.9,
            metadata={"source_filename": "algorithms.pdf", "page_number": 3, "char_offset_start": 100},
        ),
        VectorSearchResult(
            id="mem:2",
            source_type="memory",
            source_id="mem-2",
            profile_id="p1",
            text="User struggles with recursion.",
            score=0.8,
            metadata={"category": "weakness"},
        ),
    ]

    citations = CitationTracker.create_citations(chunks)
    assert len(citations) == 2
    assert citations[0].index == 1
    assert citations[0].filename == "algorithms.pdf"
    assert citations[0].page_number == 3
    assert citations[1].index == 2
    assert citations[1].source_type == "memory"


def test_citation_source_label_formatting():
    c1 = Citation(
        index=1,
        source_type="document",
        source_id="doc-123",
        filename="notes.pdf",
        page_number=4,
        char_offset_start=0,
        char_offset_end=10,
        snippet="text",
        score=0.9,
    )
    label = CitationTracker.format_source_label(c1)
    assert label == "[Source 1: notes.pdf, Page 4] (ID: doc-123)"


def test_extract_cited_indices():
    text = "According to [1], photosynthesis requires light. Furthermore, [2] and [1] confirm carbon fixation."
    indices = CitationTracker.extract_cited_indices(text)
    assert indices == [1, 2]
