"""What the tutor can search has to match what the notes actually say.

Only creating a note ever reached the vector index. Editing one left the
original wording searchable -- so a note corrected by the learner went on
being retrieved and quoted in its wrong form -- and deleting one left the
text in the index entirely, cited as a source with nothing behind it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "notes-sync-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


class _Index:
    """Records what the notes collection was asked to hold."""

    def __init__(self):
        self.indexed: list[tuple[str, str, str]] = []
        self.deleted: list[str] = []


def _patch_vector_store(monkeypatch) -> _Index:
    record = _Index()

    async def index_note(self, *, profile_id, note_id, title, text, **kwargs):
        record.indexed.append((note_id, title, text))
        return f"note:{note_id}"

    async def delete_by_note_id(self, *, profile_id, note_id):
        record.deleted.append(note_id)

    monkeypatch.setattr("app.rag.vector_store.VectorStore.index_note", index_note)
    monkeypatch.setattr("app.rag.vector_store.VectorStore.delete_by_note_id", delete_by_note_id)
    return record


def _profile(client: TestClient) -> str:
    return client.post(
        "/api/v1/profiles", json={"name": "Note Keeper", "profile_type": "GATE"}
    ).json()["data"]["id"]


def _note(client: TestClient, profile_id: str) -> str:
    created = client.post(
        f"/api/v1/profiles/{profile_id}/notes",
        json={"title": "Dijkstra", "content": "Relax every edge once per vertex."},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


def test_editing_a_note_updates_what_can_be_searched(tmp_path, monkeypatch):
    record = _patch_vector_store(monkeypatch)
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _profile(client)
        note_id = _note(client, profile_id)

        edited = client.patch(
            f"/api/v1/profiles/{profile_id}/notes/{note_id}",
            json={"content": "Relax every edge V-1 times."},
        )
        assert edited.status_code == 200, edited.text

    assert record.indexed, "the edit never reached the index"
    last_id, _, last_text = record.indexed[-1]
    assert last_id == note_id
    assert last_text == "Relax every edge V-1 times.", (
        "the index still holds the wording the learner corrected"
    )


def test_deleting_a_note_removes_it_from_the_index(tmp_path, monkeypatch):
    record = _patch_vector_store(monkeypatch)
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _profile(client)
        note_id = _note(client, profile_id)

        removed = client.delete(f"/api/v1/profiles/{profile_id}/notes/{note_id}")
        assert removed.status_code == 200, removed.text

    assert record.deleted == [note_id], "a deleted note is still quotable as a source"


def test_a_title_only_edit_still_refreshes_the_entry(tmp_path, monkeypatch):
    """The title is part of what a search matches against."""
    record = _patch_vector_store(monkeypatch)
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = _profile(client)
        note_id = _note(client, profile_id)

        client.patch(
            f"/api/v1/profiles/{profile_id}/notes/{note_id}",
            json={"title": "Dijkstra's shortest path"},
        )

    assert record.indexed[-1][1] == "Dijkstra's shortest path"
