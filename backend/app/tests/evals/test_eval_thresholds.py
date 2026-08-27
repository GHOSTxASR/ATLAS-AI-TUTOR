"""Thresholds that turn the evals into a regression gate.

The scorecards in `python -m evals.run` are for reading; these are for failing.
Both run without an API key, so CI can enforce them on every push.

Thresholds sit a little below the measured numbers rather than at them. Pinned
exactly, they would fail on harmless variation and get raised reflexively until
they meant nothing. Set here, a real regression trips them and noise does not.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

# Measured at the time of writing, on local embeddings:
#   recall@5 0.977   MRR 0.970   NDCG@5 0.960
MIN_RECALL_AT_5 = 0.90
MIN_MRR = 0.85
MIN_NDCG_AT_5 = 0.85

K = 5


async def test_retrieval_finds_the_right_passages():
    from evals.retrieval import evaluate

    run = await evaluate(k=K)

    assert len(run.queries) >= 20, "the golden set should not shrink silently"
    assert run.recall >= MIN_RECALL_AT_5, (
        f"recall@{K} fell to {run.recall:.3f}; "
        f"missed: {[q.query_id for q in run.misses]}"
    )
    assert run.mrr >= MIN_MRR, f"MRR fell to {run.mrr:.3f}"
    assert run.ndcg >= MIN_NDCG_AT_5, f"NDCG@{K} fell to {run.ndcg:.3f}"


async def test_ambiguous_queries_resolve_by_meaning_not_keywords():
    """'induction' and 'tree' mean different things in different subjects.

    A retriever that degrades to keyword matching -- or an embedding backend
    that quietly becomes the hash one -- scores near zero here while the
    overall number still looks respectable.
    """
    from evals.retrieval import evaluate_by_kind

    by_kind = await evaluate_by_kind(k=K)
    ambiguous = by_kind["ambiguous"]

    assert ambiguous.recall >= 0.80, (
        f"ambiguous recall@{K} fell to {ambiguous.recall:.3f}; "
        f"missed: {[q.query_id for q in ambiguous.misses]}"
    )


async def test_syllabus_parser_keeps_every_real_topic():
    from evals.syllabus import evaluate_heuristic

    run = evaluate_heuristic()

    assert run.topic_recall >= 0.95, f"topic recall fell to {run.topic_recall:.3f}"
    assert run.subject_recall >= 0.95, f"subject recall fell to {run.subject_recall:.3f}"


async def test_syllabus_parser_promotes_no_page_furniture():
    """The regression this dataset exists for.

    Page footers, textbook lists and exam boilerplate were being absorbed as
    topics, so roadmaps contained entries like "Page 4 of 4" and asked the
    learner to study them. Recall cannot see this failure -- only precision
    and this explicit check can.
    """
    from evals.syllabus import evaluate_heuristic

    run = evaluate_heuristic()

    offenders = {
        case.case_id: case.forbidden_found for case in run.cases if case.forbidden_found
    }
    assert not offenders, f"page furniture promoted to syllabus structure: {offenders}"
    assert run.topic_precision >= 0.95, (
        f"topic precision fell to {run.topic_precision:.3f}; "
        f"invented: {[c.spurious_topics for c in run.cases if c.spurious_topics]}"
    )
