from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import APP_TAGLINE, get_settings
from app.exceptions import AtlasError
from app.lifespan import lifespan
from app.security.redaction import redact_secrets
from app.utils.file_utils import ensure_within_directory
from app.utils.logging import configure_logging
from app.routers import (
    analytics,
    chat,
    documents,
    graph,
    health,
    memory,
    notes,
    profiles,
    quiz,
    roadmap,
    search,
    settings as settings_router,
    ws_chat,
)


def envelope(data=None, error=None, meta=None):
    return {"data": data, "error": error, "meta": meta}


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.server.log_level)
    app = FastAPI(
        title=settings.app.name,
        description=APP_TAGLINE,
        version=settings.app.version,
        lifespan=lifespan,
    )
    # In production the SPA is served from this same origin, so no cross-origin
    # access is needed at all. Development allows only the Vite dev server.
    # `allow_origins=["*"]` together with `allow_credentials=True` is an invalid
    # combination and would have let any site call this API with cookies.
    dev_origins = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (5173, settings.server.port)
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(set(dev_origins)),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AtlasError)
    async def atlas_error_handler(_: Request, exc: AtlasError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(
                error={
                    "code": exc.code,
                    "message": redact_secrets(exc.message),
                    "details": exc.details,
                }
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return validation failures in the standard envelope.

        FastAPI's default 422 body is `{"detail": [...]}`, which every frontend
        handler misses (they read `error.message`), so invalid input produced a
        silent no-op in the UI.
        """
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = first.get("msg", "Request validation failed.")
        return JSONResponse(
            status_code=422,
            content=envelope(
                error={
                    "code": "VALIDATION_ERROR",
                    "message": f"{field}: {message}" if field else message,
                    "details": {"errors": jsonable_encoder(errors)},
                }
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Wrap framework HTTP errors (404, 405, ...) in the envelope."""
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(
                error={
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "details": {},
                }
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Log the detail, return a generic envelope.

        An unhandled exception's text can carry a request URL (and therefore an
        API key), so it is logged - through the redacting formatter - and never
        echoed to the client.
        """
        logger.exception("Unhandled error handling %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=envelope(
                error={
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong. Check the server logs for details.",
                    "details": {},
                }
            ),
        )

    # Register API Routers first so /api and /ws take priority
    for router in (
        health.router,
        profiles.router,
        documents.router,
        chat.router,
        roadmap.router,
        graph.router,
        memory.router,
        quiz.router,
        analytics.router,
        notes.router,
        search.router,
        settings_router.router,
        ws_chat.router,
    ):
        app.include_router(router)

    # Mount Production SPA frontend if compiled dist directory exists
    project_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if project_frontend_dist.exists():
        assets_dir = project_frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # 1. Direct static file match (e.g. vite.svg, favicon.ico).
            #    `full_path` is attacker-controlled and Starlette does not
            #    normalise ".." for :path converters, so the resolved target
            #    must be confined to dist/ or "/../../.env" would be served.
            if full_path:
                try:
                    target_file = ensure_within_directory(
                        project_frontend_dist, project_frontend_dist / full_path
                    )
                except (ValueError, OSError):
                    target_file = None
                if target_file is not None and target_file.is_file():
                    return FileResponse(str(target_file))
            # 2. API paths must never fall through to the SPA shell. Returning
            #    index.html for an unknown /api route gave callers HTTP 200
            #    with HTML, so a typo'd or removed endpoint surfaced as
            #    `undefined` data instead of an error.
            if full_path.startswith("api/") or full_path == "api":
                return JSONResponse(
                    status_code=404,
                    content=envelope(
                        error={
                            "code": "NOT_FOUND",
                            "message": f"No API endpoint at /{full_path}",
                            "details": {},
                        }
                    ),
                )

            # 3. SPA client-side routing fallback to index.html
            index_file = project_frontend_dist / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))
            return envelope({"name": settings.app.name, "status": "ok", "docs": "/docs"})
    else:
        @app.get("/")
        async def root():
            return envelope({"name": settings.app.name, "status": "ok", "docs": "/docs"})

    return app


app = create_app()
