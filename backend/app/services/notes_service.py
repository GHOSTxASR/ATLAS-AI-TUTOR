from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.notes_repo import NotesRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import AtlasError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.models.resilience import provider_error_from
from app.pipelines.embedder import DocumentEmbedder
from app.rag.vector_store import VectorStore
from app.schemas.notes import (
    NoteCreate,
    NoteGenerateRequest,
    NoteResponse,
    NoteSummary,
    NoteUpdate,
)
from app.services.unified_context_service import UnifiedContextService

logger = logging.getLogger(__name__)

# Reading a freshly generated note is roughly this much study time. A flat
# estimate is used because the backend cannot observe how long it is read for.
NOTE_GENERATION_STUDY_MINUTES = 3.0


def _format_tags(tags_json: str | None) -> list[str]:
    if not tags_json:
        return []
    try:
        parsed = json.loads(tags_json)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


class NotesService:
    """Orchestrates automatic note generation (Lesson Notes, Revision Notes, Cheat Sheets, Summaries) and persistence."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = NotesRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.roadmap_repo = RoadmapRepository(session)
        self.graph_repo = GraphRepository(settings=self.settings)
        self.context_service = UnifiedContextService(session=session, settings=self.settings)
        self.embedder = DocumentEmbedder(settings=self.settings)
        self.vector_store = VectorStore(settings=self.settings)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def generate_note(
        self, profile_id: str, request: NoteGenerateRequest
    ) -> NoteResponse:
        """Generate structured study note using AI grounded in unified context."""
        await self._require_profile(profile_id)

        # 1. Determine Topic Title
        topic = request.topic_title or "General Academic Concepts"
        if request.roadmap_node_id:
            node = await self.roadmap_repo.get_node(request.roadmap_node_id)
            if not node or node.profile_id != profile_id:
                raise AtlasError(status_code=404, code="NOT_FOUND", message="Roadmap node not found")
            topic = node.title

        # 2. Assemble 5-Pillar Unified Context
        unified_ctx = await self.context_service.build_unified_context(
            profile_id=profile_id,
            query=topic,
            mode="teaching" if request.note_type == "lesson_note" else "revision",
            roadmap_node_id=request.roadmap_node_id,
            document_ids=request.document_ids,
        )

        # 3. Construct Note Modality Prompt
        type_instructions = {
            "lesson_note": (
                "Format: Comprehensive Lesson Note in rich GitHub-flavored Markdown.\n"
                "Sections:\n"
                "# Title\n"
                "## 1. Executive Conceptual Foundation\n"
                "## 2. Intuitive Mental Model & Real-World Analogy\n"
                "## 3. Mathematical & Algorithmic Principles (with formulas/code blocks)\n"
                "## 4. Worked Step-by-Step Problem/Proof\n"
                "## 5. Summary & Key Takeaways"
            ),
            "revision_note": (
                "Format: High-Yield Revision Note in concise Markdown.\n"
                "Sections:\n"
                "# Title\n"
                "## ⚡ Core Definitions\n"
                "## 📐 Essential Formulas & Invariants (Markdown Table)\n"
                "## ⚠️ Critical Exam Pitfalls & Memory Aids"
            ),
            "cheat_sheet": (
                "Format: Dense Quick-Reference Cheat Sheet.\n"
                "Sections:\n"
                "# Title\n"
                "## 📊 Quick Reference Table (Complexity/Operations)\n"
                "## 🛠️ Key Code Snippets & Syntax Patterns\n"
                "## 🔑 Core Invariant Rules"
            ),
            "summary": (
                "Format: Ultra-Concise Executive Summary (TL;DR).\n"
                "Sections:\n"
                "# Title\n"
                "3-5 high-density bullet points capturing the core axiom, formula, and fundamental takeaway."
            ),
        }

        user_prompt = (
            f"Generate a professional study note for the topic: '{topic}'.\n"
            f"Note Modality: '{request.note_type}'.\n"
            f"{type_instructions.get(request.note_type, '')}\n\n"
            f"Custom Guidance: {request.custom_instructions or 'Ensure maximum academic clarity.'}\n\n"
            f"Ground your notes in this unified learner context:\n{unified_ctx.system_prompt}"
        )

        # 4. Generate Content via LLM
        note_content = ""
        try:
            client = get_model_client(self.settings)
            try:
                resp = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You create world-class academic study notes in markdown."),
                        ChatMessage(role="user", content=user_prompt),
                    ],
                    temperature=0.2,
                    max_tokens=3000,
                )
                note_content = resp.content.strip()
            finally:
                await client.close()
        except ValueError as e:
            raise AtlasError(
                status_code=503, code="PROVIDER_NOT_CONFIGURED", message=str(e)
            ) from None
        except Exception as e:
            # Same reasoning as the tutor and quiz paths: a saved note full of
            # generic filler ("T(n) = a*T(n/b) + f(n)" for any topic) is worse
            # than no note, because the learner revises from it later.
            error = provider_error_from(e)
            logger.warning("Note generation failed: %s", error.message)
            raise AtlasError(
                status_code=502, code="PROVIDER_ERROR", message=error.message
            ) from None

        if not note_content:
            raise AtlasError(
                status_code=502,
                code="PROVIDER_EMPTY_RESPONSE",
                message="The AI provider returned an empty note. Try again.",
            )

        # 5. Persist Note in Database
        title = f"{request.note_type.replace('_', ' ').title()}: {topic}"
        tags = [request.note_type, topic.lower().replace(" ", "-")]

        note = await self.repo.create(
            profile_id=profile_id,
            title=title,
            content=note_content,
            note_type=request.note_type,
            source="ai_generated",
            roadmap_node_id=request.roadmap_node_id,
            tags=tags,
        )

        # 5b. Record study time so generated notes show up in analytics.
        try:
            await AnalyticsRepository(self.session).log_event(
                profile_id=profile_id,
                event_type="note_generated",
                entity_type="note",
                entity_id=note.id,
                value=NOTE_GENERATION_STUDY_MINUTES,
                metadata_json=json.dumps({"note_type": request.note_type, "topic": topic}),
            )
        except Exception as e:
            logger.warning("Could not record note_generated analytics event: %s", e)

        # 6. Index Note into ChromaDB Vector Store for RAG
        try:
            await self.vector_store.index_note(
                profile_id=profile_id,
                note_id=note.id,
                title=note.title,
                text=note_content,
                tags=",".join(tags),
                roadmap_node_id=note.roadmap_node_id,
            )
        except Exception as e:
            logger.warning(f"Failed to vector-index note: {e}")

        # 7. Link to Knowledge Graph
        try:
            note_graph_node = await self.graph_repo.add_node(
                profile_id=profile_id,
                label=note.title,
                node_type="note",
                description=f"Generated {request.note_type.replace('_', ' ')}",
                node_id=note.id,
            )
            if unified_ctx.graph.matched_concept:
                matched_id = None
                g = await self.graph_repo.get_graph(profile_id)
                for nid, attrs in g.nodes(data=True):
                    if attrs.get("label") == unified_ctx.graph.matched_concept:
                        matched_id = nid
                        break
                if matched_id:
                    await self.graph_repo.add_edge(
                        profile_id=profile_id,
                        source=matched_id,
                        target=note_graph_node["id"],
                        edge_type="referenced_by",
                    )
        except Exception as e:
            logger.warning(f"Failed to link note to knowledge graph: {e}")

        return NoteResponse(
            id=note.id,
            profile_id=profile_id,
            roadmap_node_id=note.roadmap_node_id,
            title=note.title,
            content=note.content,
            note_type=note.note_type,  # type: ignore
            source=note.source,  # type: ignore
            tags=_format_tags(note.tags_json),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    async def create_user_note(self, profile_id: str, data: NoteCreate) -> NoteResponse:
        """Create manual note authored by user."""
        await self._require_profile(profile_id)
        note = await self.repo.create(
            profile_id=profile_id,
            title=data.title,
            content=data.content,
            note_type=data.note_type,
            source="user_written",
            roadmap_node_id=data.roadmap_node_id,
            tags=data.tags,
        )
        return NoteResponse(
            id=note.id,
            profile_id=profile_id,
            roadmap_node_id=note.roadmap_node_id,
            title=note.title,
            content=note.content,
            note_type=note.note_type,  # type: ignore
            source=note.source,  # type: ignore
            tags=_format_tags(note.tags_json),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    async def list_notes(
        self,
        profile_id: str,
        note_type: str | None = None,
        roadmap_node_id: str | None = None,
        query: str | None = None,
    ) -> list[NoteSummary]:
        """List notes with optional filters."""
        await self._require_profile(profile_id)
        notes = await self.repo.list_by_profile(
            profile_id=profile_id,
            note_type=note_type,
            roadmap_node_id=roadmap_node_id,
            query=query,
        )
        return [
            NoteSummary(
                id=n.id,
                profile_id=n.profile_id,
                roadmap_node_id=n.roadmap_node_id,
                title=n.title,
                note_type=n.note_type,  # type: ignore
                source=n.source,  # type: ignore
                tags=_format_tags(n.tags_json),
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in notes
        ]

    async def get_note(self, profile_id: str, note_id: str) -> NoteResponse:
        """Get single note by ID."""
        await self._require_profile(profile_id)
        note = await self.repo.get_by_id(note_id)
        if not note or note.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Note not found")
        return NoteResponse(
            id=note.id,
            profile_id=note.profile_id,
            roadmap_node_id=note.roadmap_node_id,
            title=note.title,
            content=note.content,
            note_type=note.note_type,  # type: ignore
            source=note.source,  # type: ignore
            tags=_format_tags(note.tags_json),
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    async def update_note(
        self, profile_id: str, note_id: str, data: NoteUpdate
    ) -> NoteResponse:
        """Update existing note title or content."""
        await self._require_profile(profile_id)
        note = await self.repo.get_by_id(note_id)
        if not note or note.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Note not found")

        fields = data.model_dump(exclude_unset=True)
        updated = await self.repo.update(note, **fields)

        # Keep what the tutor can retrieve in step with what the note now
        # says. Only creation indexed a note, so an edited note stayed
        # searchable by its original wording -- corrections included.
        if {"title", "content"} & set(fields):
            try:
                await self.vector_store.index_note(
                    profile_id=profile_id,
                    note_id=updated.id,
                    title=updated.title,
                    text=updated.content,
                    tags=",".join(_format_tags(updated.tags_json)),
                    roadmap_node_id=updated.roadmap_node_id,
                )
            except Exception as e:
                logger.warning("Could not re-index edited note %s: %s", updated.id, e)

        return NoteResponse(
            id=updated.id,
            profile_id=updated.profile_id,
            roadmap_node_id=updated.roadmap_node_id,
            title=updated.title,
            content=updated.content,
            note_type=updated.note_type,  # type: ignore
            source=updated.source,  # type: ignore
            tags=_format_tags(updated.tags_json),
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    async def delete_note(self, profile_id: str, note_id: str) -> bool:
        """Delete note."""
        await self._require_profile(profile_id)
        note = await self.repo.get_by_id(note_id)
        if not note or note.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Note not found")

        # Drop the vector first: a note deleted from the database but left in
        # the index went on being quoted back to the learner as a source, with
        # nothing behind the citation.
        try:
            await self.vector_store.delete_by_note_id(profile_id=profile_id, note_id=note.id)
        except Exception as e:
            logger.warning("Could not remove note %s from the vector index: %s", note.id, e)

        await self.repo.delete(note)
        return True
