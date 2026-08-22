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
from app.exceptions import LearningOSError

logger = logging.getLogger(__name__)


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
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Source or Target node not found in graph")

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
