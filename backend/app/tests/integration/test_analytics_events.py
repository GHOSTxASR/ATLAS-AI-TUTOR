"""Analytics events must actually be emitted, in minutes.

Two defects covered here:
  * only `quiz_taken` was ever emitted, so the dashboard's chat and notes
    time were permanently zero;
  * `AnalyticsEvent.value` is summed as study *minutes*, but quiz events
    stored a 0-1 score there, which `int()` truncated to zero.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.tests.conftest import StubLLM


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "analytics-events-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _create_profile(client: TestClient) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={"name": "Analytics Events", "profile_type": "GATE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _events(profile_id: str) -> list[dict]:
    """Read analytics rows straight from SQLite.

    There is no GET endpoint for raw events (only POST /analytics/events), so
    the store is inspected directly.
    """
    import sqlite3

    from app.config import get_settings

    db_path = get_settings().paths.sqlite_dir / "learningos.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT event_type, entity_type, entity_id, value, metadata_json "
            "FROM analytics_events WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def test_tutor_chat_emits_a_chat_turn_event(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.tutor_orchestrator.get_model_client",
        lambda s: StubLLM("Recursion explained."),
    )

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        resp = client.post(
            f"/api/v1/profiles/{profile_id}/tutor/chat",
            json={"content": "Explain recursion.", "mode": "teaching"},
        )
        assert resp.status_code == 200

    events = _events(profile_id)

    chat_events = [e for e in events if e["event_type"] == "chat_turn"]
    assert len(chat_events) == 1, "chat turns were never recorded before"
    assert chat_events[0]["entity_type"] == "chat_session"
    assert chat_events[0]["value"] is not None


def test_quiz_event_records_minutes_not_score(tmp_path, monkeypatch, stub_quiz_llm):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)
        gen = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/generate",
            json={"topic_title": "Kinematics", "mode": "practice", "question_count": 3},
        )
        assert gen.status_code == 201
        quiz = gen.json()["data"]

        submit = client.post(
            f"/api/v1/profiles/{profile_id}/quiz/{quiz['id']}/submit",
            json={
                "answers": [
                    {"question_id": "q1", "user_answer": "A"},
                    {"question_id": "q2", "user_answer": "12.0"},
                    {"question_id": "q3", "user_answer": "Boundary conditions prevent errors."},
                ]
            },
        )
        assert submit.status_code == 200
        score = submit.json()["data"]["score"]

    events = _events(profile_id)

    quiz_events = [e for e in events if e["event_type"] == "quiz_taken"]
    assert len(quiz_events) == 1
    # The score belongs in metadata; `value` is a duration.
    assert quiz_events[0]["value"] != score
    assert quiz_events[0]["value"] >= 0.0
    assert str(score) in (quiz_events[0]["metadata_json"] or "")
