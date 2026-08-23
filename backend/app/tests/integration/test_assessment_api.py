from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Assessment API Tester", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_assessment_api_generation_and_evaluation(tmp_path, monkeypatch, stub_quiz_llm):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Generate Assessment via API
        gen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/assessments",
            json={
                "assessment_type": "comprehensive_exam",
                "topic_titles": ["Thermodynamics", "Kinetic Theory"],
                "difficulty": "hard",
                "question_count": 3,
                "time_limit_seconds": 1200,
            },
        )
        assert gen_resp.status_code == 201
        assessment = gen_resp.json()["data"]
        assessment_id = assessment["id"]
        assert assessment["total_questions"] == 3
        assert assessment["difficulty"] == "hard"

        # 2. Submit Answers and get Automatic Learning Evaluation
        q1_id = assessment["questions"][0]["id"]
        q2_id = assessment["questions"][1]["id"]
        q3_id = assessment["questions"][2]["id"]

        sub_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/{assessment_id}/submit",
            json={
                "answers": [
                    {"question_id": q1_id, "user_answer": "A"},
                    {"question_id": q2_id, "user_answer": "12.0"},
                    {"question_id": q3_id, "user_answer": "State variables depend on state not path."},
                ]
            },
        )
        assert sub_resp.status_code == 200
        evaluation = sub_resp.json()["data"]
        assert "score" in evaluation
        assert "letter_grade" in evaluation
        assert "question_results" in evaluation
        assert len(evaluation["question_results"]) == 3
