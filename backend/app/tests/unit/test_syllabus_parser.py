from __future__ import annotations

from typing import AsyncIterator
import pytest

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.pipelines.syllabus_heuristics import parse_heuristically
from app.pipelines.syllabus_parser import SyllabusParser


class MockSyllabusLLM(BaseModelClient):
    """Mock LLM returning structured syllabus hierarchy JSON."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        json_payload = (
            '{\n'
            '  "title": "Computer Science GATE Syllabus",\n'
            '  "description": "Comprehensive GATE CS curriculum",\n'
            '  "subjects": [\n'
            '    {\n'
            '      "title": "Data Structures & Algorithms",\n'
            '      "description": "Core computer science algorithms",\n'
            '      "chapters": [\n'
            '        {\n'
            '          "title": "Linear Data Structures",\n'
            '          "description": "Arrays, stacks, queues, and linked lists",\n'
            '          "topics": [\n'
            '            {\n'
            '              "title": "Linked Lists",\n'
            '              "description": "Singly and doubly linked lists",\n'
            '              "subtopics": ["Pointer operations", "Reversal", "Cycle detection"],\n'
            '              "estimated_hours": 3.0\n'
            '            },\n'
            '            {\n'
            '              "title": "Stacks and Queues",\n'
            '              "description": "LIFO and FIFO data structures",\n'
            '              "subtopics": ["Infix to postfix conversion", "Circular queues"],\n'
            '              "estimated_hours": 2.5\n'
            '            }\n'
            '          ]\n'
            '        }\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            '}'
        )
        return ChatResponse(content=json_payload)

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_syllabus"


@pytest.mark.asyncio
async def test_syllabus_parser_ai_extraction(monkeypatch):
    monkeypatch.setattr("app.pipelines.syllabus_parser.get_model_client", lambda s: MockSyllabusLLM())

    text = "Syllabus Content for Computer Science"
    parser = SyllabusParser()
    parsed = await parser.parse_text(text, default_title="GATE Syllabus")

    assert parsed.title == "Computer Science GATE Syllabus"
    assert len(parsed.subjects) == 1
    subj = parsed.subjects[0]
    assert subj.title == "Data Structures & Algorithms"
    assert len(subj.chapters) == 1
    chap = subj.chapters[0]
    assert chap.title == "Linear Data Structures"
    assert len(chap.topics) == 2
    topic1 = chap.topics[0]
    assert topic1.title == "Linked Lists"
    assert topic1.subtopics == ["Pointer operations", "Reversal", "Cycle detection"]
    assert topic1.estimated_hours == 3.0
    assert parsed.total_chapters == 1
    assert parsed.total_topics == 2


@pytest.mark.asyncio
async def test_syllabus_parser_heuristic_fallback_markdown():

    markdown_syllabus = (
        "# Physics: Mechanics\n"
        "## Kinematics\n"
        "### 1D Motion\n"
        "- Velocity and acceleration\n"
        "- Equations of motion\n"
        "### 2D Motion\n"
        "- Projectile motion trajectory\n"
        "- Circular motion basics\n"
        "## Dynamics\n"
        "### Newton's Laws\n"
        "- Inertia\n"
        "- Force and momentum\n"
        "- Action-Reaction pairs\n"
    )

    parsed = parse_heuristically(markdown_syllabus, default_title="Physics")

    assert len(parsed.subjects) == 1
    subj = parsed.subjects[0]
    assert "Mechanics" in subj.title
    assert len(subj.chapters) == 2
    assert subj.chapters[0].title == "Kinematics"
    assert len(subj.chapters[0].topics) == 2
    assert subj.chapters[0].topics[0].title == "1D Motion"
    assert "Velocity and acceleration" in subj.chapters[0].topics[0].subtopics
    assert subj.chapters[1].title == "Dynamics"
    assert len(subj.chapters[1].topics) == 1
    assert "Inertia" in subj.chapters[1].topics[0].subtopics
    assert parsed.total_chapters == 2
    assert parsed.total_topics == 3


@pytest.mark.asyncio
async def test_syllabus_parser_heuristic_numbered_modules():

    numbered_syllabus = (
        "Module 1: Operating Systems\n"
        "Chapter 1: Process Management\n"
        "1.1 Process Scheduling\n"
        "- Round Robin\n"
        "- Shortest Job First\n"
        "1.2 Synchronization\n"
        "- Semaphores\n"
        "- Deadlock conditions\n"
        "Module 2: Database Systems\n"
        "Chapter 1: Relational Model\n"
        "1.1 SQL Basics\n"
        "- SELECT queries\n"
        "- Joins and aggregations\n"
    )

    parsed = parse_heuristically(numbered_syllabus, default_title="CS Curriculum")

    assert len(parsed.subjects) == 2
    assert "Operating Systems" in parsed.subjects[0].title
    assert "Database Systems" in parsed.subjects[1].title
    assert len(parsed.subjects[0].chapters[0].topics) == 2
    assert "Deadlock conditions" in parsed.subjects[0].chapters[0].topics[1].subtopics


@pytest.mark.asyncio
async def test_syllabus_parser_empty_text():
    parser = SyllabusParser()
    parsed = await parser.parse_text("   ", default_title="Empty Course")
    assert parsed.title == "Empty Course"
    assert len(parsed.subjects) == 0
    assert parsed.total_topics == 0
    assert len(parsed.warnings) > 0
