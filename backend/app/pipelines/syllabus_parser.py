from __future__ import annotations

import json
import logging

from app.config import Settings, get_settings
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.pipelines.syllabus_heuristics import parse_heuristically
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
        return parse_heuristically(clean_text, default_title)

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

