from __future__ import annotations

import io
from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.tests.conftest import uploaded_document


class StubTutorLLM(BaseModelClient):
    """Deterministic tutor response so the lifecycle runs without a provider.

    The orchestrator now reports provider failures instead of substituting
    canned text, so this step needs a stubbed model rather than relying on a
    fallback to make the assertion pass.
    """

    def __init__(self, *args, **kwargs):
        pass

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(
            content=(
                "Adiabatic expansion exchanges no heat with the surroundings, "
                "while isothermal expansion holds temperature constant."
            )
        )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        return None

    def get_provider_name(self) -> str:
        return "stub"


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-e2e-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_end_to_end_full_learning_lifecycle(tmp_path, monkeypatch, stub_quiz_llm, stub_notes_llm):
    """
    End-to-End validation of the complete LearningOS learning lifecycle:
    1. Learner Profile Creation
    2. Syllabus Upload & Parsing
    3. Document Ingestion, Text Extraction & Vector Indexing
    4. Curriculum Roadmap DAG Generation
    5. Knowledge Graph Semantic Construction & Enrichment
    6. AI Tutor Orchestration with Unified 5-Pillar Context
    7. Long-Term Cognitive Memory Distillation
    8. Multi-Modality Note Generation
    9. Diagnostic Quiz Generation, Submission & Evaluation
    10. Full Analytics Calculation & Heatmap Tracking
    11. Global Search Multi-Pillar Discovery
    """
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.tutor_orchestrator.get_model_client", lambda s: StubTutorLLM()
    )

    with TestClient(app) as client:
        # Step 1: Create Learner Profile
        profile_resp = client.post(
            "/api/v1/profiles",
            json={"name": "Ashmit Sharma (JEE & GATE)", "profile_type": "JEE"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["data"]["id"]
        assert profile_id is not None

        # Step 2: Upload Syllabus and Course Material
        syllabus_text = """
# Physics & Thermodynamics Curriculum
## Chapter 1: Laws of Thermodynamics
- Zeroth Law and Thermal Equilibrium
- First Law of Thermodynamics and Internal Energy
- Adiabatic and Isothermal Processes
## Chapter 2: Heat Engines & Entropy
- Carnot Cycle and Efficiency
- Second Law of Thermodynamics
- Entropy Calculation in Reversible Processes
"""
        doc_resp = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={
                "file": (
                    "thermodynamics_syllabus.txt",
                    io.BytesIO(syllabus_text.encode("utf-8")),
                    "text/plain",
                )
            },
            data={"is_syllabus": "true"},
        )
        assert doc_resp.status_code == 201
        doc_id = doc_resp.json()["data"]["id"]
        document = uploaded_document(client, profile_id, doc_id)
        assert document["status"] in ("extracted", "indexed")

        # Step 3: Verify document chunk count and indexed status
        assert document["chunk_count"] >= 1

        # Step 4: Generate Roadmap DAG
        roadmap_resp = client.post(
            f"/api/v1/profiles/{profile_id}/roadmaps",
            json={
                "title": "Thermodynamics Mastery Pathway",
                "mode": "strict",
                "syllabus_text": syllabus_text,
            },
        )
        assert roadmap_resp.status_code == 201
        roadmap_data = roadmap_resp.json()["data"]
        nodes = roadmap_data["nodes"]
        assert len(nodes) >= 2

        # Step 5: Construct Knowledge Graph & Semantic Enrichment
        kg_node_1 = client.post(
            f"/api/v1/profiles/{profile_id}/graph/nodes",
            json={
                "label": "First Law of Thermodynamics",
                "type": "concept",
                "description": "Conservation of energy principle applied to thermodynamic systems: dQ = dU + dW.",
                "mastery_score": 0.4,
            },
        )
        assert kg_node_1.status_code == 201
        node1_id = kg_node_1.json()["data"]["id"]

        kg_node_2 = client.post(
            f"/api/v1/profiles/{profile_id}/graph/nodes",
            json={
                "label": "Carnot Heat Engine",
                "type": "concept",
                "description": "Theoretical maximum efficiency thermodynamic cycle operating between two reservoirs.",
                "mastery_score": 0.2,
            },
        )
        assert kg_node_2.status_code == 201
        node2_id = kg_node_2.json()["data"]["id"]

        edge_resp = client.post(
            f"/api/v1/profiles/{profile_id}/graph/edges",
            json={
                "source": node1_id,
                "target": node2_id,
                "type": "prerequisite_of",
            },
        )
        assert edge_resp.status_code == 201

        # Step 6: AI Tutor Orchestration with Unified 5-Pillar Context
        chat_resp = client.post(
            f"/api/v1/profiles/{profile_id}/tutor/chat",
            json={
                "content": "Teach me the difference between adiabatic and isothermal expansion.",
                "mode": "teaching",
            },
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()["data"]
        assert len(chat_data["content"]) > 0
        assert chat_data["mode"] == "teaching"

        # Step 7: Record Cognitive Long-Term Memories
        mem_weakness = client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "weakness",
                "subject": "Adiabatic Work Formula",
                "content": "Struggles with PV^gamma integration for work done in adiabatic expansion.",
                "confidence": 0.85,
            },
        )
        assert mem_weakness.status_code == 201

        mem_strength = client.post(
            f"/api/v1/profiles/{profile_id}/memory",
            json={
                "category": "strength",
                "subject": "Isothermal Processes",
                "content": "Demonstrates rapid calculation of isothermal work using W = nRT ln(V2/V1).",
                "confidence": 0.95,
            },
        )
        assert mem_strength.status_code == 201

        # Step 8: Auto-Generate Multi-Modality Study Notes
        lesson_note_resp = client.post(
            f"/api/v1/profiles/{profile_id}/notes/generate",
            json={
                "topic_title": "Thermodynamics First Law",
                "note_type": "lesson_note",
                "roadmap_node_id": nodes[0]["id"],
                "custom_instructions": "Include mathematical derivations for heat and work.",
            },
        )
        assert lesson_note_resp.status_code == 201
        assert "Thermodynamics" in lesson_note_resp.json()["data"]["title"]

        cheat_sheet_resp = client.post(
            f"/api/v1/profiles/{profile_id}/notes/generate",
            json={
                "topic_title": "Carnot Cycle Formulas",
                "note_type": "cheat_sheet",
                "roadmap_node_id": nodes[1]["id"],
            },
        )
        assert cheat_sheet_resp.status_code == 201

        # Step 9: Diagnostic Assessment Generation & Evaluation
        quiz_gen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/generate",
            json={
                "roadmap_node_id": nodes[0]["id"],
                "topic_title": "First Law & Work Calculations",
                "mode": "practice",
                "question_count": 3,
            },
        )
        assert quiz_gen_resp.status_code == 201
        quiz_data = quiz_gen_resp.json()["data"]
        quiz_id = quiz_data["id"]
        assert len(quiz_data["questions"]) == 3

        # Submit answers
        answers_payload = []
        for q in quiz_data["questions"]:
            if q["question_type"] == "mcq" and q.get("options"):
                answers_payload.append({"question_id": q["id"], "user_answer": q["options"][0]["id"]})
            elif q["question_type"] == "numerical":
                answers_payload.append({"question_id": q["id"], "user_answer": "42.0"})
            else:
                answers_payload.append({"question_id": q["id"], "user_answer": "Energy is conserved."})

        submit_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/{quiz_id}/submit",
            json={"answers": answers_payload},
        )
        assert submit_resp.status_code == 200
        eval_result = submit_resp.json()["data"]
        assert "score" in eval_result
        assert "question_results" in eval_result

        # Step 10: Verify Full Analytics Dashboard
        analytics_resp = client.get(f"/api/v1/profiles/{profile_id}/analytics/overview")
        assert analytics_resp.status_code == 200
        overview = analytics_resp.json()["data"]
        assert "completion_percentage" in overview
        assert "chapter_progress" in overview
        assert "total_study_minutes" in overview

        # Step 11: Multi-Pillar Global Search Discovery
        search_resp = client.get(
            f"/api/v1/profiles/{profile_id}/search/global",
            params={"q": "thermodynamics"},
        )
        assert search_resp.status_code == 200
        search_data = search_resp.json()["data"]
        assert search_data["total_results"] > 0
