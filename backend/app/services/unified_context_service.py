from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import AtlasError
from app.pipelines.chunker import DocumentChunker
from app.rag.pipeline import RAGPipeline
from app.schemas.context import (
    KnowledgeGraphContextSummary,
    MemoryContextSummary,
    RoadmapContextSummary,
    SyllabusContextSummary,
    UnifiedLearningContext,
)
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Token accounting uses an OpenAI tokenizer for every provider, so counts are
# estimates. Leave headroom rather than filling the window exactly.
RAG_BUDGET_SAFETY_FACTOR = 0.85
# Below this, a context block is too small to be worth retrieving.
MIN_RAG_TOKENS = 200


class UnifiedContextService:
    """Combines Memory, Roadmap, Knowledge Graph, Syllabus, and Uploaded Documents into a unified learning context."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.profile_repo = ProfileRepository(session)
        self.roadmap_repo = RoadmapRepository(session)
        self.memory_repo = MemoryRepository(session)
        self.graph_repo = GraphRepository(settings=self.settings)
        self.memory_service = MemoryService(session=session, settings=self.settings)
        self.rag_pipeline = RAGPipeline(settings=self.settings)
        self.chunker = DocumentChunker()

    async def build_unified_context(
        self,
        profile_id: str,
        query: str,
        mode: str = "teaching",
        roadmap_node_id: str | None = None,
        document_ids: list[str] | None = None,
        max_context_tokens: int = 4500,
    ) -> UnifiedLearningContext:
        """Aggregate all 5 learning pillars into a coherent, token-budgeted prompt structure."""
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

        # 1. ROADMAP & SYLLABUS PILLAR
        roadmap_summary = RoadmapContextSummary()
        syllabus_summary = SyllabusContextSummary()
        active_topic_title = None

        try:
            active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
            if active_roadmap:
                roadmap_summary.roadmap_title = active_roadmap.title
                roadmap_summary.mode = active_roadmap.mode
                syllabus_summary.syllabus_title = active_roadmap.title

                # Locate specific node or currently in-progress node
                target_node = None
                if roadmap_node_id:
                    target_node = await self.roadmap_repo.get_node(roadmap_node_id)
                elif active_roadmap.nodes:
                    # Find in_progress or first uncompleted node
                    for n in active_roadmap.nodes:
                        if n.status == "in_progress":
                            target_node = n
                            break
                    if not target_node:
                        for n in active_roadmap.nodes:
                            if n.status != "completed":
                                target_node = n
                                break

                if target_node:
                    active_topic_title = target_node.title
                    roadmap_summary.active_topic = target_node.title
                    roadmap_summary.mastery_score = target_node.mastery_score
                    roadmap_summary.status = target_node.status

                    # Prerequisite & successor topics from DAG edges
                    if active_roadmap.edges and active_roadmap.nodes:
                        node_map = {n.id: n.title for n in active_roadmap.nodes}
                        prereq_ids = [
                            e.from_node_id
                            for e in active_roadmap.edges
                            if e.to_node_id == target_node.id
                        ]
                        next_ids = [
                            e.to_node_id
                            for e in active_roadmap.edges
                            if e.from_node_id == target_node.id
                        ]
                        roadmap_summary.prerequisites = [
                            node_map[nid] for nid in prereq_ids if nid in node_map
                        ]
                        roadmap_summary.next_topics = [
                            node_map[nid] for nid in next_ids if nid in node_map
                        ]

                    # Extract syllabus chapter structure
                    syllabus_summary.current_chapter = target_node.title
                    syllabus_summary.covered_subtopics = [
                        n.title for n in active_roadmap.nodes if n.node_type in ("subtopic", "topic")
                    ][:8]

        except Exception as e:
            logger.warning(f"Roadmap context extraction failed: {e}")

        # 2. MEMORY PILLAR
        memory_summary = MemoryContextSummary()
        learner_memory_prompt = ""
        try:
            learner_memory_prompt = await self.memory_service.get_learner_profile_context(
                profile_id=profile_id, topic=active_topic_title or query
            )
            # Parse structured items for metadata summary
            mem_records = await self.memory_repo.get_by_profile_id(profile_id)
            for m in mem_records:
                if m.category == "strength":
                    memory_summary.strengths.append(f"{m.subject}: {m.content}")
                elif m.category == "weakness":
                    memory_summary.weaknesses.append(f"{m.subject}: {m.content}")
                elif m.category == "profile" and "style" in m.subject.lower():
                    memory_summary.learning_style = m.content
        except Exception as e:
            logger.warning(f"Memory context extraction failed: {e}")

        # 3. KNOWLEDGE GRAPH PILLAR
        graph_summary = KnowledgeGraphContextSummary()
        try:
            g = await self.graph_repo.get_graph(profile_id)
            # Match concept in graph
            target_label = (active_topic_title or query).lower()
            matched_id = None
            for nid, attrs in g.nodes(data=True):
                lbl = attrs.get("label", "").lower()
                if lbl in target_label or target_label in lbl:
                    matched_id = nid
                    graph_summary.matched_concept = attrs.get("label")
                    graph_summary.concept_description = attrs.get("description")
                    graph_summary.mastery_score = attrs.get("mastery_score", 0.0)
                    graph_summary.mention_count = attrs.get("mention_count", 1)
                    break

            if matched_id:
                # Find connected prerequisites, related, and documents
                for u, v, attrs in g.in_edges(matched_id, data=True):
                    rel = attrs.get("type")
                    u_lbl = g.nodes[u].get("label", u)
                    if rel == "prerequisite_of":
                        graph_summary.prerequisite_concepts.append(u_lbl)
                for u, v, attrs in g.out_edges(matched_id, data=True):
                    rel = attrs.get("type")
                    v_lbl = g.nodes[v].get("label", v)
                    if rel == "prerequisite_of":
                        graph_summary.prerequisite_concepts.append(v_lbl)
                    elif rel == "related_to":
                        graph_summary.related_concepts.append(v_lbl)
                    elif rel == "taught_in":
                        graph_summary.connected_documents.append(v_lbl)
        except Exception as e:
            logger.warning(f"Knowledge Graph context extraction failed: {e}")

        # 4. SYNTHESIZE UNIFIED SYSTEM PROMPT WITH TOKEN BUDGETING.
        #    The non-RAG pillars are built first so the retrieved-document block
        #    can be given exactly the budget they leave. `max_context_tokens`
        #    was previously accepted and then ignored, so the prompt could grow
        #    past the model's context window and be rejected outright.
        prompt_blocks: list[str] = [
            f"You are the Atlas Unified AI Tutor. Personalized learner: {profile.name} (Target Track: {profile.profile_type}).",
            f"Active Learning Mode: {mode.upper()}.",
            "",
            "### 1. LEARNER MEMORY PROFILE:",
        ]

        if memory_summary.weaknesses:
            prompt_blocks.append(f"- Known Weaknesses / Misconceptions to Address: {', '.join(memory_summary.weaknesses[:4])}")
        if memory_summary.strengths:
            prompt_blocks.append(f"- Demonstrated Strengths: {', '.join(memory_summary.strengths[:4])}")
        if memory_summary.learning_style:
            prompt_blocks.append(f"- Preferred Pedagogy / Learning Style: {memory_summary.learning_style}")
        if not (memory_summary.weaknesses or memory_summary.strengths or memory_summary.learning_style):
            prompt_blocks.append("- Building baseline profile.")

        prompt_blocks.append("")
        prompt_blocks.append("### 2. CURRICULUM & ROADMAP PROGRESSION:")
        if roadmap_summary.active_topic:
            prompt_blocks.append(f"- Current Roadmap Topic: {roadmap_summary.active_topic} (Status: {roadmap_summary.status}, Demonstrated Mastery: {int(roadmap_summary.mastery_score*100)}%)")
            if roadmap_summary.prerequisites:
                prompt_blocks.append(f"- Key Prerequisites Needed: {', '.join(roadmap_summary.prerequisites)}")
            if roadmap_summary.next_topics:
                prompt_blocks.append(f"- Next Target in Roadmap: {', '.join(roadmap_summary.next_topics)}")
        else:
            prompt_blocks.append("- Open study (No specific roadmap node locked).")

        prompt_blocks.append("")
        prompt_blocks.append("### 3. KNOWLEDGE GRAPH SEMANTIC MAP:")
        if graph_summary.matched_concept:
            prompt_blocks.append(f"- Active Concept: {graph_summary.matched_concept}")
            if graph_summary.concept_description:
                prompt_blocks.append(f"- Definition: {graph_summary.concept_description}")
            if graph_summary.related_concepts:
                prompt_blocks.append(f"- Related Concepts: {', '.join(graph_summary.related_concepts)}")
            if graph_summary.connected_documents:
                prompt_blocks.append(f"- Referenced In: {', '.join(graph_summary.connected_documents)}")
        else:
            prompt_blocks.append("- Concept mapping active.")

        prompt_blocks.append("")
        prompt_blocks.append("### 4. SYLLABUS SCOPE:")
        if syllabus_summary.current_chapter:
            prompt_blocks.append(f"- Chapter / Scope: {syllabus_summary.current_chapter}")
        if syllabus_summary.covered_subtopics:
            prompt_blocks.append(f"- Relevant Syllabus Topics: {', '.join(syllabus_summary.covered_subtopics[:5])}")

        prompt_blocks.append("")
        prompt_blocks.append("### 5. RETRIEVED DOCUMENT KNOWLEDGE (RAG):")

        # 5. UPLOADED DOCUMENTS (RAG) PILLAR, budgeted with what remains.
        #    Token counts are approximate for non-OpenAI providers, so keep a
        #    margin rather than filling the window exactly.
        used_tokens = self.chunker.count_tokens("\n".join(prompt_blocks))
        remaining = int((max_context_tokens - used_tokens) * RAG_BUDGET_SAFETY_FACTOR)

        rag_context_text = ""
        citations_list = []
        if remaining >= MIN_RAG_TOKENS:
            try:
                assembled = await self.rag_pipeline.retrieve_and_assemble(
                    profile_id=profile_id,
                    query=query,
                    doc_ids=document_ids,
                    topic_context=active_topic_title,
                    roadmap_node_id=roadmap_node_id,
                    learner_profile_context=learner_memory_prompt,
                    max_context_tokens=remaining,
                )
                rag_context_text = assembled.context_block
                citations_list = [c.to_dict() for c in assembled.citations]
            except Exception as e:
                logger.warning(f"RAG document context retrieval failed: {e}")
        else:
            logger.warning(
                "Skipping RAG context: only %d tokens left of a %d budget.",
                remaining,
                max_context_tokens,
            )

        if rag_context_text:
            prompt_blocks.append(rag_context_text)
            prompt_blocks.append("Cite source indices matching [1], [2] when answering from document context.")
        else:
            prompt_blocks.append("Rely on verified academic domain foundations.")

        full_system_prompt = "\n".join(prompt_blocks)
        total_tokens = self.chunker.count_tokens(full_system_prompt)

        return UnifiedLearningContext(
            profile_id=profile_id,
            profile_name=profile.name,
            profile_type=profile.profile_type,
            mode=mode,
            system_prompt=full_system_prompt,
            memory=memory_summary,
            roadmap=roadmap_summary,
            graph=graph_summary,
            syllabus=syllabus_summary,
            citations=citations_list,
            total_tokens=total_tokens,
        )
