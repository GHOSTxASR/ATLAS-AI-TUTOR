"""Measure what the retriever actually returns.

Every LLM-adjacent bug found in this project so far was found by a human
noticing something looked off -- undersized token budgets, a null content
field, a heuristic fallback that had been silently active for weeks. None of
those had a number attached, so none of them could regress a test.

This indexes a golden corpus through the real ``VectorStore`` and queries it
through the real ``MultiSourceRetriever``, so the number moves when the
pipeline changes. It embeds locally, which means it needs no API key and can
therefore run in CI.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from evals.metrics import RunScore, score_query

DATASETS = Path(__file__).parent / "datasets"
CORPUS_PATH = DATASETS / "retrieval_corpus.json"
QUERIES_PATH = DATASETS / "retrieval_queries.json"

#: The profile the corpus is indexed under. Vector collections are namespaced
#: per profile, so this keeps eval vectors away from any real ones.
EVAL_PROFILE_ID = "eval-profile"


@dataclass(frozen=True)
class Passage:
    id: str
    subject: str
    text: str


@dataclass(frozen=True)
class Query:
    id: str
    kind: str
    query: str
    relevant: tuple[str, ...]


def load_corpus(path: Path = CORPUS_PATH) -> list[Passage]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Passage(id=p["id"], subject=p["subject"], text=p["text"])
        for p in raw["passages"]
    ]


def load_queries(path: Path = QUERIES_PATH) -> list[Query]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Query(id=q["id"], kind=q["kind"], query=q["query"], relevant=tuple(q["relevant"]))
        for q in raw["queries"]
    ]


class RetrievalHarness:
    """Indexes the corpus into a throwaway vector store and queries it.

    Use as an async context manager; the temporary data directory is removed on
    exit so runs never accumulate or read each other's vectors.
    """

    def __init__(self, corpus: Sequence[Passage] | None = None):
        self.corpus = list(corpus) if corpus is not None else load_corpus()
        self._tmpdir: str | None = None
        self._store: Any = None
        self._retriever: Any = None

    async def __aenter__(self) -> RetrievalHarness:
        from app.config import get_settings
        from app.rag.retriever import MultiSourceRetriever
        from app.rag.vector_store import VectorStore

        self._tmpdir = tempfile.mkdtemp(prefix="atlas-eval-")
        root = Path(self._tmpdir)
        base = get_settings()
        # Point the vector store at the temp dir so an eval run can never touch
        # a real profile's vectors, and force local embeddings so the run needs
        # no API key and is reproducible.
        settings = replace(
            base,
            paths=replace(base.paths, data_dir=root, chroma_dir=root / "chroma"),
            model=replace(base.model, embedding_provider="local", embedding_backend="auto"),
        )

        self._store = VectorStore(settings=settings)
        self._retriever = MultiSourceRetriever(settings=settings, vector_store=self._store)
        await self._index()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def _index(self) -> None:
        """Index through the same call the document pipeline uses."""
        for passage in self.corpus:
            await self._store.index_document_chunks(
                profile_id=EVAL_PROFILE_ID,
                doc_id=passage.id,
                chunks=[{"text": passage.text, "chunk_index": 0, "id": passage.id}],
                filename=f"{passage.subject}.md",
                file_type="md",
            )

    async def rank(self, query: str, top_k: int) -> list[str]:
        """Passage ids for one query, best first."""
        results = await self._retriever.retrieve_documents(
            profile_id=EVAL_PROFILE_ID, query=query, top_k=top_k
        )
        return [r.source_id for r in results]

    async def run(self, queries: Sequence[Query] | None = None, k: int = 5) -> RunScore:
        cases = list(queries) if queries is not None else load_queries()
        scored = []
        for case in cases:
            ranked = await self.rank(case.query, top_k=k)
            scored.append(score_query(case.id, case.query, ranked, case.relevant, k))
        return RunScore(k=k, queries=tuple(scored))


async def evaluate(k: int = 5) -> RunScore:
    """Index the golden corpus, run every query, return the scorecard."""
    async with RetrievalHarness() as harness:
        return await harness.run(k=k)


async def evaluate_by_kind(k: int = 5) -> dict[str, RunScore]:
    """Same run, split by query kind, so a regression can be localised.

    Paraphrase and ambiguous queries fail for different reasons: the first
    when the embedding model is weak at synonymy, the second when retrieval
    ignores context. One combined number hides which broke.
    """
    queries = load_queries()
    async with RetrievalHarness() as harness:
        full = await harness.run(queries, k=k)

    by_id = {q.query_id: q for q in full.queries}
    grouped: dict[str, list] = {}
    for case in queries:
        grouped.setdefault(case.kind, []).append(by_id[case.id])
    return {kind: RunScore(k=k, queries=tuple(scores)) for kind, scores in grouped.items()}
