from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Roadmap, RoadmapNode
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import AtlasError
from app.services.roadmap_builders import (
    build_adaptive_dag,
    build_hybrid_dag,
    build_strict_dag,
)
from app.schemas.roadmap import (
    RoadmapCreate,
    RoadmapEdgeResponse,
    RoadmapNodeResponse,
    RoadmapNodeUpdate,
    RoadmapProgress,
    RoadmapResponse,
    RoadmapSummaryResponse,
)
from app.services.syllabus_service import SyllabusService

logger = logging.getLogger(__name__)

#: How much of the existing roadmap has to reappear in a freshly parsed
#: syllabus before it counts as the same course still being studied.
#:
#: The two cases this separates look nothing alike: a syllabus that grew by a
#: chapter still contains nearly all of its old topics, while a syllabus for a
#: different subject shares almost none. Anywhere in the middle is
#: vanishingly rare, so the exact figure matters far less than having one.
SAME_COURSE_TITLE_OVERLAP = 0.5


def _normalized(title: str) -> str:
    """Titles as they compare across two parses of the same syllabus."""
    return " ".join((title or "").split()).strip().lower()


def _match_existing_nodes(
    existing: Sequence[RoadmapNode], nodes_data: list[dict[str, Any]]
) -> tuple[dict[str, str], float]:
    """Pair freshly parsed topics with the ones already on the roadmap.

    Matching is by title, under its parent first so that the "Introduction"
    beneath one module is not confused with the "Introduction" beneath
    another, then by title alone for whatever is left over.

    Returns the generated-id -> existing-id map, and the share of the existing
    roadmap that was recognised.
    """
    existing_titles = {n.id: _normalized(n.title) for n in existing}
    incoming_titles = {
        nd["id"]: _normalized(nd["title"]) for nd in nodes_data if nd.get("id")
    }

    def existing_key(node: RoadmapNode) -> tuple[str, str]:
        return (existing_titles.get(node.parent_id or "", ""), existing_titles[node.id])

    def incoming_key(nd: dict[str, Any]) -> tuple[str, str]:
        return (incoming_titles.get(nd.get("parent_id") or "", ""), _normalized(nd["title"]))

    by_parent_and_title: dict[tuple[str, str], str] = {}
    by_title: dict[str, str] = {}
    for node in existing:
        by_parent_and_title.setdefault(existing_key(node), node.id)
        by_title.setdefault(existing_titles[node.id], node.id)

    id_map: dict[str, str] = {}
    claimed: set[str] = set()

    # Two passes, so a confident match is never displaced by a looser one.
    for lookup, key in ((by_parent_and_title, incoming_key), (by_title, lambda nd: _normalized(nd["title"]))):
        for nd in nodes_data:
            generated_id = nd.get("id")
            if not generated_id or generated_id in id_map:
                continue
            candidate = lookup.get(key(nd))  # type: ignore[arg-type]
            # One existing topic cannot become two, or they would collide on
            # the same primary key.
            if candidate and candidate not in claimed:
                id_map[generated_id] = candidate
                claimed.add(candidate)

    overlap = len(claimed) / len(existing) if existing else 0.0
    return id_map, overlap


