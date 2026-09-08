"""Browser-facing defences: security headers, and the Origin checks around them.

Atlas has no login. Its access control is "only this machine can reach it",
which holds for reading, because CORS stops another site seeing a response.
It does not by itself hold for *writing*: a form on an attacker's page can
still POST to `http://127.0.0.1:8000/...` as a simple request, and a
WebSocket handshake is not covered by CORS at all.

These pin the two guards that close that, plus the response headers that limit
what a browser will do with an Atlas page.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

HOSTILE = "https://evil.example"
ALLOWED = "http://localhost:5173"


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "browser-security-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def _profile_payload() -> dict[str, str]:
    return {"name": "Origin Test", "profile_type": "Custom Learning"}


# ── Security headers ──────────────────────────────────────────────────


def test_security_headers_present_on_api_responses(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "content-security-policy" in response.headers


def test_csp_blocks_the_directives_that_matter(tmp_path, monkeypatch):
    """script-src and object-src are what actually stop injected code running."""
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        csp = client.get("/api/v1/health").headers["content-security-policy"]

    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'self'" in csp
    # The whole point of script-src would be lost with either of these.
    assert "'unsafe-eval'" not in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp


def test_csp_still_permits_the_interfaces_own_resources(tmp_path, monkeypatch):
    """A policy that breaks the app would just get switched off.

    Both Tailwind's runtime and KaTeX set inline styles, and the API and chat
    WebSocket are both same-origin.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        csp = client.get("/api/v1/health").headers["content-security-policy"]

    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "connect-src 'self'" in csp
    assert "font-src 'self' data:" in csp


def test_csp_names_no_external_origin(tmp_path, monkeypatch):
    """The fonts were brought in-tree precisely so this could be true.

    Atlas claims nothing leaves the machine but calls to the model provider
    you configure. A policy permitting a font CDN would be that claim's one
    standing exception, and a page load telling Google when Atlas ran.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        csp = client.get("/api/v1/health").headers["content-security-policy"]

    # 'self', 'none', 'unsafe-inline', data: -- no scheme-qualified host.
    assert "//" not in csp, f"CSP allows an external origin: {csp}"
    assert "http" not in csp


def test_hsts_is_not_sent(tmp_path, monkeypatch):
    """Atlas is plain HTTP on loopback.

    Sending HSTS would pin the browser to HTTPS for `localhost` -- breaking
    this and every other local app on that origin, for months, with no way for
    the user to undo it easily.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        assert "strict-transport-security" not in client.get("/api/v1/health").headers


# ── Origin guard on state-changing requests ───────────────────────────


def test_cross_origin_post_is_blocked(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/profiles", json=_profile_payload(), headers={"Origin": HOSTILE}
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CROSS_ORIGIN_BLOCKED"

        # And it really did not happen.
        assert client.get("/api/v1/profiles").json()["data"] == []


def test_cross_origin_delete_is_blocked(tmp_path, monkeypatch):
    """Deletes are the most damaging thing a drive-by request could reach."""
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = client.post("/api/v1/profiles", json=_profile_payload()).json()["data"]["id"]

        blocked = client.delete(
            f"/api/v1/profiles/{profile_id}", headers={"Origin": HOSTILE}
        )
        assert blocked.status_code == 403

        # Still there.
        assert client.get(f"/api/v1/profiles/{profile_id}").status_code == 200


def test_cross_origin_multipart_upload_is_blocked(tmp_path, monkeypatch):
    """The endpoint shape a cross-origin form can actually produce.

    JSON endpoints force a preflight and were already protected; the two
    multipart endpoints were not.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = client.post("/api/v1/profiles", json=_profile_payload()).json()["data"]["id"]

        response = client.post(
            f"/api/v1/profiles/{profile_id}/documents",
            files={"file": ("notes.txt", b"some content", "text/plain")},
            headers={"Origin": HOSTILE},
        )

        assert response.status_code == 403
        assert client.get(f"/api/v1/profiles/{profile_id}/documents").json()["data"] == []


def test_same_origin_post_is_allowed(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/profiles", json=_profile_payload(), headers={"Origin": ALLOWED}
        )
        assert response.status_code == 201


def test_post_without_an_origin_header_is_allowed(tmp_path, monkeypatch):
    """curl, native clients, and same-origin browsers that omit the header.

    Browsers always send Origin on the cross-origin requests this guards
    against, so allowing the absent case blocks no attack and avoids breaking
    every non-browser caller.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        assert client.post("/api/v1/profiles", json=_profile_payload()).status_code == 201


def test_cross_origin_get_is_not_blocked(tmp_path, monkeypatch):
    """Reads are left to CORS, which stops the response being read.

    Blocking them here would add nothing and would break legitimate
    same-origin navigation in browsers that label it oddly.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={"Origin": HOSTILE})
        assert response.status_code == 200
        # CORS still refuses to let the caller read it.
        assert response.headers.get("access-control-allow-origin") != HOSTILE


# ── Origin check on the WebSocket ─────────────────────────────────────


def test_websocket_rejects_a_foreign_origin(tmp_path, monkeypatch):
    """Cross-site WebSocket hijacking.

    CORS does not apply to WebSockets, so without this check any page the user
    visits could open a socket to the tutor -- spending their provider credits
    and reading back answers built from their own documents.
    """
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = client.post("/api/v1/profiles", json=_profile_payload()).json()["data"]["id"]
        session_id = client.post(
            f"/api/v1/profiles/{profile_id}/sessions", json={"title": "t"}
        ).json()["data"]["id"]

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect(
                f"/ws/chat/{profile_id}/{session_id}", headers={"Origin": HOSTILE}
            ) as ws:
                ws.receive_text()

        assert excinfo.value.code == 1008


def test_websocket_accepts_the_interfaces_own_origin(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = client.post("/api/v1/profiles", json=_profile_payload()).json()["data"]["id"]
        session_id = client.post(
            f"/api/v1/profiles/{profile_id}/sessions", json={"title": "t"}
        ).json()["data"]["id"]

        # Connecting at all is the assertion; a rejected handshake raises.
        with client.websocket_connect(
            f"/ws/chat/{profile_id}/{session_id}", headers={"Origin": ALLOWED}
        ):
            pass


def test_websocket_without_an_origin_is_accepted(tmp_path, monkeypatch):
    """Non-browser clients, and the existing test suite, send no Origin."""
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        profile_id = client.post("/api/v1/profiles", json=_profile_payload()).json()["data"]["id"]
        session_id = client.post(
            f"/api/v1/profiles/{profile_id}/sessions", json={"title": "t"}
        ).json()["data"]["id"]

        with client.websocket_connect(f"/ws/chat/{profile_id}/{session_id}"):
            pass
