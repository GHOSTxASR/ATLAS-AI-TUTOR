from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from app.config import Settings, get_settings
from app.exceptions import AtlasError

logger = logging.getLogger(__name__)

#: Marks the edges that mirror the curriculum, so re-syncing can replace its
#: own ordering without disturbing links the learner drew by hand.
CURRICULUM_EDGE_ORIGIN = "curriculum"


class GraphRepository:
    """Manages profile-isolated Knowledge Graphs using NetworkX DiGraph and atomic JSON file persistence."""

    _graphs: dict[str, nx.DiGraph] = {}
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_dir = self.settings.paths.graph_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_lock(self, profile_id: str) -> asyncio.Lock:
        if profile_id not in self._locks:
            self._locks[profile_id] = asyncio.Lock()
        return self._locks[profile_id]

    def _get_file_path(self, profile_id: str) -> Path:
        return self.base_dir / f"{profile_id}_knowledge_graph.json"

    async def get_graph(self, profile_id: str) -> nx.DiGraph:
        """Get or load in-memory DiGraph for a profile."""
        if profile_id in self._graphs:
            return self._graphs[profile_id]

        async with self._get_lock(profile_id):
            if profile_id in self._graphs:
                return self._graphs[profile_id]

            file_path = self._get_file_path(profile_id)
            g = nx.DiGraph()

            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    g = nx.node_link_graph(data, directed=True, multigraph=False, edges="links")
                except Exception as e:
                    logger.error(f"Failed to load graph JSON for profile {profile_id}: {e}")
                    g = nx.DiGraph()

            self._graphs[profile_id] = g
            return g

    async def save_graph(self, profile_id: str) -> None:
        """Atomically persist in-memory DiGraph to JSON."""
        async with self._get_lock(profile_id):
            g = self._graphs.get(profile_id)
            if g is None:
                return

            file_path = self._get_file_path(profile_id)
            tmp_path = self.base_dir / f"{profile_id}_knowledge_graph.tmp.json"

            data = nx.node_link_data(g, edges="links")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            os.replace(tmp_path, file_path)

    async def sync_curriculum(
        self,
        profile_id: str,
        concepts: list[dict[str, Any]],
        links: list[tuple[str, str]],
    ) -> dict[str, int]:
        """Mirror a roadmap's topics, and the order they are learned in, into the graph.

        `concepts` carry the roadmap node id they come from; `links` are pairs
        of those ids meaning "learn the first before the second".

        Written in one pass under a single save. Going through `add_node` and
        `add_edge` would rewrite the whole graph file once per topic -- three
        hundred writes for a syllabus this size, each one larger than the last.

        Nothing is deleted. A concept the learner added by hand is adopted
        rather than duplicated when the curriculum turns out to name the same
        thing, and their own links survive a re-sync untouched.
        """
        if not concepts:
            return {
                "concepts_added": 0,
                "concepts_adopted": 0,
                "order_links": 0,
                "concepts_total": 0,
            }

        g = await self.get_graph(profile_id)
        now_str = datetime.now(timezone.utc).isoformat()

        async with self._get_lock(profile_id):
            by_roadmap_id: dict[str, str] = {}
            by_label: dict[str, str] = {}
            for n_id, attrs in g.nodes(data=True):
                roadmap_id = attrs.get("roadmap_node_id")
                if roadmap_id:
                    by_roadmap_id.setdefault(roadmap_id, n_id)
                label = (attrs.get("label") or "").strip().lower()
                if label:
                    by_label.setdefault(label, n_id)

            resolved: dict[str, str] = {}
            added = 0
            adopted = 0

            for concept in concepts:
                roadmap_node_id = concept.get("roadmap_node_id")
                label = (concept.get("label") or "").strip()
                if not roadmap_node_id or not label:
                    continue

                # The roadmap id is tried first: a topic that was reworded in a
                # later syllabus keeps the concept it already had, and with it
                # everything attached to it.
                n_id = by_roadmap_id.get(roadmap_node_id) or by_label.get(label.lower())

                if n_id is None:
                    n_id = str(uuid.uuid4())
                    g.add_node(
                        n_id,
                        id=n_id,
                        label=label,
                        type="concept",
                        profile_id=profile_id,
                        description=concept.get("description") or "",
                        mastery_score=float(concept.get("mastery_score") or 0.0),
                        mention_count=1,
                        first_seen=now_str,
                        last_seen=now_str,
                        roadmap_node_id=roadmap_node_id,
                        document_ids=[],
                        chat_session_ids=[],
                    )
                    added += 1
                else:
                    attrs = g.nodes[n_id]
                    if not attrs.get("roadmap_node_id"):
                        adopted += 1
                    attrs["label"] = label
                    attrs["roadmap_node_id"] = roadmap_node_id
                    if concept.get("description") and not attrs.get("description"):
                        attrs["description"] = concept["description"]
                    attrs["last_seen"] = now_str

                by_roadmap_id[roadmap_node_id] = n_id
                by_label[label.lower()] = n_id
                resolved[roadmap_node_id] = n_id

            # Replace the previous mirror, leaving hand-drawn links alone.
            g.remove_edges_from(
                [
                    (u, v)
                    for u, v, data in g.edges(data=True)
                    if data.get("origin") == CURRICULUM_EDGE_ORIGIN
                ]
            )

            # Two topics named the same thing share one concept, which can turn
            # a straight run of topics into a loop. Only worth checking for when
            # that has actually happened.
            collapsed = len(set(resolved.values())) < len(resolved)

            ordered = 0
            for source_roadmap_id, target_roadmap_id in links:
                u = resolved.get(source_roadmap_id)
                v = resolved.get(target_roadmap_id)
                if not u or not v or u == v:
                    continue
                existing = g.edges[u, v] if g.has_edge(u, v) else None
                if existing is not None and existing.get("origin") != CURRICULUM_EDGE_ORIGIN:
                    continue
                if collapsed and nx.has_path(g, v, u):
                    continue
                g.add_edge(
                    u,
                    v,
                    type="prerequisite_of",
                    weight=1.0,
                    created_at=now_str,
                    origin=CURRICULUM_EDGE_ORIGIN,
                )
                ordered += 1

        await self.save_graph(profile_id)
        return {
            "concepts_added": added,
            "concepts_adopted": adopted,
            "order_links": ordered,
            "concepts_total": len(resolved),
        }

    async def add_node(
        self,
        profile_id: str,
        label: str,
        node_type: str = "concept",
        description: str | None = None,
        mastery_score: float = 0.0,
        roadmap_node_id: str | None = None,
        document_ids: list[str] | None = None,
        chat_session_ids: list[str] | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        """Add or update a node in the graph."""
        g = await self.get_graph(profile_id)
        now_str = datetime.now(timezone.utc).isoformat()

        # Check for existing node with same label
        existing_id = None
        for n_id, attrs in g.nodes(data=True):
            if attrs.get("label", "").strip().lower() == label.strip().lower():
                existing_id = n_id
                break

        if existing_id:
            # Update existing node
            node = g.nodes[existing_id]
            node["mention_count"] = node.get("mention_count", 1) + 1
            node["last_seen"] = now_str
            if description and not node.get("description"):
                node["description"] = description
            if document_ids:
                cur_docs = set(node.get("document_ids", []))
                cur_docs.update(document_ids)
                node["document_ids"] = list(cur_docs)
            if chat_session_ids:
                cur_chats = set(node.get("chat_session_ids", []))
                cur_chats.update(chat_session_ids)
                node["chat_session_ids"] = list(cur_chats)

            await self.save_graph(profile_id)
            return {"id": existing_id, **node}

        # Create new node
        n_id = node_id or str(uuid.uuid4())
        node_attrs: dict[str, Any] = {
            "id": n_id,
            "label": label,
            "type": node_type,
            "profile_id": profile_id,
            "description": description or "",
            "mastery_score": mastery_score,
            "mention_count": 1,
            "first_seen": now_str,
            "last_seen": now_str,
            "roadmap_node_id": roadmap_node_id,
            "document_ids": document_ids or [],
            "chat_session_ids": chat_session_ids or [],
        }
        g.add_node(n_id, **node_attrs)
        await self.save_graph(profile_id)
        return node_attrs

    async def update_node(self, profile_id: str, node_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Update node attributes."""
        g = await self.get_graph(profile_id)
        if node_id not in g:
            return None

        node = g.nodes[node_id]
        for k, v in kwargs.items():
            if v is not None:
                node[k] = v
        node["last_seen"] = datetime.now(timezone.utc).isoformat()
        await self.save_graph(profile_id)
        return {"id": node_id, **node}

    async def delete_node(self, profile_id: str, node_id: str) -> bool:
        """Remove a node and all connected edges from the graph."""
        g = await self.get_graph(profile_id)
        if node_id not in g:
            return False
        g.remove_node(node_id)
        await self.save_graph(profile_id)
        return True

    async def add_edge(
        self,
        profile_id: str,
        source: str,
        target: str,
        edge_type: str = "related_to",
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Create a directed edge between two nodes in the graph."""
        g = await self.get_graph(profile_id)
        if source not in g or target not in g:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Source or Target node not found in graph")

        now_str = datetime.now(timezone.utc).isoformat()
        edge_attrs: dict[str, Any] = {
            "type": edge_type,
            "weight": weight,
            "created_at": now_str,
        }
        g.add_edge(source, target, **edge_attrs)

        # For 'related_to', also add reverse edge for bidirectional representation
        if edge_type == "related_to" and not g.has_edge(target, source):
            g.add_edge(target, source, **edge_attrs)

        await self.save_graph(profile_id)
        return {"source": source, "target": target, **edge_attrs}

    async def delete_edge(self, profile_id: str, source: str, target: str) -> bool:
        """Remove an edge from the graph."""
        g = await self.get_graph(profile_id)
        if not g.has_edge(source, target):
            return False
        g.remove_edge(source, target)
        if g.has_edge(target, source) and g[target][source].get("type") == "related_to":
            g.remove_edge(target, source)
        await self.save_graph(profile_id)
        return True

    async def get_all_nodes_and_edges(
        self, profile_id: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch all nodes and edges for rendering or querying."""
        g = await self.get_graph(profile_id)
        nodes: list[dict[str, Any]] = []
        for n_id, attrs in g.nodes(data=True):
            node_dict = dict(attrs)
            node_dict["id"] = n_id
            nodes.append(node_dict)

        edges: list[dict[str, Any]] = []
        for u, v, attrs in g.edges(data=True):
            edge_dict = dict(attrs)
            edge_dict["source"] = u
            edge_dict["target"] = v
            edges.append(edge_dict)

        return nodes, edges

    async def delete_by_profile_id(self, profile_id: str) -> None:
        """Clear graph memory and delete graph file for a profile."""
        async with self._get_lock(profile_id):
            if profile_id in self._graphs:
                del self._graphs[profile_id]
            file_path = self._get_file_path(profile_id)
            if file_path.exists():
                file_path.unlink()


# Backward compatibility alias
GraphRepo = GraphRepository
