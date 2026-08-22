from __future__ import annotations

from app.rag.reranker import Reranker
from app.rag.vector_store import VectorSearchResult


def test_reranker_relevance_scoring():
    reranker = Reranker(lambda_param=0.7)
    candidate = VectorSearchResult(
        id="c-1",
        source_type="document",
        source_id="doc-1",
        profile_id="prof-1",
        text="Quantum mechanics is a fundamental theory in physics.",
        score=0.8,
    )
    score = reranker.score_relevance("quantum physics", candidate)
    assert 0.0 <= score <= 1.0
    assert score > 0.5


def test_reranker_deduplication():
    reranker = Reranker(lambda_param=0.7)
    candidates = [
        VectorSearchResult(id="c-1", source_type="document", source_id="d1", profile_id="p", text="Exact duplicate text block.", score=0.9),
        VectorSearchResult(id="c-2", source_type="document", source_id="d2", profile_id="p", text="Exact duplicate text block.", score=0.85),
        VectorSearchResult(id="c-3", source_type="document", source_id="d3", profile_id="p", text="Unique different text block.", score=0.7),
    ]

    selected = reranker.rerank_and_diversify("query", candidates, top_k=5)
    assert len(selected) == 2
    assert {s.id for s in selected} == {"c-1", "c-3"}


def test_mmr_diversification():
    reranker = Reranker(lambda_param=0.5)
    candidates = [
        VectorSearchResult(id="c-1", source_type="document", source_id="d1", profile_id="p", text="Machine learning with neural networks and deep learning models.", score=0.95),
        VectorSearchResult(id="c-2", source_type="document", source_id="d2", profile_id="p", text="Machine learning neural networks deep learning models training.", score=0.93),
        VectorSearchResult(id="c-3", source_type="document", source_id="d3", profile_id="p", text="Support vector machines and decision trees for classification.", score=0.80),
    ]

    selected = reranker.rerank_and_diversify("machine learning", candidates, top_k=2)
    assert len(selected) == 2
    assert selected[0].id == "c-1"
    # Due to MMR penalizing similarity with c-1, c-3 (diverse) is preferred over c-2 (redundant)
    assert selected[1].id == "c-3"
