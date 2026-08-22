from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedTopic(BaseModel):
    """A topic within a syllabus chapter, potentially containing subtopics."""

    title: str = Field(..., min_length=1, description="Topic title")
    description: str = Field("", description="Topic overview or summary")
    subtopics: list[str] = Field(default_factory=list, description="Granular subtopics or concepts")
    order_index: int = Field(1, ge=1, description="Sequential order within chapter")
    estimated_hours: float | None = Field(None, ge=0.0, description="Estimated study duration in hours")
    learning_objectives: list[str] = Field(default_factory=list, description="Key learning objectives")


class ParsedChapter(BaseModel):
    """A chapter or unit within a subject."""

    title: str = Field(..., min_length=1, description="Chapter or unit title")
    description: str = Field("", description="Chapter description")
    topics: list[ParsedTopic] = Field(default_factory=list, description="Topics within this chapter")
    order_index: int = Field(1, ge=1, description="Sequential order within subject")


class ParsedSubject(BaseModel):
    """A high-level subject or module in the curriculum."""

    title: str = Field(..., min_length=1, description="Subject or module title")
    description: str = Field("", description="Subject overview")
    chapters: list[ParsedChapter] = Field(default_factory=list, description="Chapters within this subject")
    order_index: int = Field(1, ge=1, description="Sequential order in syllabus")


class ParsedSyllabus(BaseModel):
    """Complete hierarchical syllabus structure."""

    title: str = Field(..., min_length=1, description="Syllabus curriculum title")
    description: str = Field("", description="Curriculum description or target exam")
    subjects: list[ParsedSubject] = Field(default_factory=list, description="Subjects/Modules")
    total_chapters: int = Field(0, ge=0, description="Total count of chapters across all subjects")
    total_topics: int = Field(0, ge=0, description="Total count of topics across all chapters")
    warnings: list[str] = Field(default_factory=list, description="Parser warnings or notes")


class SyllabusParseRequest(BaseModel):
    """Request payload for direct text syllabus parsing."""

    text: str = Field(..., min_length=1, description="Raw syllabus text to parse")
    title: str | None = Field("Uploaded Syllabus", description="Optional syllabus title")
