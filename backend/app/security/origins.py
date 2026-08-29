"""Which browser origins may talk to this server.

One source of truth, because three separate places need the same answer and
they must not drift apart:

* the CORS middleware, which governs what a browser will *read* back;
* the Origin check on state-changing requests, which governs what a browser
  may *cause*;
* the WebSocket handshake, which CORS does not cover at all.

**Any loopback origin is accepted, on any port.** Not laziness -- it is both
safer and more correct than an allowlist of specific ports:

* The attack being stopped is a page on the open internet
  (``https://evil.example``) driving this API in the user's browser. That
  origin is not loopback and is refused whatever port it names.
* Anything already running on this machine's loopback interface could read
  ``~/.atlas`` off disk directly. Refusing its ``Origin`` header protects
  nothing.
* Pinning to the configured port breaks the app whenever the runtime port
  differs from it -- ``uvicorn --port 8400`` without a matching
  ``ATLAS_PORT``, a port picked to dodge a collision, a reverse proxy. A
  build that blocks its own interface gets the whole check switched off.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.config import Settings

#: The only non-IP hostname that means "this machine". Matched exactly: a
#: prefix or substring test would accept ``localhost.evil.example``, a domain
#: anyone can register.
_LOOPBACK_HOSTNAME = "localhost"

#: Only these schemes are loopback-trustworthy. Notably excludes ``file://``
#: and sandboxed iframes, both of which present themselves as ``null``.
_LOCAL_SCHEMES = frozenset({"http", "https", "ws", "wss"})

#: Matches any loopback origin for Starlette's CORS middleware, which cannot
#: take a predicate. Anchored at both ends -- without the trailing anchor,
#: ``http://127.0.0.1.evil.example`` would match. Kept in step with
#: ``is_loopback_origin`` by a test that runs both over the same cases.
LOOPBACK_ORIGIN_REGEX = (
    r"^https?://(localhost|127(\.\d{1,3}){3}|\[::1\])(:\d+)?$"
)


def is_loopback_origin(origin: str) -> bool:
    """Whether an ``Origin`` header value refers to this machine."""
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in _LOCAL_SCHEMES:
        return False
    # `hostname` lowercases and strips brackets from IPv6 literals, and is
    # exact -- unlike `netloc`, which still carries the port.
    hostname = parts.hostname
    if hostname is None:
        return False
    if hostname == _LOOPBACK_HOSTNAME:
        return True
    # Parsed as an address rather than pattern-matched, so
    # `127.0.0.1.evil.example` is a hostname that fails to parse rather than a
    # string that happens to start with "127.". Covers all of 127.0.0.0/8 and
    # IPv6 ::1.
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def allowed_origins(settings: Settings) -> list[str]:
    """Explicit origins for CORS, alongside the loopback regex.

    The regex does the real work; these are the two spellings a browser is
    most likely to use, listed so the configuration reads clearly.
    """
    return sorted(
        {
            f"http://localhost:{settings.server.port}",
            f"http://127.0.0.1:{settings.server.port}",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
    )


def is_allowed_origin(origin: str | None, settings: Settings) -> bool:
    """Whether a browser-supplied ``Origin`` header should be trusted.

    A missing Origin is allowed. Browsers always send one on the cross-origin
    requests this is meant to stop -- including form posts and WebSocket
    handshakes -- so absence means the caller is not a browser doing something
    cross-origin. It is curl, a test client, or a same-origin request in a
    browser that omits the header, and rejecting those would break real use
    while blocking no attack.

    ``settings`` is unused today but kept in the signature: every caller
    already holds it, and a future setting to widen this (a reverse proxy's
    origin, say) belongs here rather than in a new function.
    """
    if origin is None:
        return True
    return is_loopback_origin(origin)
