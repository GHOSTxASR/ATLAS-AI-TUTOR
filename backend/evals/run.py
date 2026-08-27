"""Run the evals and print a scorecard.

    python -m evals.run                 # everything that needs no API key
    python -m evals.run retrieval       # retrieval only
    python -m evals.run syllabus        # syllabus structure only
    python -m evals.run --json          # machine-readable, for tracking over time

Nothing here needs a key: retrieval embeds locally, and the syllabus eval
scores the deterministic parser. The AI parser is measured by the same
dataset when a chat provider is configured -- see evals/syllabus.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from evals.metrics import format_scorecard


async def _retrieval(k: int) -> dict[str, object]:
    from evals.retrieval import evaluate, evaluate_by_kind

    overall = await evaluate(k=k)
    by_kind = await evaluate_by_kind(k=k)

    print(format_scorecard(f"Retrieval (k={k})", overall))
    print()
    print("  by query kind")
    for kind in sorted(by_kind):
        run = by_kind[kind]
        print(
            f"    {kind:<12} n={len(run.queries):<3} "
            f"recall@{k}={run.recall:.3f}  MRR={run.mrr:.3f}  NDCG@{k}={run.ndcg:.3f}"
        )
    print()

    return {
        "overall": overall.as_dict(),
        "by_kind": {kind: run.as_dict() for kind, run in by_kind.items()},
    }


async def _syllabus() -> dict[str, object]:
    from evals.syllabus import evaluate_heuristic, format_syllabus_scorecard

    result = evaluate_heuristic()
    print(format_syllabus_scorecard("Syllabus structure (deterministic parser)", result))
    print()
    return result.as_dict()


async def main() -> int:
    parser = argparse.ArgumentParser(prog="evals.run", description=__doc__)
    parser.add_argument(
        "suite",
        nargs="?",
        default="all",
        choices=["all", "retrieval", "syllabus"],
        help="which suite to run (default: all)",
    )
    parser.add_argument("-k", type=int, default=5, help="retrieval cutoff (default: 5)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    results: dict[str, object] = {}
    if args.suite in ("all", "retrieval"):
        results["retrieval"] = await _retrieval(args.k)
    if args.suite in ("all", "syllabus"):
        results["syllabus"] = await _syllabus()

    if args.json:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
