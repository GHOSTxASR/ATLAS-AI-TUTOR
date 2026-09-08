from __future__ import annotations

import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    AnalyticsEvent,
    ChatMessage,
    ChatSession,
    Document,
    MemoryRecord,
    Note,
    Profile,
    QuizAttempt,
    Roadmap,
    RoadmapEdge,
    RoadmapNode,
)
from app.db.repositories.profile_repo import ProfileRepository
from app.exceptions import AtlasError
from app.schemas.profile import ProfileCreate, ProfileUpdate

#: Ceiling on what one import may write to disk, as a multiple of the
#: configured archive size limit -- so with the default 500MB limit, an import
#: may extract at most 5GB.
#:
#: Deliberately an absolute budget rather than a ratio against the individual
#: archive. Legitimate exports compress *extremely* well: a 1,300-node
#: roadmap's JSON shrinks 22x and plain-text documents 40x, so a ratio test
#: rejects exactly the most compressible real profiles while a bomb small
#: enough to stay under the ratio still slips through. Total bytes written is
#: the thing that actually threatens the disk, so that is what is bounded.
IMPORT_EXTRACTION_MULTIPLE = 10

#: Chunk size for copying a member out of the archive.
_EXTRACT_CHUNK_SIZE = 1024 * 1024

#: Prefix for export archives staged in the system temp directory.
_EXPORT_PREFIX = "atlas-export-"

#: How long a staged export may sit before it is assumed abandoned.
_STALE_EXPORT_SECONDS = 60 * 60


def _sweep_stale_exports() -> None:
    """Delete export archives left behind by downloads that never finished.

    The endpoint deletes its archive in a background task, but Starlette only
    runs those *after* the response is sent -- so a client that disconnects
    mid-download leaves the file behind. Rather than add a scheduled job for
    something this small, each export clears out anything older than an hour,
    which keeps the failure self-correcting.

    Never raises: an export must not fail because a stale file could not be
    removed (another process may still be sending it, and Windows will not
    unlink an open file).
    """
    cutoff = time.time() - _STALE_EXPORT_SECONDS
    try:
        candidates = Path(tempfile.gettempdir()).glob(f"{_EXPORT_PREFIX}*.zip")
        for stale in candidates:
            try:
                if stale.stat().st_mtime < cutoff:
                    stale.unlink(missing_ok=True)
            except OSError:
                continue
    except OSError:
        return


class ProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProfileRepository(session)

    async def get_all_profiles(self) -> Sequence[Profile]:
        return await self.repo.get_all()

    async def get_profile(self, profile_id: str) -> Profile:
        profile = await self.repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")
        return profile

    async def create_profile(self, data: ProfileCreate) -> Profile:
        profile = await self.repo.create(**data.model_dump())
        self._ensure_profile_directories(profile.id)
        return profile

    async def update_profile(self, profile_id: str, data: ProfileUpdate) -> Profile:
        profile = await self.get_profile(profile_id)
        update_data = data.model_dump(exclude_unset=True)
        return await self.repo.update(profile, **update_data)

    async def delete_profile(self, profile_id: str) -> None:
        deleted = await self.repo.delete(profile_id)
        if not deleted:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")
        self._cleanup_profile_directories(profile_id)
        # Drop all profile vector collections from ChromaDB
        from app.rag.vector_store import VectorStore

        vector_store = VectorStore()
        await vector_store.delete_all_profile_data(profile_id)

    async def export_profile(self, profile_id: str) -> Path:
        """Package a profile's data, documents and records into a ZIP on disk.

        Returns the path to a temporary file rather than bytes, so neither the
        archive nor a copy of it is held in memory. **The caller owns that
        file and must delete it** -- the export endpoint does so in a
        background task once the response has been sent.
        """
        profile = await self.get_profile(profile_id)

        # 1. Fetch domain records
        chats_q = await self.session.execute(select(ChatSession).where(ChatSession.profile_id == profile_id))
        chats = chats_q.scalars().all()
        chat_ids = [c.id for c in chats]

        msgs_q = await self.session.execute(select(ChatMessage).where(ChatMessage.session_id.in_(chat_ids))) if chat_ids else None
        msgs = msgs_q.scalars().all() if msgs_q else []

        roadmaps_q = await self.session.execute(select(Roadmap).where(Roadmap.profile_id == profile_id))
        roadmaps = roadmaps_q.scalars().all()
        roadmap_ids = [r.id for r in roadmaps]

        nodes_q = await self.session.execute(select(RoadmapNode).where(RoadmapNode.roadmap_id.in_(roadmap_ids))) if roadmap_ids else None
        nodes = nodes_q.scalars().all() if nodes_q else []

        edges_q = await self.session.execute(select(RoadmapEdge).where(RoadmapEdge.roadmap_id.in_(roadmap_ids))) if roadmap_ids else None
        edges = edges_q.scalars().all() if edges_q else []

        mems_q = await self.session.execute(select(MemoryRecord).where(MemoryRecord.profile_id == profile_id))
        memories = mems_q.scalars().all()

        notes_q = await self.session.execute(select(Note).where(Note.profile_id == profile_id))
        notes = notes_q.scalars().all()

        quizzes_q = await self.session.execute(select(QuizAttempt).where(QuizAttempt.profile_id == profile_id))
        quizzes = quizzes_q.scalars().all()

        events_q = await self.session.execute(select(AnalyticsEvent).where(AnalyticsEvent.profile_id == profile_id))
        events = events_q.scalars().all()

        documents_q = await self.session.execute(select(Document).where(Document.profile_id == profile_id))
        documents = documents_q.scalars().all()

        # 2. Assemble ZIP on disk rather than in memory. Held in a BytesIO,
        #    the whole archive was resident and `getvalue()` then copied it,
        #    so exporting peaked at roughly twice the archive size -- the
        #    mirror of the problem the import side had.
        _sweep_stale_exports()
        fd, temp_name = tempfile.mkstemp(prefix=_EXPORT_PREFIX, suffix=".zip")
        os.close(fd)
        archive_path = Path(temp_name)

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "profile.json",
                json.dumps(
                    {
                        "id": profile.id,
                        "name": profile.name,
                        "profile_type": profile.profile_type,
                        "created_at": profile.created_at.isoformat() if hasattr(profile.created_at, "isoformat") else str(profile.created_at),
                        "updated_at": profile.updated_at.isoformat() if hasattr(profile.updated_at, "isoformat") else str(profile.updated_at),
                    },
                    indent=2,
                ),
            )
            zf.writestr("manifest.json", json.dumps({"version": 2}, indent=2))
            zf.writestr(
                "chats.json",
                json.dumps(
                    [
                        {
                            "id": c.id,
                            "title": c.title,
                            "messages": [
                                {"id": m.id, "role": m.role, "content": m.content, "created_at": str(m.created_at)}
                                for m in msgs
                                if m.session_id == c.id
                            ],
                        }
                        for c in chats
                    ],
                    indent=2,
                ),
            )
            zf.writestr(
                "roadmaps.json",
                json.dumps(
                    [
                        {
                            "id": r.id,
                            "title": r.title,
                            "mode": r.mode,
                            "version": r.version,
                            "is_active": r.is_active,
                            "source_document_id": r.source_document_id,
                            "nodes": [
                                {
                                    "id": n.id,
                                    "title": n.title,
                                    "description": n.description,
                                    "node_type": n.node_type,
                                    "status": n.status,
                                    "mastery_score": n.mastery_score,
                                    "order_index": n.order_index,
                                    "time_spent_minutes": n.time_spent_minutes,
                                    "ai_generated": n.ai_generated,
                                    "completed_at": str(n.completed_at) if n.completed_at else None,
                                }
                                for n in nodes
                                if n.roadmap_id == r.id
                            ],
                            "edges": [
                                {"id": e.id, "from_node_id": e.from_node_id, "to_node_id": e.to_node_id, "edge_type": e.edge_type}
                                for e in edges
                                if e.roadmap_id == r.id
                            ],
                        }
                        for r in roadmaps
                    ],
                    indent=2,
                ),
            )
            zf.writestr(
                "memories.json",
                json.dumps(
                    [
                        {"id": m.id, "category": m.category, "subject": getattr(m, "subject", ""), "content": m.content, "confidence": m.confidence, "source": m.source, "source_id": m.source_id, "is_active": m.is_active}
                        for m in memories
                    ],
                    indent=2,
                ),
            )
            zf.writestr(
                "notes.json",
                json.dumps(
                    [{"id": n.id, "title": n.title, "content": n.content, "note_type": getattr(n, "note_type", "study_note"), "roadmap_node_id": n.roadmap_node_id, "source": n.source, "tags_json": n.tags_json} for n in notes],
                    indent=2,
                ),
            )
            zf.writestr(
                "quiz_attempts.json",
                json.dumps(
                    [{
                        "id": q.id,
                        "roadmap_node_id": q.roadmap_node_id,
                        "mode": q.mode,
                        "started_at": str(q.started_at),
                        "completed_at": str(q.completed_at) if q.completed_at else None,
                        "score": q.score,
                        "total_questions": q.total_questions,
                        "correct_count": q.correct_count,
                        "time_limit_seconds": q.time_limit_seconds,
                        "questions_json": q.questions_json,
                    } for q in quizzes],
                    indent=2,
                ),
            )
            zf.writestr(
                "analytics_events.json",
                json.dumps(
                    [{"id": e.id, "event_type": e.event_type, "entity_type": e.entity_type, "entity_id": e.entity_id, "value": e.value, "metadata_json": e.metadata_json, "occurred_at": str(e.occurred_at)} for e in events],
                    indent=2,
                ),
            )
            zf.writestr(
                "documents.json",
                json.dumps(
                    [{
                        "id": d.id,
                        "filename": d.filename,
                        "file_path": d.file_path,
                        "storage_rel_path": str(
                            (get_settings().paths.data_dir / d.file_path).relative_to(self._profile_dir(profile_id))
                        ),
                        "extracted_rel_path": str(
                            (get_settings().paths.data_dir / d.extracted_text_path).relative_to(self._profile_dir(profile_id))
                        ) if d.extracted_text_path else None,
                        "file_type": d.file_type,
                        "content_hash": d.content_hash,
                        "status": d.status,
                        "page_count": d.page_count,
                        "chunk_count": d.chunk_count,
                        "word_count": d.word_count,
                        "indexed_at": str(d.indexed_at) if d.indexed_at else None,
                        "error_message": d.error_message,
                        "is_syllabus": d.is_syllabus,
                        "roadmap_node_id": d.roadmap_node_id,
                    } for d in documents],
                    indent=2,
                ),
            )

            # Include raw and extracted document files
            p_dir = self._profile_dir(profile_id)
            if p_dir.exists():
                for f in p_dir.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(p_dir)
                        zf.write(f, arcname=f"files/{rel}")

        return archive_path

    async def import_profile(self, archive: Path) -> Profile:
        """Restore profile, data files, and database records from an exported ZIP.

        Takes a path rather than bytes so the archive is read from disk. A
        profile export is every document a profile owns, so holding the whole
        thing in memory made the upload limit a memory limit; now nothing
        larger than one chunk is resident at a time.
        """
        try:
            zip_handle = zipfile.ZipFile(archive, "r")
        except zipfile.BadZipFile as exc:
            # Previously escaped as an unhandled error, so picking the wrong
            # file in the file dialog produced a 500 rather than a sentence
            # telling you what was wrong.
            raise AtlasError(
                status_code=422,
                code="INVALID_ZIP",
                message="That file is not a valid ZIP archive.",
            ) from exc

        with zip_handle as zf:
            members = zf.namelist()
            if "profile.json" not in members:
                raise AtlasError(status_code=422, code="INVALID_ZIP", message="ZIP missing profile.json")

            # Validate archive paths before creating a profile or writing files.
            archive_root = Path("profile").resolve()
            for member in members:
                if not member.startswith("files/") or member.endswith("/"):
                    continue
                relative_path = member[len("files/") :]
                if not (archive_root / relative_path).resolve().is_relative_to(archive_root):
                    raise AtlasError(
                        status_code=422,
                        code="INVALID_ZIP",
                        message="ZIP contains a file outside the profile directory",
                    )

            # Refuse a decompression bomb before anything is created or
            # written. Bounding memory moved the risk to disk: a 48KB archive
            # can declare 48MB of contents, and the same trick scales to
            # filling the drive. Declared sizes come from the archive
            # directory, so this costs nothing to read.
            settings = get_settings()
            extraction_budget = (
                settings.ingestion.max_import_size_mb * 1024 * 1024 * IMPORT_EXTRACTION_MULTIPLE
            )
            declared = sum(info.file_size for info in zf.infolist())
            if declared > extraction_budget:
                raise AtlasError(
                    status_code=422,
                    code="INVALID_ZIP",
                    message=(
                        f"This archive expands to {declared // (1024 * 1024)}MB, beyond "
                        f"the {extraction_budget // (1024 * 1024)}MB an import may write."
                    ),
                    details={
                        "declared_bytes": declared,
                        "extraction_budget_bytes": extraction_budget,
                    },
                )

            profile_data = json.loads(zf.read("profile.json").decode("utf-8"))
            name = profile_data.get("name", "Imported Profile")
            p_type = profile_data.get("profile_type", "General")

            # Create new profile in database
            profile = await self.create_profile(ProfileCreate(name=name, profile_type=p_type))

            # Restore files
            p_dir = self._profile_dir(profile.id)
            extracted = 0
            for member in members:
                if member.startswith("files/") and not member.endswith("/"):
                    rel_path = member[len("files/") :]
                    out_path = (p_dir / rel_path).resolve()
                    if not out_path.is_relative_to(p_dir.resolve()):
                        raise AtlasError(
                            status_code=422,
                            code="INVALID_ZIP",
                            message="ZIP contains a file outside the profile directory",
                        )
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    # Copied in chunks rather than `zf.read(member)`, which
                    # would hold an entire document in memory. The running
                    # total is the backstop for an archive whose declared
                    # sizes were a lie -- the check above trusts the
                    # directory, this one trusts only what actually arrives.
                    with zf.open(member) as source, out_path.open("wb") as target:
                        while chunk := source.read(_EXTRACT_CHUNK_SIZE):
                            extracted += len(chunk)
                            if extracted > extraction_budget:
                                raise AtlasError(
                                    status_code=422,
                                    code="INVALID_ZIP",
                                    message=(
                                        "This archive expanded to far more than its "
                                        "size suggested and was refused."
                                    ),
                                )
                            target.write(chunk)

            roadmap_id_map: dict[str, str] = {}
            node_id_map: dict[str, str] = {}
            if "roadmaps.json" in members:
                roadmap_list = json.loads(zf.read("roadmaps.json").decode("utf-8"))
                for data in roadmap_list:
                    roadmap = Roadmap(
                        profile_id=profile.id,
                        title=data.get("title", "Imported Roadmap"),
                        mode=data.get("mode", "strict"),
                        version=data.get("version", 1),
                        is_active=data.get("is_active", True),
                    )
                    self.session.add(roadmap)
                    await self.session.flush()
                    roadmap_id_map[data.get("id", "")] = roadmap.id

                    for node_data in data.get("nodes", []):
                        node = RoadmapNode(
                            roadmap_id=roadmap.id,
                            profile_id=profile.id,
                            title=node_data.get("title", "Imported Topic"),
                            description=node_data.get("description"),
                            node_type=node_data.get("node_type", "topic"),
                            status=node_data.get("status", "not_started"),
                            order_index=node_data.get("order_index", 1),
                            mastery_score=node_data.get("mastery_score", 0.0),
                            time_spent_minutes=node_data.get("time_spent_minutes", 0),
                            ai_generated=node_data.get("ai_generated", False),
                        )
                        self.session.add(node)
                        await self.session.flush()
                        node_id_map[node_data.get("id", "")] = node.id

                    for edge_data in data.get("edges", []):
                        from_node_id = node_id_map.get(edge_data.get("from_node_id", ""))
                        to_node_id = node_id_map.get(edge_data.get("to_node_id", ""))
                        if from_node_id and to_node_id:
                            self.session.add(
                                RoadmapEdge(
                                    roadmap_id=roadmap.id,
                                    from_node_id=from_node_id,
                                    to_node_id=to_node_id,
                                    edge_type=edge_data.get("edge_type", "sequential"),
                                )
                            )

            if "documents.json" in members:
                document_list = json.loads(zf.read("documents.json").decode("utf-8"))
                for data in document_list:
                    storage_rel_path = data.get("storage_rel_path")
                    if not storage_rel_path:
                        continue
                    document_path = p_dir / storage_rel_path
                    extracted_rel_path = data.get("extracted_rel_path")
                    document = Document(
                        profile_id=profile.id,
                        filename=data.get("filename", "Imported document"),
                        file_path=str(document_path.relative_to(get_settings().paths.data_dir)),
                        extracted_text_path=(
                            str((p_dir / extracted_rel_path).relative_to(get_settings().paths.data_dir))
                            if extracted_rel_path
                            else None
                        ),
                        file_type=data.get("file_type", "txt"),
                        content_hash=data.get("content_hash", ""),
                        # Vectors are not part of the archive and the new
                        # profile has its own collections, so the document must
                        # be re-indexed. Importing it as "indexed" left the
                        # content permanently unsearchable.
                        status="pending",
                        page_count=data.get("page_count"),
                        chunk_count=0,
                        word_count=data.get("word_count"),
                        indexed_at=None,
                        error_message=data.get("error_message"),
                        is_syllabus=data.get("is_syllabus", False),
                        roadmap_node_id=node_id_map.get(data.get("roadmap_node_id", "")),
                    )
                    self.session.add(document)

            if "chats.json" in members:
                chat_list = json.loads(zf.read("chats.json").decode("utf-8"))
                for data in chat_list:
                    chat = ChatSession(profile_id=profile.id, title=data.get("title", "Imported Chat"))
                    self.session.add(chat)
                    await self.session.flush()
                    for message_data in data.get("messages", []):
                        self.session.add(
                            ChatMessage(
                                session_id=chat.id,
                                role=message_data.get("role", "user"),
                                content=message_data.get("content", ""),
                            )
                        )

            # Restore memories if present
            if "memories.json" in members:
                mem_list = json.loads(zf.read("memories.json").decode("utf-8"))
                for m in mem_list:
                    rec = MemoryRecord(
                        profile_id=profile.id,
                        category=m.get("category", "fact"),
                        subject=m.get("subject", ""),
                        content=m.get("content", ""),
                        confidence=m.get("confidence", 0.8),
                        source=m.get("source", "import"),
                        source_id=m.get("source_id"),
                        is_active=m.get("is_active", True),
                    )
                    self.session.add(rec)

            # Restore notes if present
            if "notes.json" in members:
                notes_list = json.loads(zf.read("notes.json").decode("utf-8"))
                for n in notes_list:
                    note = Note(
                        profile_id=profile.id,
                        roadmap_node_id=node_id_map.get(n.get("roadmap_node_id", "")),
                        title=n.get("title", "Imported Note"),
                        content=n.get("content", ""),
                        note_type=n.get("note_type", "lesson_note"),
                        source=n.get("source", "import"),
                        tags_json=n.get("tags_json"),
                    )
                    self.session.add(note)

            if "quiz_attempts.json" in members:
                quiz_list = json.loads(zf.read("quiz_attempts.json").decode("utf-8"))
                for data in quiz_list:
                    self.session.add(
                        QuizAttempt(
                            profile_id=profile.id,
                            roadmap_node_id=node_id_map.get(data.get("roadmap_node_id", "")),
                            mode=data.get("mode", "practice"),
                            score=data.get("score"),
                            total_questions=data.get("total_questions", 0),
                            correct_count=data.get("correct_count"),
                            time_limit_seconds=data.get("time_limit_seconds"),
                            questions_json=data.get("questions_json", "[]"),
                        )
                    )

            if "analytics_events.json" in members:
                event_list = json.loads(zf.read("analytics_events.json").decode("utf-8"))
                for data in event_list:
                    self.session.add(
                        AnalyticsEvent(
                            profile_id=profile.id,
                            event_type=data.get("event_type", "imported"),
                            entity_type=data.get("entity_type", "roadmap_node"),
                            entity_id=data.get("entity_id"),
                            value=data.get("value"),
                            metadata_json=data.get("metadata_json"),
                        )
                    )

            await self.session.commit()
            return profile

    @staticmethod
    def _profile_dir(profile_id: str) -> Path:
        return get_settings().paths.profiles_dir / profile_id

    def _ensure_profile_directories(self, profile_id: str) -> None:
        base = self._profile_dir(profile_id)
        (base / "documents" / "raw").mkdir(parents=True, exist_ok=True)
        (base / "documents" / "extracted").mkdir(parents=True, exist_ok=True)

    def _cleanup_profile_directories(self, profile_id: str) -> None:
        import shutil

        base = self._profile_dir(profile_id)
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
