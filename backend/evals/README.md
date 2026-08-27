# Evals

Measurements of whether the AI parts of Atlas actually work, as opposed to
whether they run without raising.

## Why this exists

Every LLM-adjacent bug found in this project so far was found by a human
noticing that something looked off:

- the memory extractor returned nothing for weeks — a reasoning model spent its
  whole budget thinking and returned a null content field
- syllabus parsing silently fell back to a heuristic that turned page footers
  into topics, so roadmaps contained "Page 4 of 12"
- short answers were graded on keyword overlap rather than meaning, because the
  evaluator's 350-token budget was spent before it wrote any JSON

None of those raised. None had a number attached, so none could regress a test,
and each survived until somebody happened to look at the right output. That is
the gap these close.

## Running them

```bash
python -m evals.run                 # every suite that needs no API key
python -m evals.run retrieval       # retrieval only
python -m evals.run syllabus        # syllabus structure only
python -m evals.run --json          # machine-readable, for tracking over time
```

Nothing here needs a key. Retrieval embeds locally, and the syllabus suite
scores the deterministic parser — which is why both can gate CI.

The same numbers are asserted as thresholds in
`app/tests/evals/test_eval_thresholds.py`, so `pytest` fails on a regression
without anyone having to read a scorecard.

## Suites

### Retrieval

Indexes a golden corpus through the real `VectorStore` and queries it through
the real `MultiSourceRetriever`, so the number moves when the pipeline changes
rather than when a reimplementation of it changes.

22 queries over 22 passages, phrased the way a student types them. Three kinds,
scored separately because they fail for different reasons:

| kind | what it catches |
|---|---|
| `paraphrase` | asks for a concept without naming it — fails when the embedding model is weak at synonymy |
| `ambiguous` | *induction*, *tree*, *work* mean different things in different subjects — fails when retrieval degrades to keyword matching |
| `multi` | more than one passage genuinely answers it — fails when the retriever fixates on one |

Four metrics, because each hides a failure the others miss: **precision@k**
(is the top-k padded with noise), **recall@k** (do relevant passages surface at
all), **MRR** (how far the reader scrolls to the first useful hit), **NDCG@k**
(position-weighted — the one to watch when comparing rerankers).

> **Reading precision@5.** Most queries have exactly one relevant passage, so
> the arithmetic ceiling is 0.200. The scorecard prints precision against that
> ceiling rather than against 1.0, because 0.200 does not mean "80% junk".

### Syllabus structure

Parses fixtures in the formats students upload — markdown headings, numbered
outlines, university `Unit I / Unit II` style — and compares the structure
against a known-correct one.

Scored on recall **and** precision, because they catch opposite failures.
Recall falls when real topics are missed. Precision falls when page furniture,
textbook lists and exam boilerplate get promoted into the syllabus — which is
the bug that shipped, and which recall alone cannot see.

The `university-units-with-noise` fixture exists specifically for this: it
carries page footers, a "Prescribed Textbooks" section and an exam-pattern line
that must never reach the roadmap.

## Adding a case

Add to the JSON in `datasets/` — no code change needed.

Write queries a student would actually type, not keyword strings; a golden set
made of keywords measures string matching and will pass no matter how badly
retrieval degrades. Include at least one case that is *supposed* to be hard.
A dataset that cannot fail is not measuring anything.

For `relevant`, list every passage a tutor could legitimately cite. Being too
strict punishes correct behaviour; being too loose makes the metric unable to
fail.

## What is not covered yet

- **Tutoring quality.** Whether an explanation is *good* needs either human
  rating or an LLM judge, and an unvalidated judge is just a second model's
  opinion. Not attempted rather than done badly.
- **Quiz question quality.** Same problem. Question *validity* — options
  parse, exactly one is correct, numerical answers have a tolerance — is
  checkable without a judge and is the obvious next suite.
- **The AI syllabus parser.** `evals.syllabus.evaluate_ai` scores it against
  the same dataset, but it needs a configured chat provider, so it cannot gate
  CI and is run on demand.