def _remap_ids(
    nodes_data: list[dict[str, Any]],
    edges_data: list[dict[str, Any]],
    id_map: dict[str, str],
) -> None:
    """Point a freshly built graph at the rows that already exist."""
    for nd in nodes_data:
        nd["id"] = id_map.get(nd.get("id"), nd.get("id"))
        if nd.get("parent_id"):
            nd["parent_id"] = id_map.get(nd["parent_id"], nd["parent_id"])
    for ed in edges_data:
        ed["from_node_id"] = id_map.get(ed["from_node_id"], ed["from_node_id"])
        ed["to_node_id"] = id_map.get(ed["to_node_id"], ed["to_node_id"])


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
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

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
            raise AtlasError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Either document_id or syllabus_text must be provided to generate a roadmap.",
            )

        title = data.title or parsed_syllabus.title or "Learning Roadmap"
        mode = data.mode.lower()

        # 2. Build graph DAG based on selected mode
        if mode == "adaptive":
            nodes_data, edges_data = await build_adaptive_dag(self.settings, profile_id, parsed_syllabus)
        elif mode == "hybrid":
            nodes_data, edges_data = await build_hybrid_dag(self.settings, profile_id, parsed_syllabus)
        else:
            # Strict mode (default)
            nodes_data, edges_data = build_strict_dag(profile_id, parsed_syllabus)

        # 3. Continue the roadmap already in progress when this syllabus is
        # the same course. Replacing it wholesale gave every topic a new id,
        # which reset all progress and cut every chat, note, quiz attempt and
        # document loose from the topic it was filed under -- so adding one
        # chapter to a syllabus cost the learner everything done so far.
        active = await self.repo.get_active_roadmap(profile_id)
        if active and active.nodes:
            id_map, overlap = _match_existing_nodes(active.nodes, nodes_data)
            if overlap >= SAME_COURSE_TITLE_OVERLAP:
                _remap_ids(nodes_data, edges_data, id_map)
                incoming_ids = {nd["id"] for nd in nodes_data if nd.get("id")}
                dropped = [n.id for n in active.nodes if n.id not in incoming_ids]
                keep_node_ids = await self.repo.nodes_with_history(dropped)
                logger.info(
                    "Updating roadmap %s in place: %.0f%% of its topics are in the "
                    "new syllabus, %d dropped (%d kept for their history).",
                    active.id,
                    overlap * 100,
                    len(dropped),
                    len(keep_node_ids),
                )
                reconciled = await self.repo.reconcile_roadmap(
                    active,
                    title=title,
                    mode=mode,
                    source_document_id=data.document_id,
                    nodes_data=nodes_data,
                    edges_data=edges_data,
                    keep_node_ids=keep_node_ids,
                )
                return self._format_roadmap_response(reconciled)

        # A different subject: keep the old roadmap as history and start fresh.
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
            raise AtlasError(status_code=404, code="NOT_FOUND", message="No active roadmap found for profile")
        return self._format_roadmap_response(roadmap)

    async def get_roadmap_by_id(self, profile_id: str, roadmap_id: str) -> RoadmapResponse:
        """Get roadmap by ID."""
        await self._require_profile(profile_id)
        roadmap = await self.repo.get_full_roadmap(roadmap_id)
        if not roadmap or roadmap.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Roadmap not found")
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
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Roadmap node not found")

        update_fields = data.model_dump(exclude_unset=True)
        if data.status == "completed" and not node.completed_at:
            update_fields["completed_at"] = datetime.now(timezone.utc)

        updated_node = await self.repo.update_node(node, **update_fields)
        return RoadmapNodeResponse.model_validate(updated_node)

    async def regenerate_roadmap(
        self, profile_id: str, roadmap_id: str, mode: str | None = None
    ) -> RoadmapResponse:
        """Rebuild a roadmap from its syllabus without losing what has been done.

        Progress used to be copied across by title onto a freshly created set
        of nodes. Generation now folds a re-parsed syllabus into the roadmap
        that is already there, which keeps the node ids as well as the
        progress -- so the chats, notes and quiz attempts filed against each
        topic stay attached to it instead of being cut loose.
        """
        old_roadmap = await self.repo.get_full_roadmap(roadmap_id)
        if not old_roadmap or old_roadmap.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Roadmap not found")

        # Read before generating: the commit inside expires this instance, and
        # touching an expired attribute afterwards raises rather than reloading.
        source_document_id = old_roadmap.source_document_id
        gen_mode = mode or old_roadmap.mode
        roadmap_title = old_roadmap.title
        next_version = old_roadmap.version + 1

        return await self.generate_roadmap(
            profile_id=profile_id,
            data=RoadmapCreate(
                document_id=source_document_id,
                mode=gen_mode,  # type: ignore[arg-type]
                title=roadmap_title,
            ),
            version=next_version,
        )
