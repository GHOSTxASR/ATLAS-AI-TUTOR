from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.pipelines.document_extractor import DocumentExtractor
from app.pipelines.syllabus_parser import SyllabusParser
from app.schemas.syllabus import ParsedSyllabus
from app.services.document_text import load_document_text

logger = logging.getLogger(__name__)


class SyllabusService:
    """Service orchestrating syllabus hierarchy extraction from uploaded documents and text."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.doc_repo = DocumentRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.parser = SyllabusParser(settings=self.settings)
        self.extractor = DocumentExtractor()

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def parse_document_syllabus(self, profile_id: str, document_id: str) -> ParsedSyllabus:
        """Extract structured syllabus from an uploaded document."""
        await self._require_profile(profile_id)

        document, text = await load_document_text(
            self.session,
            self.settings,
            profile_id,
            document_id,
            extractor=self.extractor,
        )

        title = Path(document.filename).stem.replace("_", " ").title()
        return await self.parser.parse_text(text=text, default_title=title)

    async def synthesize_from_documents(
        self, profile_id: str, document_ids: list[str]
    ) -> ParsedSyllabus:
        """Write a syllabus from uploaded materials when none was provided.

        Documents that yield no text are skipped rather than failing the whole
        request: one unreadable scan among six should not cost the roadmap.
        """
        await self._require_profile(profile_id)

        sources: list[tuple[str, str]] = []
        for document_id in document_ids:
            try:
                document, text = await load_document_text(
                    self.session, self.settings, profile_id, document_id, extractor=self.extractor
                )
                sources.append((document.filename, text))
            except AtlasError as e:
                logger.warning("Skipping document %s while writing a syllabus: %s", document_id, e)

        if not sources:
            raise AtlasError(
                status_code=422,
                code="EXTRACTION_EMPTY",
                message="None of the selected documents had any readable text.",
            )

        syllabus = await self.parser.synthesize_from_materials(sources)
        if syllabus is None:
            raise AtlasError(
                status_code=422,
                code="SYLLABUS_SYNTHESIS_FAILED",
                message=(
                    "Could not work out a curriculum from these materials. "
                    "Upload a syllabus and mark it as one, or try again."
                ),
            )
        return syllabus

    async def parse_raw_text(self, text: str, title: str = "Uploaded Syllabus") -> ParsedSyllabus:
        """Parse raw text string into a structured syllabus."""
        return await self.parser.parse_text(text=text, default_title=title)
