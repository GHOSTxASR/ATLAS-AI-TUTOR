"""Central redaction of API keys and tokens.

Two complementary layers:

1. **Pattern matching** catches credential-shaped text (``?key=``, ``Bearer x``,
   ``sk-...``) even for providers this app has never seen.
2. **The secret registry** catches the exact key values this process is holding,
   so a leak in a format no pattern anticipates is still scrubbed. Keys are
   registered as they are resolved for a request.

Every string derived from a provider - error messages, tracebacks, log records,
persisted ``error_message`` columns - must pass through :func:`redact_secrets`
before it is stored, logged, or returned.
"""

from __future__ import annotations

import re
import threading

REDACTED = "***REDACTED***"

# Shortest value worth registering. Below this the "secret" is almost certainly
# a placeholder and blanket-replacing it would corrupt unrelated text.
_MIN_SECRET_LENGTH = 12

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Credentials passed as query parameters (Gemini's historical style).
    re.compile(r"(?i)([?&](?:key|api[-_]?key|access[-_]?token|token)=)[^&\s\"'>]+"),
    # Authorization headers.
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    # Header/JSON key-value forms, e.g. "x-goog-api-key": "...".
    re.compile(r"(?i)((?:x-)?(?:goog-)?api[-_]?key\"?\s*[:=]\s*\"?)[A-Za-z0-9._\-]{8,}"),
    # Well-known provider key prefixes.
    re.compile(r"\b(sk-)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\b(AIza)[A-Za-z0-9._\-]{20,}"),
    re.compile(r"\b(AQ\.)[A-Za-z0-9._\-]{20,}"),
    re.compile(r"\b(gsk_)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\b(xai-)[A-Za-z0-9._\-]{12,}"),
)

_lock = threading.Lock()
_known_secrets: set[str] = set()


def register_secret(value: str | None) -> None:
    """Remember a live credential so it can be scrubbed from any output."""
    if not value:
        return
    candidate = value.strip()
    if len(candidate) < _MIN_SECRET_LENGTH:
        return
    with _lock:
        _known_secrets.add(candidate)


def forget_secret(value: str | None) -> None:
    """Drop a credential from the registry (used when a key is deleted)."""
    if not value:
        return
    with _lock:
        _known_secrets.discard(value.strip())


def clear_secrets() -> None:
    """Empty the registry. Intended for tests."""
    with _lock:
        _known_secrets.clear()


def known_secret_count() -> int:
    """Number of registered secrets. Intended for tests and diagnostics."""
    with _lock:
        return len(_known_secrets)


def redact_secrets(text: str) -> str:
    """Remove known credential values and credential-shaped text."""
    if not text:
        return ""
    cleaned = str(text)

    # Exact known values first: this catches leaks in any format at all.
    with _lock:
        secrets = sorted(_known_secrets, key=len, reverse=True)
    for secret in secrets:
        if secret in cleaned:
            cleaned = cleaned.replace(secret, REDACTED)

    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", cleaned)

    return cleaned
