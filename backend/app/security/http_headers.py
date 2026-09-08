"""Response headers that constrain what a browser will do with Atlas's pages.

Defence in depth rather than a fix for a known hole. The app's actual XSS
surface is already narrow -- `react-markdown` runs without `rehype-raw`, so
raw HTML inside a document or a model reply is never rendered, and nothing in
the frontend uses `dangerouslySetInnerHTML`. These headers are what limits the
damage if that ever changes, or if a dependency introduces a sink nobody
noticed.

Deliberately absent: `Strict-Transport-Security`. Atlas is served over plain
HTTP on loopback, and pinning a browser to HTTPS for `localhost` would break
this and every other local app on the same origin for months.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CONTENT_SECURITY_POLICY = "; ".join(
    (
        # Anything not named below may only load from this origin. Since the
        # fonts were brought in-tree there is no external origin left to
        # allow, so this policy names no third party at all.
        "default-src 'self'",
        # The directive that actually stops injected script. No 'unsafe-inline'
        # and no 'unsafe-eval': the built bundle needs neither.
        "script-src 'self'",
        # 'unsafe-inline' is required here and is not a meaningful weakness:
        # style injection cannot execute script, and both Tailwind's runtime
        # and KaTeX set inline styles.
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        # data: for inlined icons, blob: for canvas exports and object URLs.
        "img-src 'self' data: blob:",
        # Same-origin only. The API and the chat WebSocket are both served
        # from this origin; provider APIs are called from the server, never
        # from the browser.
        "connect-src 'self'",
        # No Flash, no Java, no <embed>. Nothing legitimate uses these.
        "object-src 'none'",
        # Stops injected markup from retargeting every relative URL.
        "base-uri 'self'",
        # Forms may only post back to Atlas.
        "form-action 'self'",
        # The modern replacement for X-Frame-Options; both are sent because
        # frame-ancestors is ignored by some older browsers.
        "frame-ancestors 'none'",
    )
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    # Stops a browser from second-guessing a declared Content-Type -- the
    # mechanism behind "uploaded .txt gets executed as script".
    "X-Content-Type-Options": "nosniff",
    # Nothing should embed Atlas in a frame, so clickjacking has no surface.
    "X-Frame-Options": "DENY",
    # A local-first app should never announce its URLs to anywhere else.
    "Referrer-Policy": "no-referrer",
    # Atlas asks for none of these; deny them so injected content cannot ask
    # on its behalf.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the headers above to every response.

    Existing values are never overwritten, so a specific route can opt out of
    one of these by setting it itself.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
