from __future__ import annotations

import pytest
from app.rag.vector_store import VectorStore


@pytest.mark.asyncio
async def test_vector_store_indexing_and_query_documents(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    vector_store = VectorStore()
    profile_id = "test-prof-1"
    doc_id = "doc-alpha"

    chunks = [
        {"chunk_index": 0, "text": "Binary search trees maintain sorted order for efficient lookup.", "page_number": 1},
        {"chunk_index": 1, "text": "Hash tables provide average O(1) time complexity for key-value retrieval.", "page_number": 2},
    ]

    indexed_count = await vector_store.index_document_chunks(
        profile_id=profile_id,
        doc_id=doc_id,
        chunks=chunks,
        filename="data_structures.pdf",
        file_type="pdf",
    )
    assert indexed_count == 2

    # Query with semantic term matching BST
    results = await vector_store.query_documents(
        profile_id=profile_id,
        query="Tell me about binary search tree lookups",
        top_k=2,
    )
    assert len(results) >= 1
    assert results[0].source_type == "document"
    assert results[0].source_id == doc_id
    assert results[0].metadata["source_filename"] == "data_structures.pdf"
    assert results[0].metadata["page_number"] == 1


@pytest.mark.asyncio
async def test_vector_store_metadata_filtering(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    vector_store = VectorStore()
    profile_id = "test-prof-filter"

    # Index doc 1 (PDF)
    await vector_store.index_document_chunks(
        profile_id=profile_id,
        doc_id="doc-1",
        chunks=[{"chunk_index": 0, "text": "Thermodynamics first law states conservation of energy.", "page_number": 10}],
        filename="physics.pdf",
        file_type="pdf",
    )

    # Index doc 2 (TXT)
    await vector_store.index_document_chunks(
        profile_id=profile_id,
        doc_id="doc-2",
        chunks=[{"chunk_index": 0, "text": "Thermodynamics second law states entropy of isolated system increases.", "page_number": 1}],
        filename="notes.txt",
        file_type="txt",
    )

    # 1. Filter by doc_id
    doc1_results = await vector_store.query_documents(
        profile_id=profile_id,
        query="energy entropy",
        top_k=5,
        doc_ids=["doc-1"],
    )
    assert len(doc1_results) == 1
    assert doc1_results[0].source_id == "doc-1"

    # 2. Filter by file_type
    txt_results = await vector_store.query_documents(
        profile_id=profile_id,
        query="thermodynamics",
        top_k=5,
        file_type="txt",
    )
    assert len(txt_results) == 1
    assert txt_results[0].source_id == "doc-2"


@pytest.mark.asyncio
async def test_vector_store_memory_notes_and_multi_source(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    vector_store = VectorStore()
    profile_id = "test-prof-multi"

    # Index memory
    await vector_store.index_memory(
        profile_id=profile_id,
        memory_id="mem-1",
        text="Student struggles with dynamic programming recurrence relations.",
        category="weakness",
        subject="Algorithms",
    )

    # Index note
    await vector_store.index_note(
        profile_id=profile_id,
        note_id="note-1",
        title="DP Patterns",
        text="Top-down memoization vs bottom-up tabulation strategies for dynamic programming.",
    )

    # Index graph node
    await vector_store.index_graph_node(
        node_id="concept-1",
        label="Dynamic Programming",
        description="Optimization method using overlapping subproblems and optimal substructure.",
        profile_id=profile_id,
    )

    # Multi-source search
    all_results = await vector_store.query_all(
        profile_id=profile_id,
        query="dynamic programming memoization weakness",
        top_k=10,
    )

    assert len(all_results) >= 3
    source_types = {r.source_type for r in all_results}
    assert "memory" in source_types
    assert "note" in source_types
    assert "graph_node" in source_types


@pytest.mark.asyncio
async def test_profile_isolation_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    vector_store = VectorStore()
    prof_a = "profile-a"
    prof_b = "profile-b"

    await vector_store.index_memory(prof_a, "mem-a", "Secret information for Profile A")
    await vector_store.index_memory(prof_b, "mem-b", "Secret information for Profile B")

    # Profile A should not see Profile B's memories
    res_a = await vector_store.query_memory(prof_a, "Secret information", top_k=5)
    assert len(res_a) == 1
    assert res_a[0].profile_id == prof_a

    # Clean up Profile A
    await vector_store.delete_all_profile_data(prof_a)
    after_clean = await vector_store.query_memory(prof_a, "Secret information", top_k=5)
    assert len(after_clean) == 0

    # Profile B still intact
    res_b = await vector_store.query_memory(prof_b, "Secret information", top_k=5)
    assert len(res_b) == 1
