"""Application logging setup with mandatory credential redaction.

Roughly forty call sites across the services interpolate raw exceptions into
log messages, and third-party libraries (uvicorn, httpx, chromadb) log request
URLs we do not control. Rather than trusting every one of those sites, the
redaction happens once here, at the formatter, so *no* log line can carry an
API key regardless of who emitted it.
"""

from __future__ import annotations

import logging

from app.security.redaction import redact_secrets

DEFAULT_FORMAT = "%(levelname)s [%(name)s] %(message)s"

# Third-party loggers that attach their own handlers and therefore need the
# redacting formatter applied explicitly.
_THIRD_PARTY_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "httpx",
    "httpcore",
    "chromadb",
    "apscheduler",
)


class RedactingFormatter(logging.Formatter):
    """Formatter that scrubs credentials from the fully rendered log line.

    Wrapping ``format`` (rather than filtering ``record.msg``) means exception
    tracebacks and ``%``-interpolated arguments are covered too.
    """

    def __init__(self, inner: logging.Formatter | None = None) -> None:
        super().__init__(DEFAULT_FORMAT)
        self._inner = inner

    def format(self, record: logging.LogRecord) -> str:
        rendered = self._inner.format(record) if self._inner else super().format(record)
        return redact_secrets(rendered)


def _wrap_handler(handler: logging.Handler) -> None:
    if isinstance(handler.formatter, RedactingFormatter):
        return
    handler.setFormatter(RedactingFormatter(handler.formatter))


def install_redaction() -> None:
    """Apply the redacting formatter to every handler currently installed."""
    for handler in logging.getLogger().handlers:
        _wrap_handler(handler)
    for name in _THIRD_PARTY_LOGGERS:
        for handler in logging.getLogger(name).handlers:
            _wrap_handler(handler)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging and guarantee credential redaction."""
    logging.basicConfig(level=level.upper(), format=DEFAULT_FORMAT)
    logging.getLogger().setLevel(level.upper())
    install_redaction()
