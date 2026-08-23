from __future__ import annotations

from app.rag.context_assembler import ContextAssembler
from app.rag.vector_store import VectorSearchResult


def test_context_assembler_empty_chunks():
    assembler = ContextAssembler()
    assembled = assembler.assemble([])
    assert assembled.context_block == ""
    assert len(assembled.citations) == 0
    assert "Atlas" in assembled.system_prompt


def test_context_assembler_with_chunks_and_topic():
    assembler = ContextAssembler(max_context_tokens=1000)
    chunks = [
        VectorSearchResult(
            id="doc:1:chunk:0",
            source_type="document",
            source_id="doc-1",
            profile_id="p1",
            text="First law of motion: inertia.",
            score=0.9,
            metadata={"source_filename": "physics.pdf", "page_number": 1},
        ),
        VectorSearchResult(
            id="doc:1:chunk:1",
            source_type="document",
            source_id="doc-1",
            profile_id="p1",
            text="Second law of motion: F = ma.",
            score=0.85,
            metadata={"source_filename": "physics.pdf", "page_number": 2},
        ),
    ]

    assembled = assembler.assemble(chunks, topic_context="Classical Mechanics")
    assert "<CONTEXT>" in assembled.system_prompt
    assert "[Source 1: physics.pdf, Page 1]" in assembled.system_prompt
    assert "First law of motion: inertia." in assembled.system_prompt
    assert "Current Study Topic: Classical Mechanics" in assembled.system_prompt
    assert len(assembled.citations) == 2
    assert assembled.total_tokens > 0
