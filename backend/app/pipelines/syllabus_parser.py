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


def _syllabus_from_payload(data: dict, default_title: str) -> ParsedSyllabus:
    """Turn a model's JSON reply into a syllabus, numbering everything in order.

    Shared by parsing a syllabus document and by writing one from course
    materials: both ask for the same shape back, and both need the indices
    renumbered rather than trusting whatever the model counted.
    """
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

    #: How much of each document the model is shown when writing a syllabus
    #: from course materials. Enough to tell what a document covers -- the
    #: whole library would not fit, and the job is to name topics rather than
    #: reproduce text.
    MATERIAL_EXCERPT_CHARS = 3000

    #: The most documents read in one pass. Past this the excerpts crowd each
    #: other out and the curriculum comes back vaguer than the materials.
    MAX_MATERIALS = 12

    async def synthesize_from_materials(
        self, sources: list[tuple[str, str]], default_title: str = "Course Roadmap"
    ) -> ParsedSyllabus | None:
        """Write a syllabus from course materials, for when none was uploaded.

        A learner with lecture slides and chapter PDFs but no syllabus had no
        way to get a roadmap at all: generation needed a syllabus, and the only
        thing that could produce one was a syllabus.

        This reads across the materials and lays out the course they teach --
        in teaching order, foundations first, with a topic that several
        documents touch appearing once.

        `sources` are (filename, text) pairs. Returns None when the model
        cannot produce a usable curriculum, leaving the caller to say so
        rather than handing back an empty roadmap.
        """
        if not sources:
            return None

        excerpts = []
        for filename, text in sources[: self.MAX_MATERIALS]:
            excerpt = (text or "").strip()[: self.MATERIAL_EXCERPT_CHARS]
            if excerpt:
                excerpts.append(f"--- {filename} ---\n{excerpt}")
        if not excerpts:
            return None

        system_prompt = (
            "You are a curriculum designer. You are given excerpts from the materials of "
            "a single course -- lecture notes, slides, chapters. No syllabus exists, so "
            "you are writing one.\n\n"
            "Work out what course these materials teach, and lay it out as a curriculum:\n"
            "- Order it for learning. A topic comes after whatever it depends on, not in "
            "the order the files happened to be uploaded.\n"
            "- Group related topics into chapters, and chapters into subjects or modules.\n"
            "- A topic that several documents cover appears once.\n"
            "- Name topics the way a syllabus would, not after filenames or slide titles.\n"
            "- Cover what the materials actually contain. Do not fall back on a standard "
            "curriculum for the subject, and do not pad it out.\n\n"
            "Return ONLY valid JSON matching this exact schema:\n"
            "{\n"
            '  "title": "Course Title",\n'
            '  "description": "One line on what the course covers",\n'
            '  "subjects": [\n'
            "    {\n"
            '      "title": "Subject or Module Name",\n'
            '      "description": "Overview",\n'
            '      "chapters": [\n'
            "        {\n"
            '          "title": "Chapter Name",\n'
            '          "description": "Overview",\n'
            '          "topics": [\n'
            '            {"title": "Topic Name", "description": "One line", '
            '"subtopics": ["Subtopic"]}\n'
            "          ]\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        user_content = (
            f"Course materials ({len(excerpts)} documents), each truncated:\n\n"
            + "\n\n".join(excerpts)
        )

        client = get_model_client(self.settings)
        try:
            response = await client.chat_complete(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_content),
                ],
                temperature=0.2,
                max_tokens=self.AI_MAX_OUTPUT_TOKENS,
            )
            if response.truncated:
                logger.warning("Ran out of room writing a syllabus from materials.")
                return None

            data = json.loads(extract_json_payload(response.content))
            if not isinstance(data, dict):
                return None
            if not data.get("title"):
                data["title"] = default_title

            syllabus = _syllabus_from_payload(data, default_title)
            return syllabus if syllabus.total_topics else None
        except Exception as e:
            logger.warning("Could not write a syllabus from the materials: %s", e)
            return None
        finally:
            await client.close()

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

            return _syllabus_from_payload(data, default_title)
        finally:
            await client.close()

