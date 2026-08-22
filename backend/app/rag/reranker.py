from __future__ import annotations

import logging
import re
from typing import Sequence

from app.rag.vector_store import VectorSearchResult

logger = logging.getLogger(__name__)


def _tokenize_words(text: str) -> set[str]:
    """Extract lowercase alphanumeric word tokens."""
    return set(re.findall(r"\b[a-z0-9_]+\b", text.lower()))


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _lexical_overlap_score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    """Compute lexical query term coverage in document."""
    if not query_tokens or not doc_tokens:
        return 0.0
    matched = len(query_tokens & doc_tokens)
    return matched / len(query_tokens)


class Reranker:
    """Re-scores, deduplicates, and applies Maximal Marginal Relevance (MMR) diversification."""

    DEFAULT_LAMBDA = 0.7  # Balance between relevance (0.7) and diversity (0.3)

    def __init__(self, lambda_param: float = DEFAULT_LAMBDA):
        self.lambda_param = lambda_param

    def score_relevance(self, query: str, candidate: VectorSearchResult) -> float:
        """Combine vector similarity score with lexical keyword overlap."""
        q_tokens = _tokenize_words(query)
        d_tokens = _tokenize_words(candidate.text)
        lex_score = _lexical_overlap_score(q_tokens, d_tokens)

        # 70% vector score + 30% lexical overlap score
        combined = (0.7 * candidate.score) + (0.3 * lex_score)
        return min(1.0, max(0.0, combined))

    def rerank_and_diversify(
        self,
        query: str,
        candidates: Sequence[VectorSearchResult],
        top_k: int = 8,
        lambda_param: float | None = None,
    ) -> list[VectorSearchResult]:
        """Apply MMR selection over candidates to maximize relevance and information diversity."""
        if not candidates:
            return []

        lam = lambda_param if lambda_param is not None else self.lambda_param

        # Precompute tokens and initial relevance scores
        scored_candidates: list[tuple[VectorSearchResult, set[str], float]] = []
        seen_texts: set[str] = set()

        for c in candidates:
            clean_text = c.text.strip()
            # Skip exact text duplicates
            if clean_text in seen_texts:
                continue
            seen_texts.add(clean_text)

            c_tokens = _tokenize_words(clean_text)
            rel_score = self.score_relevance(query, c)
            # Update candidate score with composite score
            c.score = round(rel_score, 4)
            scored_candidates.append((c, c_tokens, rel_score))

        if not scored_candidates:
            return []

        selected: list[VectorSearchResult] = []
        selected_token_sets: list[set[str]] = []
        remaining = list(scored_candidates)

        while remaining and len(selected) < top_k:
            best_idx = -1
            best_mmr_score = -float("inf")

            for idx, (cand, cand_tokens, rel_score) in enumerate(remaining):
                if not selected:
                    # First item is purely highest relevance
                    mmr_score = rel_score
                else:
                    # Max similarity to any already selected chunk
                    max_sim_to_selected = max(
                        _jaccard_similarity(cand_tokens, sel_tokens)
                        for sel_tokens in selected_token_sets
                    )
                    mmr_score = (lam * rel_score) - ((1.0 - lam) * max_sim_to_selected)

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            if best_idx == -1:
                break

            chosen_item, chosen_tokens, _ = remaining.pop(best_idx)
            selected.append(chosen_item)
            selected_token_sets.append(chosen_tokens)

        return selected


# Alias
DocumentReranker = Reranker
