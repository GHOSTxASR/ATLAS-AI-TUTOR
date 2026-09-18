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

    async def parse_raw_text(self, text: str, title: str = "Uploaded Syllabus") -> ParsedSyllabus:
        """Parse raw text string into a structured syllabus."""
        return await self.parser.parse_text(text=text, default_title=title)
