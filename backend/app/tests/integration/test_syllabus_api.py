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
        json={"name": "Syllabus API Profile", "profile_type": "JEE"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_syllabus_upload_and_parse_endpoint(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _create_profile(client)

        syllabus_content = (
            b"# Mathematics Curriculum\n"
            b"## Chapter 1: Calculus\n"
            b"### Limits and Continuity\n"
            b"- Epsilon-delta definition\n"
            b"- L'Hopital's rule\n"
            b"### Derivatives\n"
            b"- Product rule and quotient rule\n"
            b"- Chain rule\n"
            b"## Chapter 2: Linear Algebra\n"
            b"### Matrices and Determinants\n"
            b"- Matrix multiplication\n"
            b"- Inverse and rank\n"
        )

        # 1. Upload syllabus document with is_syllabus=True
        upload_resp = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("math_syllabus.txt", syllabus_content, "text/plain")},
            data={"is_syllabus": "true"},
        )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()["data"]
        doc_id = doc_data["id"]
        assert doc_data["is_syllabus"] is True

        # 2. Parse syllabus endpoint
        parse_resp = client.post(
            f"/api/v1/profiles/{profile_id}/documents/{doc_id}/parse-syllabus"
        )
        assert parse_resp.status_code == 200
        syllabus = parse_resp.json()["data"]

        assert "subjects" in syllabus
        assert len(syllabus["subjects"]) >= 1
        assert syllabus["total_chapters"] >= 2
        assert syllabus["total_topics"] >= 3

        # Check subtopic extraction
        first_subject = syllabus["subjects"][0]
        chapter1 = first_subject["chapters"][0]
        assert chapter1["title"] == "Chapter 1: Calculus"
        topic1 = chapter1["topics"][0]
        assert topic1["title"] == "Limits and Continuity"
        assert len(topic1["subtopics"]) >= 2
        assert "L'Hopital's rule" in topic1["subtopics"]
