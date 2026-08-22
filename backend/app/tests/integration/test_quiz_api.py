from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Quiz API Profile", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_quiz_api_lifecycle(tmp_path, monkeypatch, stub_quiz_llm):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        # 1. Generate Quiz via API
        gen_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/generate",
            json={
                "topic_title": "Rotational Dynamics",
                "mode": "practice",
                "question_count": 3,
            },
        )
        assert gen_resp.status_code == 201
        quiz = gen_resp.json()["data"]
        quiz_id = quiz["id"]
        assert len(quiz["questions"]) == 3

        # 2. Submit Quiz Answers
        q1_id = quiz["questions"][0]["id"]
        q2_id = quiz["questions"][1]["id"]
        q3_id = quiz["questions"][2]["id"]

        sub_resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/{quiz_id}/submit",
            json={
                "answers": [
                    {"question_id": q1_id, "user_answer": "A"},
                    {"question_id": q2_id, "user_answer": "12.0"},
                    {"question_id": q3_id, "user_answer": "Boundary conditions prevent errors."},
                ]
            },
        )
        assert sub_resp.status_code == 200
        result = sub_resp.json()["data"]
        assert result["score"] >= 0.6
        assert len(result["question_results"]) == 3

        # 3. Get Results
        res_resp = client.get(f"/api/v1/profiles/{profile_id}/quiz/{quiz_id}/results")
        assert res_resp.status_code == 200
        res_data = res_resp.json()["data"]
        assert res_data["score"] == result["score"]

        # 4. Get History
        hist_resp = client.get(f"/api/v1/profiles/{profile_id}/quiz/history")
        assert hist_resp.status_code == 200
        history = hist_resp.json()["data"]
        assert len(history) >= 1
        assert history[0]["id"] == quiz_id


def test_quiz_generation_reports_provider_failure(tmp_path, monkeypatch):
    """A failed generation must error, not hand back templated placeholders.

    Regression: the service returned three hardcoded questions (including a
    made-up numerical answer), so the learner sat a quiz that tested nothing
    and received a meaningless score.
    """
    app = _make_app(tmp_path, monkeypatch)

    def _no_provider(_settings):
        raise ValueError("No Gemini API key configured. Set it on the Settings page.")

    monkeypatch.setattr("app.services.quiz_service.get_model_client", _no_provider)

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        resp = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/generate",
            json={"topic_title": "Rotational Dynamics", "mode": "practice", "question_count": 5},
        )

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PROVIDER_NOT_CONFIGURED"
    assert "best describes the core principle" not in resp.text
