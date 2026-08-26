"""DAG construction for the three roadmap modes.

Split out of RoadmapService, which was doing two unrelated jobs: turning a
parsed syllabus into nodes and edges, and managing roadmaps once they exist.
These functions touch no repository and no session -- they take a parsed
syllabus and return plain dicts -- so keeping them in the service put 200 lines
of graph building in between its CRUD methods.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.config import Settings
from app.models.abstraction import ChatMessage
from app.models.provider_factory import get_model_client
from app.schemas.syllabus import ParsedSyllabus
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


def build_strict_dag(
    profile_id: str, syllabus: ParsedSyllabus
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

async def build_adaptive_dag(
    settings: Settings, profile_id: str, syllabus: ParsedSyllabus
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
        return build_strict_dag(profile_id, syllabus)

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
        client = get_model_client(settings)
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
        return build_strict_dag(profile_id, syllabus)

async def build_hybrid_dag(
    settings: Settings, profile_id: str, syllabus: ParsedSyllabus
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hybrid Mode: Preserves strict syllabus hierarchy and inserts AI bridge prerequisite nodes."""
    nodes, edges = build_strict_dag(profile_id, syllabus)
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
        client = get_model_client(settings)
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
