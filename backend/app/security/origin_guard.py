"""Reject state-changing requests that a browser marks as cross-origin.

CORS already stops another site *reading* Atlas's responses, but it does not
stop the request being made. A form on an attacker's page can still POST to
`http://127.0.0.1:8000/...` as a "simple request", no preflight involved --
the browser blocks the attacker from seeing the reply, but the write has
already happened. That is the whole shape of a CSRF attack, and Atlas has no
per-request token to fall back on because it has no login.

Most of Atlas's endpoints take a JSON body, which forces a preflight and is
therefore already protected. The two that accept `multipart/form-data`
(document upload and profile import) are exactly the shape a form can produce,
so they were reachable this way. This closes that without a token scheme.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.security.origins import is_allowed_origin

logger = logging.getLogger(__name__)

#: Methods that can change something. GET/HEAD/OPTIONS are excluded: they are
#: meant to be side-effect free, and Atlas has no state-changing GET routes.
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Block cross-origin writes from a browser.

    Only acts when the browser actually declares a foreign origin. A request
    with no `Origin` header is left alone -- see `is_allowed_origin` for why
    that is safe rather than a bypass.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if not is_allowed_origin(origin, get_settings()):
                logger.warning(
                    "Blocked cross-origin %s %s from origin %r",
                    request.method,
                    request.url.path,
                    origin,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "data": None,
                        "error": {
                            "code": "CROSS_ORIGIN_BLOCKED",
                            "message": (
                                "This request came from another site and was blocked. "
                                "Atlas only accepts requests from its own interface."
                            ),
                            "details": {},
                        },
                        "meta": None,
                    },
                )
        return await call_next(request)
