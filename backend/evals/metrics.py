"""Ranking metrics for retrieval evaluation.

Four numbers, because each hides a different failure the others miss:

- **precision@k** -- of what you showed, how much was useful. Falls when the
  retriever pads the top-k with noise.
- **recall@k** -- of what was useful, how much you showed. Falls when relevant
  passages exist but never surface.
- **MRR** -- how far the reader scrolls before the first useful hit. A system
  can have decent precision and still bury the good answer at rank 8.
- **NDCG@k** -- position-weighted, so improving rank 1 counts for more than
  improving rank 9. This is the one to watch when comparing rerankers.

Every function takes ranked ids (best first) and the set of relevant ids, so
they apply to any retriever without knowing anything about it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


def precision_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    relevant = set(relevant_ids)
    if k <= 0:
        return 0.0
    top = ranked_ids[:k]
    if not top:
        return 0.0
    return sum(1 for doc_id in top if doc_id in relevant) / len(top)


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    found = sum(1 for doc_id in ranked_ids[:k] if doc_id in relevant)
    return found / len(relevant)


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    """1/rank of the first relevant hit; 0 if none was retrieved."""
    relevant = set(relevant_ids)
    for position, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Normalised discounted cumulative gain with binary relevance.

    Normalised against the best achievable ordering for this query, so a query
    with two relevant passages is not penalised for having fewer than a query
    with five.
    """
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0

    dcg = sum(
        1.0 / math.log2(position + 1)
        for position, doc_id in enumerate(ranked_ids[:k], start=1)
        if doc_id in relevant
    )
    ideal = sum(
        1.0 / math.log2(position + 1)
        for position in range(1, min(len(relevant), k) + 1)
    )
    return dcg / ideal if ideal else 0.0


@dataclass(frozen=True)
class QueryScore:
    """One query's scorecard, kept so a regression can be traced to its query."""

    query_id: str
    query: str
    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float
    ranked_ids: tuple[str, ...]
    relevant_ids: tuple[str, ...]

    @property
    def found_any(self) -> bool:
        return self.reciprocal_rank > 0.0


@dataclass(frozen=True)
class RunScore:
    """Aggregate over a query set."""

    k: int
    queries: tuple[QueryScore, ...]

    def _mean(self, attr: str) -> float:
        if not self.queries:
            return 0.0
        return sum(getattr(q, attr) for q in self.queries) / len(self.queries)

    @property
    def precision(self) -> float:
        return self._mean("precision")

    @property
    def recall(self) -> float:
        return self._mean("recall")

    @property
    def mrr(self) -> float:
        return self._mean("reciprocal_rank")

    @property
    def ndcg(self) -> float:
        return self._mean("ndcg")

    @property
    def precision_ceiling(self) -> float:
        """The best precision@k this query set physically allows.

        Most study questions have exactly one right passage, so at k=5 no
        retriever can beat 0.200 -- reading a raw precision@5 of 0.2 as "80%
        junk" is the obvious wrong conclusion. Reported next to it so the
        comparison is against what is achievable, not against 1.0.
        """
        if not self.queries:
            return 0.0
        return sum(
            min(len(q.relevant_ids), self.k) / self.k for q in self.queries
        ) / len(self.queries)

    @property
    def precision_vs_ceiling(self) -> float:
        """Precision as a fraction of what was achievable. This one targets 1.0."""
        ceiling = self.precision_ceiling
        return self.precision / ceiling if ceiling else 0.0

    @property
    def misses(self) -> tuple[QueryScore, ...]:
        """Queries that surfaced nothing relevant -- the ones worth reading."""
        return tuple(q for q in self.queries if not q.found_any)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "k": self.k,
            "queries": len(self.queries),
            f"precision@{self.k}": round(self.precision, 4),
            f"precision@{self.k}_ceiling": round(self.precision_ceiling, 4),
            "precision_vs_ceiling": round(self.precision_vs_ceiling, 4),
            f"recall@{self.k}": round(self.recall, 4),
            "mrr": round(self.mrr, 4),
            f"ndcg@{self.k}": round(self.ndcg, 4),
            "misses": len(self.misses),
        }


def score_query(
    query_id: str,
    query: str,
    ranked_ids: Sequence[str],
    relevant_ids: Sequence[str],
    k: int,
) -> QueryScore:
    return QueryScore(
        query_id=query_id,
        query=query,
        precision=precision_at_k(ranked_ids, relevant_ids, k),
        recall=recall_at_k(ranked_ids, relevant_ids, k),
        reciprocal_rank=reciprocal_rank(ranked_ids, relevant_ids),
        ndcg=ndcg_at_k(ranked_ids, relevant_ids, k),
        ranked_ids=tuple(ranked_ids),
        relevant_ids=tuple(relevant_ids),
    )


def format_scorecard(title: str, run: RunScore) -> str:
    """Human-readable summary, with the misses named."""
    lines = [
        f"{title}",
        "-" * len(title),
        f"  queries       {len(run.queries)}",
        f"  precision@{run.k:<4} {run.precision:.3f}"
        f"  ({run.precision_vs_ceiling:.0%} of the {run.precision_ceiling:.3f} ceiling)",
        f"  recall@{run.k:<7} {run.recall:.3f}",
        f"  MRR           {run.mrr:.3f}",
        f"  NDCG@{run.k:<9} {run.ndcg:.3f}",
    ]
    if run.misses:
        lines.append(f"  misses        {len(run.misses)}")
        for miss in run.misses:
            lines.append(f"    - [{miss.query_id}] {miss.query}")
    return "\n".join(lines)
