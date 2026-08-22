from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import ChatMessage, ChatSession
from app.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.notes_repo import NotesRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import LearningOSError
from app.rag.vector_store import VectorStore
from app.schemas.search import (
    GlobalSearchRequest,
    GlobalSearchResponse,
    GlobalSearchResultItem,
)

logger = logging.getLogger(__name__)


class GlobalSearchService:
    """Orchestrates unified global search across Chats, Notes, Documents, Knowledge Graph, and Roadmap."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.profile_repo = ProfileRepository(session)
        self.chat_session_repo = ChatSessionRepository(session)
        self.chat_msg_repo = ChatMessageRepository(session)
        self.notes_repo = NotesRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.roadmap_repo = RoadmapRepository(session)
        self.graph_repo = GraphRepository(settings=self.settings)
        self.vector_store = VectorStore(settings=self.settings)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def global_search(
        self, profile_id: str, request: GlobalSearchRequest
    ) -> GlobalSearchResponse:
        """Search across all 5 pillars and aggregate categorized results."""
        await self._require_profile(profile_id)
        q = request.query.strip().lower()
        limit = request.limit_per_category
        categories = request.categories or ["chats", "notes", "documents", "graph", "roadmap"]

        chat_results: list[GlobalSearchResultItem] = []
        note_results: list[GlobalSearchResultItem] = []
        doc_results: list[GlobalSearchResultItem] = []
        graph_results: list[GlobalSearchResultItem] = []
        roadmap_results: list[GlobalSearchResultItem] = []

        # 1. CHATS SEARCH
        if "chats" in categories:
            try:
                # Search sessions by title
                sessions = await self.chat_session_repo.search(profile_id, q)
                for s in sessions[:limit]:
                    chat_results.append(
                        GlobalSearchResultItem(
                            id=s.id,
                            title=s.title,
                            subtitle="Chat Conversation",
                            snippet=f"Session created on {s.created_at.strftime('%Y-%m-%d')}",
                            category="chats",
                            url_path=f"/chat/{s.id}",
                            score=1.0,
                            metadata={"session_id": s.id, "created_at": s.created_at.isoformat()},
                        )
                    )

                # Search messages by content
                msg_stmt = (
                    select(ChatMessage, ChatSession.title.label("session_title"))
                    .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                    .where(ChatSession.profile_id == profile_id)
                    .where(func.lower(ChatMessage.content).like(f"%{q}%"))
                    .order_by(ChatMessage.created_at.desc())
                    .limit(limit)
                )
                msg_res = await self.session.execute(msg_stmt)
                for msg, session_title in msg_res.all():
                    if len(chat_results) >= limit:
                        break
                    # Highlight snippet around match
                    content = msg.content
                    idx = content.lower().find(q)
                    start = max(0, idx - 40)
                    end = min(len(content), idx + 80)
                    snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")

                    chat_results.append(
                        GlobalSearchResultItem(
                            id=msg.id,
                            title=f"Message in '{session_title}'",
                            subtitle=f"Role: {msg.role.title()}",
                            snippet=snippet,
                            category="chats",
                            url_path=f"/chat/{msg.session_id}",
                            score=0.9,
                            metadata={"session_id": msg.session_id, "role": msg.role},
                        )
                    )
            except Exception as e:
                logger.warning(f"Global search in chats failed: {e}")

        # 2. NOTES SEARCH
        if "notes" in categories:
            try:
                notes = await self.notes_repo.list_by_profile(profile_id=profile_id, query=q)
                seen_note_ids = set()
                for n in notes[:limit]:
                    seen_note_ids.add(n.id)
                    snippet = n.content[:150] + ("..." if len(n.content) > 150 else "")
                    note_results.append(
                        GlobalSearchResultItem(
                            id=n.id,
                            title=n.title,
                            subtitle=f"{n.note_type.replace('_', ' ').title()} • {n.source.replace('_', ' ').title()}",
                            snippet=snippet,
                            category="notes",
                            url_path=f"/notes?note_id={n.id}",
                            score=1.0,
                            metadata={"note_type": n.note_type, "source": n.source},
                        )
                    )

                # Optional semantic search in notes vector collection
                if request.include_semantic and len(note_results) < limit:
                    vec_matches = await self.vector_store.query_notes(
                        profile_id=profile_id,
                        query=q,
                        top_k=limit - len(note_results),
                    )
                    for vm in vec_matches:
                        if vm.score < 0.6:
                            continue
                        note_id = vm.metadata.get("note_id") or vm.source_id
                        if note_id and note_id not in seen_note_ids:
                            seen_note_ids.add(note_id)
                            note_results.append(
                                GlobalSearchResultItem(
                                    id=note_id,
                                    title=vm.metadata.get("title", "Study Note"),
                                    subtitle="Semantic Match • Note Content",
                                    snippet=(vm.text or "")[:150],
                                    category="notes",
                                    url_path=f"/notes?note_id={note_id}",
                                    score=vm.score,
                                    metadata=vm.metadata,
                                )
                            )
            except Exception as e:
                logger.warning(f"Global search in notes failed: {e}")

        # 3. DOCUMENTS SEARCH
        if "documents" in categories:
            try:
                docs = await self.doc_repo.list_by_profile(profile_id=profile_id)
                seen_doc_ids = set()
                for d in docs:
                    if q in d.filename.lower():
                        seen_doc_ids.add(d.id)
                        doc_results.append(
                            GlobalSearchResultItem(
                                id=d.id,
                                title=d.filename,
                                subtitle=f"{d.file_type.upper()} Document • Status: {d.status}",
                                snippet=f"File: {d.filename} (Status: {d.status})",
                                category="documents",
                                url_path=f"/documents?doc_id={d.id}",
                                score=1.0,
                                metadata={"file_type": d.file_type, "status": d.status},
                            )
                        )
                        if len(doc_results) >= limit:
                            break

                # Vector chunk search inside documents
                if request.include_semantic and len(doc_results) < limit:
                    vec_matches = await self.vector_store.query_documents(
                        profile_id=profile_id,
                        query=q,
                        top_k=limit - len(doc_results),
                    )
                    for vm in vec_matches:
                        if vm.score < 0.6:
                            continue
                        doc_id = vm.metadata.get("doc_id") or vm.source_id
                        fn = vm.metadata.get("filename", "Uploaded Document")
                        page = vm.metadata.get("page_number", 1)
                        t_text = vm.text or ""
                        doc_results.append(
                            GlobalSearchResultItem(
                                id=vm.id,
                                title=f"{fn} (Page {page})",
                                subtitle="Document Content Match",
                                snippet=t_text[:150] + ("..." if len(t_text) > 150 else ""),
                                category="documents",
                                url_path=f"/documents?doc_id={doc_id}",
                                score=vm.score,
                                metadata=vm.metadata,
                            )
                        )
            except Exception as e:
                logger.warning(f"Global search in documents failed: {e}")

        # 4. KNOWLEDGE GRAPH SEARCH
        if "graph" in categories:
            try:
                g = await self.graph_repo.get_graph(profile_id)
                for nid, attrs in g.nodes(data=True):
                    label = attrs.get("label", "")
                    desc = attrs.get("description", "")
                    ntype = attrs.get("type", "concept")
                    mastery = attrs.get("mastery_score", 0.0)

                    if q in label.lower() or (desc and q in desc.lower()):
                        graph_results.append(
                            GlobalSearchResultItem(
                                id=nid,
                                title=label,
                                subtitle=f"Knowledge Node ({ntype.title()}) • Mastery: {int(mastery*100)}%",
                                snippet=desc or f"Knowledge graph entity of type '{ntype}'.",
                                category="graph",
                                url_path=f"/graph?node_id={nid}",
                                score=1.0,
                                metadata={"node_type": ntype, "mastery_score": mastery},
                            )
                        )
                        if len(graph_results) >= limit:
                            break
            except Exception as e:
                logger.warning(f"Global search in knowledge graph failed: {e}")

        # 5. ROADMAP SEARCH
        if "roadmap" in categories:
            try:
                active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
                if active_roadmap:
                    if q in active_roadmap.title.lower():
                        roadmap_results.append(
                            GlobalSearchResultItem(
                                id=active_roadmap.id,
                                title=active_roadmap.title,
                                subtitle=f"Roadmap Curriculum • Mode: {active_roadmap.mode.title()}",
                                snippet=f"Active curriculum containing {len(active_roadmap.nodes or [])} topics.",
                                category="roadmap",
                                url_path=f"/roadmap?roadmap_id={active_roadmap.id}",
                                score=1.0,
                                metadata={"mode": active_roadmap.mode},
                            )
                        )

                    if active_roadmap.nodes:
                        for node in active_roadmap.nodes:
                            if q in node.title.lower():
                                roadmap_results.append(
                                    GlobalSearchResultItem(
                                        id=node.id,
                                        title=node.title,
                                        subtitle=f"Topic Node • Status: {node.status} • Mastery: {int(node.mastery_score*100)}%",
                                        snippet=f"Curriculum topic in {active_roadmap.title} (Order: {node.order_index})",
                                        category="roadmap",
                                        url_path=f"/roadmap?node_id={node.id}",
                                        score=0.95,
                                        metadata={"status": node.status, "mastery_score": node.mastery_score},
                                    )
                                )
                                if len(roadmap_results) >= limit:
                                    break
            except Exception as e:
                logger.warning(f"Global search in roadmap failed: {e}")

        total_count = (
            len(chat_results)
            + len(note_results)
            + len(doc_results)
            + len(graph_results)
            + len(roadmap_results)
        )

        return GlobalSearchResponse(
            query=request.query,
            total_results=total_count,
            chats=chat_results,
            notes=note_results,
            documents=doc_results,
            graph=graph_results,
            roadmap=roadmap_results,
        )
