from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.config import ensure_data_directories, get_settings, project_root
from app.db.database import close_database, init_database
from app.models.provider_factory import register_known_secrets
from app.tasks.background import drain as drain_background_tasks
from app.tasks.document_pipeline_task import resume_interrupted_documents
from app.tasks.scheduler import shutdown_scheduler, start_scheduler
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def run_migrations(db_url: str):
    backend_dir = project_root() / "backend"
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    # The app configures its own logging (including credential redaction);
    # alembic must not reconfigure it when invoked in-process.
    alembic_cfg.attributes["configure_logger"] = False
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        settings = get_settings()
        # Re-apply after uvicorn installs its own handlers, so every logger in
        # the process (ours and third-party) redacts credentials.
        configure_logging(settings.server.log_level)
        ensure_data_directories(settings)
        # Load configured API keys into the redaction registry before anything
        # has a chance to log one.
        register_known_secrets(settings)
        await init_database(settings)
        app.state.settings = settings

        # Run Alembic migrations automatically on startup
        db_url = f"sqlite:///{(settings.paths.sqlite_dir / 'learningos.db').as_posix()}"
        await asyncio.to_thread(run_migrations, db_url)

        # Start background task scheduler
        start_scheduler()

        # Pick up documents a previous run left mid-processing; without this
        # an interrupted upload would sit at "pending" indefinitely.
        try:
            await resume_interrupted_documents()
        except Exception:
            logger.warning("Could not resume interrupted documents.", exc_info=True)
    except Exception:
        logger.exception("Startup failed")
        raise

    yield

    shutdown_scheduler()
    # Let detached work (memory extraction, summaries) finish before the
    # database goes away.
    await drain_background_tasks()
    await close_database()
