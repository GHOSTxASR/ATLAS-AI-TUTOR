from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    ChatSession,
    Document,
    Note,
    QuizAttempt,
    Roadmap,
    RoadmapEdge,
    RoadmapNode,
)
from app.db.repositories.base import BaseRepository


class RoadmapRepository(BaseRepository[Roadmap]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=Roadmap, session=session)

    async def get_active_roadmap(self, profile_id: str) -> Roadmap | None:
        """Fetch the currently active roadmap for a profile along with all nodes and edges."""
        stmt = (
            select(Roadmap)
            .where(Roadmap.profile_id == profile_id)
            .where(Roadmap.is_active.is_(True))
            .options(
                selectinload(Roadmap.nodes),
                selectinload(Roadmap.edges),
            )
            .order_by(Roadmap.version.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_full_roadmap(self, roadmap_id: str) -> Roadmap | None:
        """Fetch a specific roadmap by ID along with its full node and edge DAG."""
        stmt = (
            select(Roadmap)
            .where(Roadmap.id == roadmap_id)
            .options(
                selectinload(Roadmap.nodes),
                selectinload(Roadmap.edges),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_profile(self, profile_id: str) -> Sequence[Roadmap]:
        """List all roadmaps for a profile ordered by creation date descending."""
        stmt = (
            select(Roadmap)
            .where(Roadmap.profile_id == profile_id)
            .options(selectinload(Roadmap.nodes))
            .order_by(Roadmap.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def archive_active_roadmaps(self, profile_id: str) -> None:
        """Mark any currently active roadmaps for this profile as archived."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Roadmap)
            .where(Roadmap.profile_id == profile_id)
            .where(Roadmap.is_active.is_(True))
            .values(is_active=False, archived_at=now)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def create_full_roadmap(
        self,
        profile_id: str,
        title: str,
        mode: str,
        version: int = 1,
        source_document_id: str | None = None,
        nodes_data: list[dict[str, Any]] | None = None,
        edges_data: list[dict[str, Any]] | None = None,
    ) -> Roadmap:
        """Create a Roadmap along with its nodes and edges in a single atomic transaction."""
        roadmap = Roadmap(
            profile_id=profile_id,
            title=title,
            mode=mode,
            version=version,
            is_active=True,
            source_document_id=source_document_id,
        )
        self.session.add(roadmap)
        await self.session.flush()

        # Insert nodes
        created_nodes: dict[str, RoadmapNode] = {}
        if nodes_data:
            for nd in nodes_data:
                node = RoadmapNode(
                    id=nd.get("id"),
                    roadmap_id=roadmap.id,
                    profile_id=profile_id,
                    title=nd["title"],
                    description=nd.get("description", ""),
                    node_type=nd.get("node_type", "topic"),
                    status=nd.get("status", "not_started"),
                    parent_id=nd.get("parent_id"),
                    order_index=nd.get("order_index", 1),
                    mastery_score=nd.get("mastery_score", 0.0),
                    time_spent_minutes=nd.get("time_spent_minutes", 0),
                    ai_generated=nd.get("ai_generated", False),
                    completed_at=nd.get("completed_at"),
                )
                self.session.add(node)
                if node.id:
                    created_nodes[node.id] = node

            await self.session.flush()

        # Insert edges
        if edges_data:
            for ed in edges_data:
                edge = RoadmapEdge(
                    roadmap_id=roadmap.id,
                    from_node_id=ed["from_node_id"],
                    to_node_id=ed["to_node_id"],
                    edge_type=ed.get("edge_type", "sequential"),
                )
                self.session.add(edge)

        await self.session.commit()
        return await self.get_full_roadmap(roadmap.id)  # type: ignore

    #: Everything that points at a roadmap node. A topic dropped from a
    #: syllabus is only worth keeping if the learner left something behind on
    #: it, and this is where that evidence lives.
    _NODE_REFERENCES = (
        (ChatSession, "roadmap_node_id"),
        (Document, "roadmap_node_id"),
        (QuizAttempt, "roadmap_node_id"),
        (Note, "roadmap_node_id"),
    )

    async def nodes_with_history(self, node_ids: Sequence[str]) -> set[str]:
        """Which of these nodes the learner has actually touched.

        Progress recorded on the node itself counts, and so does anything
        filed against it -- a chat, a note, a quiz attempt, an uploaded
        document. Deleting one of those nodes would strand all of it.
        """
        if not node_ids:
            return set()

        ids = list(node_ids)
        touched: set[str] = set()

        progressed = await self.session.execute(
            select(RoadmapNode.id).where(
                RoadmapNode.id.in_(ids),
                (RoadmapNode.status != "not_started")
                | (RoadmapNode.mastery_score > 0.0)
                | (RoadmapNode.time_spent_minutes > 0),
            )
        )
        touched.update(progressed.scalars().all())

        for model, column in self._NODE_REFERENCES:
            referenced = await self.session.execute(
                select(getattr(model, column)).where(getattr(model, column).in_(ids)).distinct()
            )
            touched.update(r for r in referenced.scalars().all() if r)

        return touched

    async def reconcile_roadmap(
        self,
        roadmap: Roadmap,
        *,
        title: str,
        mode: str,
        source_document_id: str | None,
        nodes_data: list[dict[str, Any]],
        edges_data: list[dict[str, Any]],
        keep_node_ids: set[str],
    ) -> Roadmap:
        """Fold a freshly parsed syllabus into an existing roadmap.

        Node ids are the anchor for every chat, note, quiz attempt and
        document filed against a topic, so a topic that survives the edit
        keeps its row rather than being replaced by an identical-looking new
        one. `nodes_data` is expected to already carry the surviving ids --
        the service maps them across before calling.

        Progress is never taken from `nodes_data`: the syllabus describes the
        course, not how far through it the learner is.
        """
        existing = {n.id: n for n in roadmap.nodes}
        incoming_ids = {nd["id"] for nd in nodes_data if nd.get("id")}

        roadmap.title = title
        roadmap.mode = mode
        roadmap.version = roadmap.version + 1
        if source_document_id:
            roadmap.source_document_id = source_document_id
        self.session.add(roadmap)

        for nd in nodes_data:
            node_id = nd.get("id")
            current = existing.get(node_id) if node_id else None
            if current is not None:
                # Same topic, possibly reworded or moved: refresh how it is
                # described and where it sits, and leave the learner's
                # progress alone.
                current.title = nd["title"]
                current.description = nd.get("description", "")
                current.node_type = nd.get("node_type", current.node_type)
                current.parent_id = nd.get("parent_id")
                current.order_index = nd.get("order_index", current.order_index)
                self.session.add(current)
            else:
                self.session.add(
                    RoadmapNode(
                        id=node_id,
                        roadmap_id=roadmap.id,
                        profile_id=roadmap.profile_id,
                        title=nd["title"],
                        description=nd.get("description", ""),
                        node_type=nd.get("node_type", "topic"),
                        status=nd.get("status", "not_started"),
                        parent_id=nd.get("parent_id"),
                        order_index=nd.get("order_index", 1),
                        mastery_score=nd.get("mastery_score", 0.0),
                        time_spent_minutes=nd.get("time_spent_minutes", 0),
                        ai_generated=nd.get("ai_generated", False),
                        completed_at=nd.get("completed_at"),
                    )
                )

        # Topics the new syllabus dropped. Ones the learner never touched go;
        # the rest stay, because deleting them would take real work with them.
        removed = [
            node_id
            for node_id in existing
            if node_id not in incoming_ids and node_id not in keep_node_ids
        ]
        if removed:
            # Children first: a parent_id still pointing at a deleted row
            # would be nulled out and orphan whatever hangs off it.
            await self.session.execute(
                update(RoadmapNode)
                .where(RoadmapNode.parent_id.in_(removed))
                .values(parent_id=None)
            )
            await self.session.execute(
                delete(RoadmapEdge).where(
                    RoadmapEdge.from_node_id.in_(removed)
                    | RoadmapEdge.to_node_id.in_(removed)
                )
            )
            await self.session.execute(
                delete(RoadmapNode).where(RoadmapNode.id.in_(removed))
            )

        await self.session.flush()

        # Edges carry no learner data, so they are simply rebuilt. Any that
        # would dangle -- into a kept-but-dropped topic, say -- are skipped.
        await self.session.execute(
            delete(RoadmapEdge).where(RoadmapEdge.roadmap_id == roadmap.id)
        )
        live_ids = {
            node_id for node_id in set(existing) | incoming_ids if node_id not in set(removed)
        }
        for ed in edges_data:
            if ed["from_node_id"] in live_ids and ed["to_node_id"] in live_ids:
                self.session.add(
                    RoadmapEdge(
                        roadmap_id=roadmap.id,
                        from_node_id=ed["from_node_id"],
                        to_node_id=ed["to_node_id"],
                        edge_type=ed.get("edge_type", "sequential"),
                    )
                )

        await self.session.commit()

        # Sessions here are created with expire_on_commit=False, so committing
        # leaves the node collection loaded exactly as it was read at the top
        # of this method -- and a re-fetch hands back that same identity-mapped
        # object rather than reloading it. Without this the caller sees the
        # roadmap as it looked *before* the syllabus was folded in, so a newly
        # added chapter only turned up after a refresh.
        #
        # Detached rather than expired: expiring leaves the instance in the
        # identity map, and reloading it then lazy-loads from wherever the
        # response happens to be assembled, which is outside the async
        # context the driver needs.
        self.session.expunge_all()
        return await self.get_full_roadmap(roadmap.id)  # type: ignore

    async def get_node(self, node_id: str) -> RoadmapNode | None:
        """Get a single roadmap node by ID."""
        stmt = select(RoadmapNode).where(RoadmapNode.id == node_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_node(self, node: RoadmapNode, **kwargs: Any) -> RoadmapNode:
        """Update fields on a roadmap node."""
        for k, v in kwargs.items():
            if hasattr(node, k):
                setattr(node, k, v)
        self.session.add(node)
        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def delete_by_profile_id(self, profile_id: str) -> None:
        """Delete all roadmaps for a profile."""
        await self.session.execute(
            delete(Roadmap).where(Roadmap.profile_id == profile_id)
        )
        await self.session.commit()


# Backward compatibility alias
RoadmapRepo = RoadmapRepository
