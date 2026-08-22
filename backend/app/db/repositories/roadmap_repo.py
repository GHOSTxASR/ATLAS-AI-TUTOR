from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Roadmap, RoadmapEdge, RoadmapNode
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
