from __future__ import annotations

import json
import logging
import re

from app.config import Settings, get_settings
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.schemas.syllabus import (
    ParsedChapter,
    ParsedSubject,
    ParsedSyllabus,
    ParsedTopic,
)
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)


class _TruncatedSyllabusResponse(Exception):
    """The model hit its output ceiling before finishing the JSON tree."""


class SyllabusParser:
    """Extracts structured Subjects, Chapters, Topics, and Subtopics from syllabus documents."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def parse_text(self, text: str, default_title: str = "Syllabus") -> ParsedSyllabus:
        """Parse raw extracted syllabus text into a structured hierarchical syllabus."""
        clean_text = text.strip()
        if not clean_text:
            return ParsedSyllabus(
                title=default_title,
                subjects=[],
                total_chapters=0,
                total_topics=0,
                warnings=["Empty syllabus content provided."],
            )

        # 1. Attempt AI-powered structured extraction
        # A long syllabus asks for a large JSON tree, and the reply gets cut off
        # at the token ceiling mid-object. That surfaced as a JSON error and
        # dropped straight to the heuristic parser, which turns page headers and
        # stray glyphs into "topics" -- 376 nodes of noise for a 43-page
        # syllabus. Shrink the slice and try again before giving up: less input
        # means a smaller tree, which fits.
        for slice_chars in self.AI_INPUT_SLICES:
            try:
                parsed = await self._parse_with_ai(
                    clean_text, default_title, max_chars=slice_chars
                )
                if parsed and parsed.subjects:
                    return parsed
                logger.warning(
                    "AI syllabus parsing returned no subjects at %d characters.", slice_chars
                )
            except _TruncatedSyllabusResponse:
                logger.warning(
                    "AI syllabus response hit the token limit at %d characters of input; "
                    "retrying with a smaller slice.",
                    slice_chars,
                )
                continue
            except Exception as e:
                logger.warning(
                    "AI syllabus parsing failed, falling back to heuristic parser: %s", e
                )
                break

        # 2. Fallback to deterministic regex-based parser
        return self._parse_heuristically(clean_text, default_title)

    #: Input sizes to try, largest first. Each retry asks the model to describe
    #: less text, so the JSON it must return shrinks with it.
    AI_INPUT_SLICES = (12000, 6000, 3000)

    #: Room for the JSON tree. 3500 could not hold the structure a
    #: 12,000-character syllabus produces, so every large syllabus truncated.
    #: The ceiling has to clear reasoning overhead as well as the JSON: routers
    #: like openrouter/auto happily pick a reasoning model, and its thinking
    #: tokens are charged against this same budget -- one observed reply spent
    #: 1,623 reasoning tokens to emit 195 characters of visible output.
    AI_MAX_OUTPUT_TOKENS = 16000

    async def _parse_with_ai(
        self, text: str, default_title: str, max_chars: int = 12000
    ) -> ParsedSyllabus | None:
        """Use LLM model client to extract nested syllabus hierarchy."""
        client = get_model_client(self.settings)

        system_prompt = (
            "You are an expert curriculum structuring assistant. "
            "Analyze the provided syllabus text and extract the complete educational hierarchy: "
            "Subjects/Modules -> Chapters/Units -> Topics -> Subtopics.\n"
            "Return ONLY valid JSON matching this exact schema:\n"
            "{\n"
            '  "title": "Syllabus Title",\n'
            '  "description": "Short overview",\n'
            '  "subjects": [\n'
            "    {\n"
            '      "title": "Subject or Module Name",\n'
            '      "description": "Overview",\n'
            '      "chapters": [\n'
            "        {\n"
            '          "title": "Chapter or Unit Name",\n'
            '          "description": "Overview",\n'
            '          "topics": [\n'
            "            {\n"
            '              "title": "Topic Name",\n'
            '              "description": "Topic details",\n'
            '              "subtopics": ["Subtopic 1", "Subtopic 2"],\n'
            '              "estimated_hours": 2.5,\n'
            '              "learning_objectives": ["Objective 1"]\n'
            "            }\n"
            "          ]\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        user_content = f"Syllabus Text (Truncated to first 12,000 characters if long):\n{text[:12000]}"

        try:
            response = await client.chat_complete(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_content),
                ],
                temperature=0.1,
                max_tokens=self.AI_MAX_OUTPUT_TOKENS,
            )

            if response.truncated:
                # Parsing this would fail anyway, and the failure would look
                # like a malformed reply rather than one that ran out of room.
                raise _TruncatedSyllabusResponse()

            raw_json = extract_json_payload(response.content)

            data = json.loads(raw_json)
            if not isinstance(data, dict):
                return None

            if "title" not in data or not data["title"]:
                data["title"] = default_title

            # Re-index order indices sequentially
            subjects: list[ParsedSubject] = []
            s_idx = 1
            for raw_subj in data.get("subjects", []):
                chapters: list[ParsedChapter] = []
                c_idx = 1
                for raw_chap in raw_subj.get("chapters", []):
                    topics: list[ParsedTopic] = []
                    t_idx = 1
                    for raw_top in raw_chap.get("topics", []):
                        topics.append(
                            ParsedTopic(
                                title=str(raw_top.get("title", f"Topic {t_idx}")),
                                description=str(raw_top.get("description", "")),
                                subtopics=[str(s) for s in raw_top.get("subtopics", [])],
                                order_index=t_idx,
                                estimated_hours=raw_top.get("estimated_hours"),
                                learning_objectives=[str(o) for o in raw_top.get("learning_objectives", [])],
                            )
                        )
                        t_idx += 1
                    chapters.append(
                        ParsedChapter(
                            title=str(raw_chap.get("title", f"Chapter {c_idx}")),
                            description=str(raw_chap.get("description", "")),
                            topics=topics,
                            order_index=c_idx,
                        )
                    )
                    c_idx += 1
                subjects.append(
                    ParsedSubject(
                        title=str(raw_subj.get("title", f"Subject {s_idx}")),
                        description=str(raw_subj.get("description", "")),
                        chapters=chapters,
                        order_index=s_idx,
                    )
                )
                s_idx += 1

            total_chapters = sum(len(s.chapters) for s in subjects)
            total_topics = sum(len(c.topics) for s in subjects for c in s.chapters)

            return ParsedSyllabus(
                title=data.get("title", default_title),
                description=data.get("description", ""),
                subjects=subjects,
                total_chapters=total_chapters,
                total_topics=total_topics,
            )
        finally:
            await client.close()

    def _parse_heuristically(self, text: str, default_title: str) -> ParsedSyllabus:
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
