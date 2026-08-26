from __future__ import annotations

import re

from app.schemas.syllabus import (
    ParsedChapter,
    ParsedSubject,
    ParsedSyllabus,
    ParsedTopic,
)


def parse_heuristically(text: str, default_title: str) -> ParsedSyllabus:
    """Deterministic regex and heading parser for offline or fallback syllabus extraction."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    warnings: list[str] = ["Parsed using deterministic heuristic rules."]

    subjects: list[ParsedSubject] = []
    current_subject: ParsedSubject | None = None
    current_chapter: ParsedChapter | None = None
    current_topic: ParsedTopic | None = None

    # Regex patterns
    re_subject = re.compile(
        r"^(?:#\s+|Module\s+[\dIVXLCDM]+[:.\s-]*|Unit\s+[\dIVXLCDM]+[:.\s-]*|Subject[:.\s-]*|Section\s+[A-Z][:.\s-]*)(.*)$",
        re.IGNORECASE,
    )
    re_chapter = re.compile(
        r"^(?:##\s+|Chapter\s+[\dIVXLCDM]+[:.\s-]*|\d+[\.\)]\s+)(.*)$",
        re.IGNORECASE,
    )
    re_topic = re.compile(
        r"^(?:###\s+|\d+\.\d+[\.\)]?\s+|Topic[:.\s-]*|[-*]\s+)(.*)$",
        re.IGNORECASE,
    )
    re_subtopic = re.compile(
        r"^(?:\d+\.\d+\.\d+[\.\)]?\s+|\s*[-*]\s+|[a-z][\.\)]\s+)(.*)$",
        re.IGNORECASE,
    )

    def ensure_subject() -> ParsedSubject:
        nonlocal current_subject
        if current_subject is None:
            current_subject = ParsedSubject(
                title=default_title,
                description="General Curriculum",
                chapters=[],
                order_index=len(subjects) + 1,
            )
            subjects.append(current_subject)
        return current_subject

    def ensure_chapter() -> ParsedChapter:
        nonlocal current_chapter
        subj = ensure_subject()
        if current_chapter is None:
            current_chapter = ParsedChapter(
                title="Main Topics",
                description="",
                topics=[],
                order_index=len(subj.chapters) + 1,
            )
            subj.chapters.append(current_chapter)
        return current_chapter

    for line in lines:
        # 1. Check Subtopic (deepest level)
        if current_topic is not None and re_subtopic.match(line) and not line.startswith("#"):
            sub_match = re_subtopic.match(line)
            sub_title = sub_match.group(1).strip() if sub_match else line
            if sub_title and len(sub_title) < 120:
                current_topic.subtopics.append(sub_title)
                continue

        # 2. Check Subject
        if line.startswith("# ") or re_subject.match(line):
            m = re_subject.match(line)
            raw_title = m.group(1).strip() if m and m.group(1).strip() else line.lstrip("# ").strip()
            current_subject = ParsedSubject(
                title=raw_title or f"Subject {len(subjects) + 1}",
                description="",
                chapters=[],
                order_index=len(subjects) + 1,
            )
            subjects.append(current_subject)
            current_chapter = None
            current_topic = None
            continue

        # 3. Check Chapter
        if line.startswith("## ") or re_chapter.match(line):
            subj = ensure_subject()
            m = re_chapter.match(line)
            raw_title = m.group(1).strip() if m and m.group(1).strip() else line.lstrip("# ").strip()
            current_chapter = ParsedChapter(
                title=raw_title or f"Chapter {len(subj.chapters) + 1}",
                description="",
                topics=[],
                order_index=len(subj.chapters) + 1,
            )
            subj.chapters.append(current_chapter)
            current_topic = None
            continue

        # 4. Check Topic
        if line.startswith("### ") or re_topic.match(line):
            chap = ensure_chapter()
            m = re_topic.match(line)
            raw_title = m.group(1).strip() if m and m.group(1).strip() else line.lstrip("# ").strip()
            current_topic = ParsedTopic(
                title=raw_title or f"Topic {len(chap.topics) + 1}",
                description="",
                subtopics=[],
                order_index=len(chap.topics) + 1,
            )
            chap.topics.append(current_topic)
            continue

        # 5. Non-heading descriptive text or bullet
        if current_topic is not None:
            if len(line) < 100:
                current_topic.subtopics.append(line)
            else:
                if not current_topic.description:
                    current_topic.description = line[:200]
        elif current_chapter is not None:
            # Treat line as a topic
            current_topic = ParsedTopic(
                title=line[:80],
                description="",
                subtopics=[],
                order_index=len(current_chapter.topics) + 1,
            )
            current_chapter.topics.append(current_topic)
        else:
            # Treat line as a topic in default chapter
            chap = ensure_chapter()
            current_topic = ParsedTopic(
                title=line[:80],
                description="",
                subtopics=[],
                order_index=len(chap.topics) + 1,
            )
            chap.topics.append(current_topic)

    # Ensure every subject has at least 1 chapter and every chapter has at least 1 topic
    if not subjects:
        subjects.append(
            ParsedSubject(
                title=default_title,
                description="",
                chapters=[
                    ParsedChapter(
                        title="General Chapter",
                        description="",
                        topics=[
                            ParsedTopic(
                                title="Introduction & Overview",
                                description="Core syllabus topics",
                                order_index=1,
                            )
                        ],
                        order_index=1,
                    )
                ],
                order_index=1,
            )
        )

    total_chapters = sum(len(s.chapters) for s in subjects)
    total_topics = sum(len(c.topics) for s in subjects for c in s.chapters)

    return ParsedSyllabus(
        title=default_title,
        description="Extracted curriculum structure",
        subjects=subjects,
        total_chapters=total_chapters,
        total_topics=total_topics,
        warnings=warnings,
    )
