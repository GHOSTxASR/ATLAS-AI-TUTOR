"""Application logging must survive startup.

`alembic/env.py` calls `logging.config.fileConfig()`, whose
`disable_existing_loggers` argument defaults to True. Migrations run during
lifespan startup, so every logger created before that point - effectively the
whole application - was switched off for the life of the process. Provider
errors, retry warnings and background-task failures all went silently missing,
which is exactly the logging you need when something breaks in production.
"""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

# Loggers created at import time, i.e. the ones fileConfig would have disabled.
APP_LOGGERS = (
    "app.main",
    "app.lifespan",
    "app.routers.ws_chat",
    "app.services.tutor_orchestrator",
    "app.tasks.background",
    "app.pipelines.embedder",
)


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "logging-startup-data"))

    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


def test_loggers_are_still_enabled_after_migrations_run(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)

    # Startup (and therefore `alembic upgrade head`) happens on context entry.
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

        disabled = [name for name in APP_LOGGERS if logging.getLogger(name).disabled]
        assert not disabled, f"startup disabled these loggers: {disabled}"

        for name in APP_LOGGERS:
            assert logging.getLogger(name).isEnabledFor(logging.WARNING), name


def test_a_warning_still_reaches_handlers_after_startup(tmp_path, monkeypatch, caplog):
    app = _make_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

        with caplog.at_level(logging.WARNING):
            logging.getLogger("app.tasks.background").warning("post-startup probe")

    assert any("post-startup probe" in r.getMessage() for r in caplog.records)
