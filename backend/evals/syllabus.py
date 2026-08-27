"""Measure whether syllabus parsing produces the structure it was given.

A syllabus parse is the root of everything downstream -- the roadmap, the
graph, what gets quizzed. When it silently degraded to the heuristic parser,
page footers became topics and roadmaps filled with entries like "Page 4 of
12". Nothing failed; the output was just wrong, and it stayed wrong until
somebody looked.

Two numbers, because they catch opposite failures:

- **recall** -- did the real topics survive? Falls when the parser misses
  structure.
- **precision** -- did anything fake get promoted to a topic? Falls when the
  parser treats page furniture, textbook lists and exam boilerplate as
  content. This is the one that would have caught the shipped bug.

The deterministic parser is scored with no API key, so it can gate CI. The AI
parser is scored by the same dataset when a chat provider is configured.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DATASETS = Path(__file__).parent / "datasets"
SYLLABI_PATH = DATASETS / "syllabi.json"


def normalise(title: str) -> str:
    """Compare titles by their words, not their punctuation.

    "Newton's Laws of Motion" and "Newtons Laws of Motion" are the same topic;
    scoring them as a miss would measure the fixture's punctuation rather than
    the parser.
    """
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


@dataclass(frozen=True)
class SyllabusCase:
    id: str
    format: str
    default_title: str
    text: str
    subjects: tuple[str, ...]
    chapters: tuple[str, ...]
    topics: tuple[str, ...]
    must_not_appear: tuple[str, ...]


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    format: str
    topic_recall: float
    topic_precision: float
    subject_recall: float
    chapter_recall: float
    missed_topics: tuple[str, ...]
    spurious_topics: tuple[str, ...]
    forbidden_found: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """Nothing missed, nothing invented, no page furniture promoted."""
        return (
            self.topic_recall == 1.0
            and not self.forbidden_found
            and self.subject_recall == 1.0
        )


@dataclass(frozen=True)
class SyllabusRunScore:
    cases: tuple[CaseScore, ...]

    def _mean(self, attr: str) -> float:
        if not self.cases:
            return 0.0
        return sum(getattr(c, attr) for c in self.cases) / len(self.cases)

    @property
    def topic_recall(self) -> float:
        return self._mean("topic_recall")

    @property
    def topic_precision(self) -> float:
        return self._mean("topic_precision")

    @property
    def subject_recall(self) -> float:
        return self._mean("subject_recall")

    @property
    def chapter_recall(self) -> float:
        return self._mean("chapter_recall")

    @property
    def forbidden_total(self) -> int:
        """Page furniture promoted to a topic. This must be zero."""
        return sum(len(c.forbidden_found) for c in self.cases)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "cases": len(self.cases),
            "topic_recall": round(self.topic_recall, 4),
            "topic_precision": round(self.topic_precision, 4),
            "subject_recall": round(self.subject_recall, 4),
            "chapter_recall": round(self.chapter_recall, 4),
            "forbidden_promoted": self.forbidden_total,
        }


def load_cases(path: Path = SYLLABI_PATH) -> list[SyllabusCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for entry in raw["syllabi"]:
        expected = entry["expected"]
        cases.append(
            SyllabusCase(
                id=entry["id"],
                format=entry["format"],
                default_title=entry["default_title"],
                text=entry["text"],
                subjects=tuple(expected.get("subjects", [])),
                chapters=tuple(expected.get("chapters", [])),
                topics=tuple(expected.get("topics", [])),
                must_not_appear=tuple(expected.get("must_not_appear", [])),
            )
        )
    return cases


def _collect(parsed) -> tuple[set[str], set[str], set[str]]:
    """Every subject, chapter and topic title the parser produced."""
    subjects, chapters, topics = set(), set(), set()
    for subject in parsed.subjects:
        subjects.add(normalise(subject.title))
        for chapter in subject.chapters:
            chapters.add(normalise(chapter.title))
            for topic in chapter.topics:
                topics.add(normalise(topic.title))
                topics.update(normalise(s) for s in topic.subtopics)
    return subjects, chapters, topics


def score_case(case: SyllabusCase, parsed) -> CaseScore:
    got_subjects, got_chapters, got_topics = _collect(parsed)

    want_topics = {normalise(t) for t in case.topics}
    want_subjects = {normalise(s) for s in case.subjects}
    want_chapters = {normalise(c) for c in case.chapters}

    found_topics = want_topics & got_topics
    # Everything the parser produced that no level of the expected structure
    # accounts for. Chapter and subject names are excluded: emitting one as a
    # topic is a depth disagreement, not an invention.
    accounted = want_topics | want_subjects | want_chapters
    spurious = got_topics - accounted

    forbidden = tuple(
        original
        for original in case.must_not_appear
        if any(normalise(original) in got or got in normalise(original)
               for got in got_topics | got_chapters | got_subjects
               if got)
    )

    return CaseScore(
        case_id=case.id,
        format=case.format,
        topic_recall=len(found_topics) / len(want_topics) if want_topics else 0.0,
        topic_precision=(
            len(found_topics) / len(got_topics) if got_topics else 0.0
        ),
        subject_recall=(
            len(want_subjects & got_subjects) / len(want_subjects) if want_subjects else 0.0
        ),
        chapter_recall=(
            len(want_chapters & got_chapters) / len(want_chapters) if want_chapters else 0.0
        ),
        missed_topics=tuple(sorted(want_topics - got_topics)),
        spurious_topics=tuple(sorted(spurious)),
        forbidden_found=forbidden,
    )


def evaluate_heuristic(cases: Sequence[SyllabusCase] | None = None) -> SyllabusRunScore:
    """Score the deterministic parser. No API key, no network."""
    from app.pipelines.syllabus_heuristics import parse_heuristically

    todo = list(cases) if cases is not None else load_cases()
    scored = [
        score_case(case, parse_heuristically(case.text, case.default_title))
        for case in todo
    ]
    return SyllabusRunScore(cases=tuple(scored))


async def evaluate_ai(cases: Sequence[SyllabusCase] | None = None) -> SyllabusRunScore:
    """Score the AI parser. Needs a configured chat provider."""
    from app.pipelines.syllabus_parser import SyllabusParser

    todo = list(cases) if cases is not None else load_cases()
    parser = SyllabusParser()
    scored = []
    for case in todo:
        parsed = await parser.parse_text(case.text, default_title=case.default_title)
        scored.append(score_case(case, parsed))
    return SyllabusRunScore(cases=tuple(scored))


def format_syllabus_scorecard(title: str, run: SyllabusRunScore) -> str:
    lines = [
        title,
        "-" * len(title),
        f"  cases            {len(run.cases)}",
        f"  topic recall     {run.topic_recall:.3f}",
        f"  topic precision  {run.topic_precision:.3f}",
        f"  subject recall   {run.subject_recall:.3f}",
        f"  chapter recall   {run.chapter_recall:.3f}",
        f"  page furniture   {run.forbidden_total}  (must be 0)",
    ]
    for case in run.cases:
        if case.clean:
            continue
        lines.append(f"    [{case.case_id}] ({case.format})")
        if case.missed_topics:
            lines.append(f"      missed:   {', '.join(case.missed_topics[:5])}")
        if case.forbidden_found:
            lines.append(f"      promoted: {', '.join(case.forbidden_found[:5])}")
        if case.spurious_topics:
            lines.append(f"      invented: {', '.join(case.spurious_topics[:5])}")
    return "\n".join(lines)
