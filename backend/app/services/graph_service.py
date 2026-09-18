from __future__ import annotations

import json
import logging

import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Roadmap
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.services.document_text import load_document_text
from app.exceptions import AtlasError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.schemas.graph import (
    GraphDataResponse,
    GraphEdge,
    GraphEdgeCreate,
    GraphEnrichRequest,
    GraphNode,
    GraphNodeCreate,
    GraphNodeUpdate,
    GraphPathResponse,
    GraphStats,
)
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)

#: Roadmap node types that name something to be learned. Subjects and
#: chapters are how a syllabus is filed, not concepts in their own right.
LEARNABLE_ROADMAP_NODE_TYPES = ("topic", "bridge")


class GraphService:
    """Orchestrates Knowledge Graph generation, entity-relation extraction, and NetworkX topological queries."""

    def __init__(self, session: AsyncSession | None = None, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = GraphRepository(settings=self.settings)
        self.profile_repo = ProfileRepository(session) if session else None

    async def _require_profile(self, profile_id: str) -> None:
        if self.profile_repo:
            profile = await self.profile_repo.get_by_id(profile_id)
            if not profile:
                raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def get_graph_data(self, profile_id: str) -> GraphDataResponse:
        """Fetch all graph nodes and edges with aggregate summary statistics."""
        await self._require_profile(profile_id)
        await self._backfill_curriculum(profile_id)
        raw_nodes, raw_edges = await self.repo.get_all_nodes_and_edges(profile_id)

        nodes: list[GraphNode] = []
        mastery_sum = 0.0
        concept_count = 0
        doc_count = 0

        for nd in raw_nodes:
            node = GraphNode.model_validate(nd)
            nodes.append(node)
            if node.type == "concept":
                concept_count += 1
                mastery_sum += node.mastery_score
            elif node.type == "document":
                doc_count += 1

        edges = [GraphEdge.model_validate(ed) for ed in raw_edges]
        avg_mastery = round(mastery_sum / concept_count, 2) if concept_count > 0 else 0.0

        stats = GraphStats(
            total_nodes=len(nodes),
            total_edges=len(edges),
            concepts_count=concept_count,
            documents_count=doc_count,
            average_mastery=avg_mastery,
        )

        return GraphDataResponse(
            nodes=nodes,
            links=edges,
            directed=True,
            multigraph=False,
            stats=stats,
        )

    async def create_node(self, profile_id: str, data: GraphNodeCreate) -> GraphNode:
        """Create a new concept or entity node."""
        await self._require_profile(profile_id)
        node_dict = await self.repo.add_node(
            profile_id=profile_id,
            label=data.label,
            node_type=data.type,
            description=data.description,
            mastery_score=data.mastery_score,
            roadmap_node_id=data.roadmap_node_id,
            document_ids=data.document_ids,
            chat_session_ids=data.chat_session_ids,
        )
        return GraphNode.model_validate(node_dict)

    async def update_node(
        self, profile_id: str, node_id: str, data: GraphNodeUpdate
    ) -> GraphNode:
        """Update an existing graph node."""
        await self._require_profile(profile_id)
        updated = await self.repo.update_node(
            profile_id=profile_id,
            node_id=node_id,
            **data.model_dump(exclude_unset=True),
        )
        if not updated:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Graph node not found")
        return GraphNode.model_validate(updated)

    async def delete_node(self, profile_id: str, node_id: str) -> bool:
        """Delete a node and its incident edges."""
        await self._require_profile(profile_id)
        deleted = await self.repo.delete_node(profile_id, node_id)
        if not deleted:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Graph node not found")
        return True

    async def create_edge(self, profile_id: str, data: GraphEdgeCreate) -> GraphEdge:
        """Create a relationship edge between two graph nodes."""
        await self._require_profile(profile_id)
        edge_dict = await self.repo.add_edge(
            profile_id=profile_id,
            source=data.source,
            target=data.target,
            edge_type=data.type,
            weight=data.weight,
        )
        return GraphEdge.model_validate(edge_dict)

    async def delete_edge(self, profile_id: str, source: str, target: str) -> bool:
        """Delete an edge from the graph."""
        await self._require_profile(profile_id)
        deleted = await self.repo.delete_edge(profile_id, source, target)
        if not deleted:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Graph edge not found")
        return True

    async def _backfill_curriculum(self, profile_id: str) -> None:
        """Mirror the active roadmap the first time a graph built before this is read.

        Generating a roadmap keeps the graph in step from now on, but a learner
        who built theirs earlier would open this page and still find whatever
        ad-hoc extractions they had run, with the curriculum missing. Once a
        single concept is tied to a topic there is nothing left to backfill and
        this stops doing anything.
        """
        if self.session is None:
            return
        try:
            graph = await self.repo.get_graph(profile_id)
            if any(attrs.get("roadmap_node_id") for _, attrs in graph.nodes(data=True)):
                return

            from app.db.repositories.roadmap_repo import RoadmapRepository

            roadmap = await RoadmapRepository(self.session).get_active_roadmap(profile_id)
            if roadmap is None:
                return
            result = await self.sync_from_roadmap(profile_id, roadmap)
            if result["concepts_total"]:
                logger.info(
                    "Backfilled %d curriculum concepts into the graph for profile %s.",
                    result["concepts_total"],
                    profile_id,
                )
        except Exception as e:
            logger.warning("Could not backfill the curriculum graph for %s: %s", profile_id, e)

    async def sync_from_roadmap(self, profile_id: str, roadmap: Roadmap) -> dict[str, int]:
        """Mirror a roadmap's topics, and the order they are learned in, into the graph.

        The roadmap has already worked out what comes before what: strict mode
        chains the syllabus in order, adaptive mode asks the model for a
        prerequisite DAG, hybrid mode inserts bridging concepts first. All
        three mean "learn this before that", which is what an edge in the
        concept graph means, so the ordering is carried across rather than
        guessed at a second time from the same syllabus.

        Until this existed the graph had no idea a curriculum was there. It
        filled up only from ad-hoc extractions -- four to eight concepts at a
        time, each batch an island with no edge to any other -- while the
        roadmap next to it held every topic in sequence.
        """
        nodes = list(roadmap.nodes)
        edges = list(roadmap.edges)

        learnable = [n for n in nodes if n.node_type in LEARNABLE_ROADMAP_NODE_TYPES]
        position = {n.id: n.order_index or 0 for n in nodes}

        concepts = [
            {
                "roadmap_node_id": node.id,
                "label": node.title,
                "description": node.description or "",
                "mastery_score": node.mastery_score or 0.0,
            }
            for node in sorted(
                learnable,
                key=lambda n: (position.get(n.parent_id or "", 0), n.order_index or 0),
            )
        ]

        learnable_ids = {node.id for node in learnable}
        links = [
            (edge.from_node_id, edge.to_node_id)
            for edge in edges
            if edge.from_node_id in learnable_ids and edge.to_node_id in learnable_ids
        ]

        return await self.repo.sync_curriculum(profile_id, concepts, links)

    async def enrich_from_text(
        self, profile_id: str, data: GraphEnrichRequest
    ) -> GraphDataResponse:
        """Extract concepts, descriptions, and prerequisite links from learning text and link to source.

        A document can be named instead of pasting its contents. The text was
        already extracted when it was uploaded, so asking for it again was
        asking the learner to fetch something the app was sitting on.
        """
        await self._require_profile(profile_id)

        text = data.text or ""
        source_type = data.source_type
        source_id = data.source_id
        source_label = data.source_label

        if data.document_id:
            if self.session is None:
                raise AtlasError(
                    status_code=400,
                    code="VALIDATION_ERROR",
                    message="Reading a document requires a database session.",
                )
            document, text = await load_document_text(
                self.session, self.settings, profile_id, data.document_id
            )
            source_type = "document"
            source_id = data.document_id
            source_label = source_label or document.filename

        # 1. Ensure source entity node exists (Document / Chat)
        source_node_id = None
        if source_id:
            entity_label = source_label or (
                f"Document {source_id[:8]}"
                if source_type == "document"
                else f"Session {source_id[:8]}"
            )
            source_node = await self.repo.add_node(
                profile_id=profile_id,
                label=entity_label,
                node_type=source_type,
                node_id=source_id,
            )
            source_node_id = source_node["id"]

        # 2. Extract concepts with LLM
        prompt = (
            "You are an expert knowledge graph extraction engine. Given this learning text, "
            "extract the top 4-8 core technical concepts, definitions, and any prerequisite relationships between them.\n\n"
            f"Text Content:\n{text[:4000]}\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            "{\n"
            '  "concepts": [\n'
            '    {"label": "Concept Name", "description": "Concise summary"}\n'
            "  ],\n"
            '  "relationships": [\n'
            '    {"source": "Concept A", "target": "Concept B", "type": "prerequisite_of"}\n'
            "  ]\n"
            "}"
        )

        extracted_concepts: list[dict[str, str]] = []
        extracted_rels: list[dict[str, str]] = []

        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You extract semantic concept knowledge graphs. Return ONLY JSON."),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.1,
                    max_tokens=2500,
                )
                raw = extract_json_payload(response.content)

                parsed = json.loads(raw)
                extracted_concepts = parsed.get("concepts", [])
                extracted_rels = parsed.get("relationships", [])
            finally:
                await client.close()
        except Exception as e:
            logger.warning(f"AI graph extraction failed; using heuristic term extraction: {e}")
            # Fallback heuristic: extract capitalized key phrases
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for line in lines[:5]:
                if len(line) > 5 and len(line) < 50 and not line.startswith("#"):
                    extracted_concepts.append({"label": line, "description": "Extracted from source content."})

        # 3. Add extracted concepts and link to source
        label_to_id: dict[str, str] = {}
        for c in extracted_concepts:
            lbl = c.get("label", "").strip()
            if not lbl:
                continue
            doc_ids = [source_id] if source_id and source_type == "document" else []
            chat_ids = [source_id] if source_id and source_type == "chat" else []

            created = await self.repo.add_node(
                profile_id=profile_id,
                label=lbl,
                node_type="concept",
                description=c.get("description", ""),
                document_ids=doc_ids,
                chat_session_ids=chat_ids,
            )
            label_to_id[lbl.lower()] = created["id"]

            # Link concept -> source
            if source_node_id:
                rel_type = "taught_in" if source_type == "document" else "referenced_by"
                await self.repo.add_edge(
                    profile_id=profile_id,
                    source=created["id"],
                    target=source_node_id,
                    edge_type=rel_type,
                )

        # 4. Add concept-to-concept relationships
        for r in extracted_rels:
            src_lbl = r.get("source", "").strip().lower()
            tgt_lbl = r.get("target", "").strip().lower()
            rel_type = r.get("type", "related_to")

            src_id = label_to_id.get(src_lbl)
            tgt_id = label_to_id.get(tgt_lbl)

            if src_id and tgt_id and src_id != tgt_id:
                try:
                    await self.repo.add_edge(
                        profile_id=profile_id,
                        source=src_id,
                        target=tgt_id,
                        edge_type=rel_type,
                    )
                except Exception:
                    pass

        return await self.get_graph_data(profile_id)

    async def search_nodes(self, profile_id: str, query: str) -> list[GraphNode]:
        """Search graph nodes by label or description query."""
        await self._require_profile(profile_id)
        raw_nodes, _ = await self.repo.get_all_nodes_and_edges(profile_id)
        q = query.strip().lower()

        results: list[GraphNode] = []
        for nd in raw_nodes:
            lbl = nd.get("label", "").lower()
            desc = nd.get("description", "").lower()
            if q in lbl or q in desc:
                results.append(GraphNode.model_validate(nd))

        return results

    async def find_concept_path(
        self, profile_id: str, source_id: str, target_id: str
    ) -> GraphPathResponse:
        """Find the shortest learning prerequisite path between two concepts using NetworkX."""
        await self._require_profile(profile_id)
        g = await self.repo.get_graph(profile_id)

        if source_id not in g or target_id not in g:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Source or target concept not found")

        try:
            path_ids = nx.shortest_path(g, source=source_id, target=target_id)
            path_nodes = [GraphNode.model_validate({"id": nid, **g.nodes[nid]}) for nid in path_ids]
            return GraphPathResponse(
                source_id=source_id,
                target_id=target_id,
                path_found=True,
                path=path_nodes,
                length=len(path_nodes) - 1,
            )
        except nx.NetworkXNoPath:
            return GraphPathResponse(
                source_id=source_id,
                target_id=target_id,
                path_found=False,
                path=[],
                length=0,
            )
