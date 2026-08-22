from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Roadmap, RoadmapNode
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import LearningOSError
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.schemas.roadmap import (
    RoadmapCreate,
    RoadmapEdgeResponse,
    RoadmapNodeResponse,
    RoadmapNodeUpdate,
    RoadmapProgress,
    RoadmapResponse,
    RoadmapSummaryResponse,
)
from app.schemas.syllabus import ParsedSyllabus
from app.services.syllabus_service import SyllabusService
from app.utils.text_utils import extract_json_payload

logger = logging.getLogger(__name__)


def _is_acyclic(node_ids: set[str], edges: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    """Verify if graph is acyclic using Kahn's algorithm or DFS. Returns (is_acyclic, pruned_edges)."""
    adj: dict[str, list[str]] = {n: [] for n in node_ids}
    in_degree: dict[str, int] = {n: 0 for n in node_ids}

    valid_edges: list[dict[str, Any]] = []
    for e in edges:
        u, v = e["from_node_id"], e["to_node_id"]
        if u in node_ids and v in node_ids and u != v:
            adj[u].append(v)
            in_degree[v] += 1
            valid_edges.append(e)

    # Kahn's algorithm
    queue = [n for n, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        u = queue.pop(0)
        visited_count += 1
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if visited_count == len(node_ids):
        return True, valid_edges

    # Cycle detected: break back-edges to enforce DAG
    logger.warning("Cycle detected in generated roadmap graph; breaking cycle edges to preserve DAG.")
    acyclic_edges: list[dict[str, Any]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)
        for e in valid_edges:
            if e["from_node_id"] == node:
                neighbor = e["to_node_id"]
                if neighbor not in visited:
                    acyclic_edges.append(e)
                    dfs(neighbor)
                elif neighbor not in rec_stack:
                    acyclic_edges.append(e)
        rec_stack.remove(node)

    for n in node_ids:
        if n not in visited:
            dfs(n)

    return False, acyclic_edges


class RoadmapService:
    """Orchestrates Roadmap DAG generation in Strict, Adaptive, and Hybrid modes with progress tracking."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = RoadmapRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.syllabus_service = SyllabusService(session=session, settings=self.settings)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def generate_roadmap(
        self, profile_id: str, data: RoadmapCreate, version: int = 1
    ) -> RoadmapResponse:
        """Generate a complete learning roadmap DAG from a syllabus document or text."""
        await self._require_profile(profile_id)

        # 1. Parse syllabus
        if data.document_id:
            parsed_syllabus = await self.syllabus_service.parse_document_syllabus(
                profile_id=profile_id, document_id=data.document_id
            )
        elif data.syllabus_text:
            parsed_syllabus = await self.syllabus_service.parse_raw_text(
                text=data.syllabus_text, title=data.title or "Curriculum Roadmap"
            )
        else:
            raise LearningOSError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Either document_id or syllabus_text must be provided to generate a roadmap.",
            )

        title = data.title or parsed_syllabus.title or "Learning Roadmap"
        mode = data.mode.lower()

        # 2. Build graph DAG based on selected mode
        if mode == "adaptive":
            nodes_data, edges_data = await self._build_adaptive_dag(profile_id, parsed_syllabus)
        elif mode == "hybrid":
            nodes_data, edges_data = await self._build_hybrid_dag(profile_id, parsed_syllabus)
        else:
            # Strict mode (default)
            nodes_data, edges_data = self._build_strict_dag(profile_id, parsed_syllabus)

        # 3. Archive previously active roadmaps
        await self.repo.archive_active_roadmaps(profile_id)

        # 4. Save new roadmap
        roadmap = await self.repo.create_full_roadmap(
            profile_id=profile_id,
            title=title,
            mode=mode,
            version=version,
            source_document_id=data.document_id,
            nodes_data=nodes_data,
            edges_data=edges_data,
        )

        return self._format_roadmap_response(roadmap)

    # ── Mode Builders ─────────────────────────────────────────────────

    def _build_strict_dag(
        self, profile_id: str, syllabus: ParsedSyllabus
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Strict Mode: 1:1 direct mapping from syllabus structure with sequential edges."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        all_topic_ids: list[str] = []

        for s_idx, subj in enumerate(syllabus.subjects, start=1):
            subj_id = str(uuid.uuid4())
            nodes.append({
                "id": subj_id,
                "title": subj.title,
                "description": subj.description,
                "node_type": "subject",
                "status": "not_started",
                "parent_id": None,
                "order_index": s_idx,
                "ai_generated": False,
            })

            for c_idx, chap in enumerate(subj.chapters, start=1):
                chap_id = str(uuid.uuid4())
                nodes.append({
                    "id": chap_id,
                    "title": chap.title,
                    "description": chap.description,
                    "node_type": "chapter",
                    "status": "not_started",
                    "parent_id": subj_id,
                    "order_index": c_idx,
                    "ai_generated": False,
                })

                chap_topic_ids: list[str] = []
                for t_idx, topic in enumerate(chap.topics, start=1):
                    topic_id = str(uuid.uuid4())
                    nodes.append({
                        "id": topic_id,
                        "title": topic.title,
                        "description": topic.description,
                        "node_type": "topic",
                        "status": "not_started",
                        "parent_id": chap_id,
                        "order_index": t_idx,
                        "ai_generated": False,
                    })
                    chap_topic_ids.append(topic_id)
                    all_topic_ids.append(topic_id)

        # Connect consecutive topics sequentially across the curriculum
        for i in range(len(all_topic_ids) - 1):
            edges.append({
                "from_node_id": all_topic_ids[i],
                "to_node_id": all_topic_ids[i + 1],
                "edge_type": "sequential",
            })

        return nodes, edges

    async def _build_adaptive_dag(
        self, profile_id: str, syllabus: ParsedSyllabus
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Adaptive Mode: AI determines optimal prerequisite order and dependency DAG."""
        # Extract flat topic list
        topic_items: list[dict[str, Any]] = []
        for subj in syllabus.subjects:
            for chap in subj.chapters:
                for top in chap.topics:
                    topic_items.append({
                        "title": top.title,
                        "description": top.description,
                        "subject": subj.title,
                        "chapter": chap.title,
                    })

        if not topic_items:
            return self._build_strict_dag(profile_id, syllabus)

        # Query LLM for prerequisite ordering
        prompt = (
            "You are an expert learning scientist. Given the following list of study topics, "
            "determine the optimal learning sequence and prerequisite relationships to form a Directed Acyclic Graph (DAG).\n"
            "Topics:\n"
            f"{json.dumps(topic_items, indent=2)}\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            "{\n"
            '  "ordered_nodes": [\n'
            '    {"temp_id": "t1", "title": "Topic Name", "description": "Overview", "node_type": "topic"}\n'
            "  ],\n"
            '  "dependencies": [\n'
            '    {"from_temp_id": "t1", "to_temp_id": "t2", "edge_type": "prerequisite"}\n'
            "  ]\n"
            "}"
        )

        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You generate optimal prerequisite learning DAGs. Return ONLY JSON."),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.2,
                    max_tokens=3500,
                )
                raw = extract_json_payload(response.content)

                dag_json = json.loads(raw)
                temp_to_real: dict[str, str] = {}
                nodes: list[dict[str, Any]] = []
                edges: list[dict[str, Any]] = []

                for idx, nd in enumerate(dag_json.get("ordered_nodes", []), start=1):
                    real_id = str(uuid.uuid4())
                    temp_id = str(nd.get("temp_id", f"t{idx}"))
                    temp_to_real[temp_id] = real_id

                    nodes.append({
                        "id": real_id,
                        "title": str(nd.get("title", f"Topic {idx}")),
                        "description": str(nd.get("description", "")),
                        "node_type": "topic",
                        "status": "not_started",
                        "parent_id": None,
                        "order_index": idx,
                        "ai_generated": True,
                    })

                for dep in dag_json.get("dependencies", []):
                    from_id = temp_to_real.get(dep.get("from_temp_id", ""))
                    to_id = temp_to_real.get(dep.get("to_temp_id", ""))
                    if from_id and to_id and from_id != to_id:
                        edges.append({
                            "from_node_id": from_id,
                            "to_node_id": to_id,
                            "edge_type": str(dep.get("edge_type", "prerequisite")),
                        })

                # Validate acyclicity
                node_id_set = {n["id"] for n in nodes}
                _, clean_edges = _is_acyclic(node_id_set, edges)
                return nodes, clean_edges
            finally:
                await client.close()
        except Exception as e:
            logger.warning(f"Adaptive DAG generation failed, falling back to Strict mode: {e}")
            return self._build_strict_dag(profile_id, syllabus)

    async def _build_hybrid_dag(
        self, profile_id: str, syllabus: ParsedSyllabus
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Hybrid Mode: Preserves strict syllabus hierarchy and inserts AI bridge prerequisite nodes."""
        nodes, edges = self._build_strict_dag(profile_id, syllabus)
        topic_nodes = [n for n in nodes if n["node_type"] == "topic"]

        if not topic_nodes:
            return nodes, edges

        prompt = (
            "Given this curriculum of study topics, identify up to 3 foundational prerequisite concepts "
            "that would bridge gaps and help students master these topics better.\n"
            f"Topics: {[t['title'] for t in topic_nodes[:15]]}\n\n"
            "Return ONLY JSON:\n"
            "[\n"
            '  {"title": "Bridge Concept Title", "description": "Why needed", "prerequisite_for_topic": "Existing Topic Title"}\n'
            "]"
        )

        try:
            client = get_model_client(self.settings)
            try:
                response = await client.chat_complete(
                    messages=[
                        ChatMessage(role="system", content="You identify prerequisite bridging concepts. Return ONLY JSON."),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.2,
                    max_tokens=1500,
                )
                raw = extract_json_payload(response.content)

                bridges = json.loads(raw)
                if isinstance(bridges, list):
                    for b in bridges:
                        if not isinstance(b, dict) or "title" not in b:
                            continue
                        target_title = str(b.get("prerequisite_for_topic", "")).lower()
                        # Find target topic
                        target_node = next(
                            (n for n in topic_nodes if target_title in n["title"].lower()), None
                        )
                        if target_node:
                            bridge_id = str(uuid.uuid4())
                            nodes.append({
                                "id": bridge_id,
                                "title": f"Bridge: {b['title']}",
                                "description": str(b.get("description", "Foundational prerequisite")),
                                "node_type": "bridge",
                                "status": "not_started",
                                "parent_id": target_node.get("parent_id"),
                                "order_index": target_node.get("order_index", 1),
                                "ai_generated": True,
                            })
                            edges.append({
                                "from_node_id": bridge_id,
                                "to_node_id": target_node["id"],
                                "edge_type": "bridge",
                            })
            finally:
                await client.close()
        except Exception as e:
            logger.warning(f"Hybrid bridge generation failed, using strict DAG: {e}")

        return nodes, edges

    # ── Progress & Unlocks ────────────────────────────────────────────

    def _compute_unlocks_and_progress(
        self, nodes: Sequence[RoadmapNode], edges: Sequence[Any]
    ) -> tuple[dict[str, bool], RoadmapProgress]:
        """Compute whether each node is unlocked and aggregate completion progress."""
        completed_or_skipped = {n.id for n in nodes if n.status in ("completed", "skipped")}

        # Build incoming dependency graph
        incoming: dict[str, list[str]] = {n.id: [] for n in nodes}
        for e in edges:
            to_id = getattr(e, "to_node_id", None) or (e["to_node_id"] if isinstance(e, dict) else None)
            from_id = getattr(e, "from_node_id", None) or (e["from_node_id"] if isinstance(e, dict) else None)
            if to_id and from_id and to_id in incoming:
                incoming[to_id].append(from_id)

        unlock_map: dict[str, bool] = {}
        for n in nodes:
            deps = incoming.get(n.id, [])
            # A node is unlocked if it has no prerequisites OR all incoming prerequisites are completed/skipped
            unlock_map[n.id] = all(dep in completed_or_skipped for dep in deps)

        # Progress stats
        topic_nodes = [n for n in nodes if n.node_type in ("topic", "bridge")]
        total = len(topic_nodes) or len(nodes)
        completed = sum(1 for n in nodes if n.status == "completed")
        in_progress = sum(1 for n in nodes if n.status == "in_progress")
        pct = round((completed / total * 100.0), 1) if total > 0 else 0.0

        # Average over the whole curriculum, counting untouched topics as 0.
        # Excluding them (the old `mastery_score > 0.0` filter) reported 72%
        # mastery on a roadmap that was 33% complete, and disagreed with the
        # identically-labelled figure on the analytics overview.
        scored_nodes = topic_nodes or list(nodes)
        avg_mastery = (
            round(sum(n.mastery_score for n in scored_nodes) / len(scored_nodes), 2)
            if scored_nodes
            else 0.0
        )

        progress = RoadmapProgress(
            total_nodes=total,
            completed_nodes=completed,
            in_progress_nodes=in_progress,
            completion_percentage=pct,
            average_mastery=avg_mastery,
        )

        return unlock_map, progress

    def _format_roadmap_response(self, roadmap: Roadmap) -> RoadmapResponse:
        """Format Roadmap ORM into RoadmapResponse with unlock states and progress."""
        unlock_map, progress = self._compute_unlocks_and_progress(roadmap.nodes, roadmap.edges)

        node_responses: list[RoadmapNodeResponse] = []
        for n in roadmap.nodes:
            resp = RoadmapNodeResponse.model_validate(n)
            resp.unlocked = unlock_map.get(n.id, True)
            node_responses.append(resp)

        edge_responses = [RoadmapEdgeResponse.model_validate(e) for e in roadmap.edges]

        return RoadmapResponse(
            id=roadmap.id,
            profile_id=roadmap.profile_id,
            title=roadmap.title,
            mode=roadmap.mode,
            version=roadmap.version,
            is_active=roadmap.is_active,
            source_document_id=roadmap.source_document_id,
            created_at=roadmap.created_at,
            nodes=node_responses,
            edges=edge_responses,
            progress=progress,
        )

    # ── Service Methods ───────────────────────────────────────────────

    async def get_active_roadmap(self, profile_id: str) -> RoadmapResponse:
        """Get currently active roadmap for a profile."""
        await self._require_profile(profile_id)
        roadmap = await self.repo.get_active_roadmap(profile_id)
        if not roadmap:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="No active roadmap found for profile")
        return self._format_roadmap_response(roadmap)

    async def get_roadmap_by_id(self, profile_id: str, roadmap_id: str) -> RoadmapResponse:
        """Get roadmap by ID."""
        await self._require_profile(profile_id)
        roadmap = await self.repo.get_full_roadmap(roadmap_id)
        if not roadmap or roadmap.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Roadmap not found")
        return self._format_roadmap_response(roadmap)

    async def list_roadmaps(self, profile_id: str) -> list[RoadmapSummaryResponse]:
        """List all roadmaps for a profile."""
        await self._require_profile(profile_id)
        roadmaps = await self.repo.list_by_profile(profile_id)
        summaries: list[RoadmapSummaryResponse] = []
        for r in roadmaps:
            summaries.append(
                RoadmapSummaryResponse(
                    id=r.id,
                    profile_id=r.profile_id,
                    title=r.title,
                    mode=r.mode,
                    version=r.version,
                    is_active=r.is_active,
                    source_document_id=r.source_document_id,
                    created_at=r.created_at,
                    node_count=len(r.nodes),
                )
            )
        return summaries

    async def update_node_status(
        self, profile_id: str, roadmap_id: str, node_id: str, data: RoadmapNodeUpdate
    ) -> RoadmapNodeResponse:
        """Update node status or mastery score."""
        await self._require_profile(profile_id)
        node = await self.repo.get_node(node_id)
        if not node or node.profile_id != profile_id or node.roadmap_id != roadmap_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Roadmap node not found")

        update_fields = data.model_dump(exclude_unset=True)
        if data.status == "completed" and not node.completed_at:
            update_fields["completed_at"] = datetime.now(timezone.utc)

        updated_node = await self.repo.update_node(node, **update_fields)
        return RoadmapNodeResponse.model_validate(updated_node)

    async def regenerate_roadmap(
        self, profile_id: str, roadmap_id: str, mode: str | None = None
    ) -> RoadmapResponse:
        """Regenerate a roadmap as a new version and migrate progress from matching old nodes."""
        old_roadmap = await self.repo.get_full_roadmap(roadmap_id)
        if not old_roadmap or old_roadmap.profile_id != profile_id:
            raise LearningOSError(status_code=404, code="NOT_FOUND", message="Roadmap not found")

        gen_mode = mode or old_roadmap.mode
        new_version = old_roadmap.version + 1

        # Generate new roadmap
        create_req = RoadmapCreate(
            document_id=old_roadmap.source_document_id,
            mode=gen_mode,  # type: ignore
            title=old_roadmap.title,
        )
        new_roadmap_resp = await self.generate_roadmap(
            profile_id=profile_id, data=create_req, version=new_version
        )

        # Progress Migration: match old nodes to new nodes by normalized title
        old_nodes_by_title = {n.title.strip().lower(): n for n in old_roadmap.nodes}
        new_roadmap_db = await self.repo.get_full_roadmap(new_roadmap_resp.id)
        if new_roadmap_db:
            for new_n in new_roadmap_db.nodes:
                match = old_nodes_by_title.get(new_n.title.strip().lower())
                if match and match.status in ("completed", "in_progress", "skipped"):
                    await self.repo.update_node(
                        new_n,
                        status=match.status,
                        mastery_score=match.mastery_score,
                        time_spent_minutes=match.time_spent_minutes,
                        completed_at=match.completed_at,
                    )

            # Re-fetch after progress migration
            new_roadmap_db = await self.repo.get_full_roadmap(new_roadmap_resp.id)
            return self._format_roadmap_response(new_roadmap_db)  # type: ignore

        return new_roadmap_resp
