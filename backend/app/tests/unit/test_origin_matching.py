"""Which Origin values count as "this machine".

The interesting cases are the near-misses. `localhost.evil.example` is a
domain anyone can register, and a naive substring or prefix test accepts it --
which would hand an attacker exactly the bypass this check exists to prevent.
"""

from __future__ import annotations

import re

import pytest

from app.security.origins import (
    LOOPBACK_ORIGIN_REGEX,
    is_allowed_origin,
    is_loopback_origin,
)


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8400",  # a port that is not the configured one
        "http://localhost",  # no explicit port
        "http://127.0.0.1",
        "https://localhost:8000",  # if someone terminates TLS locally
        "http://[::1]:8000",  # IPv6 loopback
        "http://127.0.0.2:8000",  # the rest of 127.0.0.0/8 is also this machine
        "http://LOCALHOST:8000",  # hostnames are case-insensitive
    ],
)
def test_loopback_origins_are_accepted(origin):
    assert is_loopback_origin(origin) is True


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://evil.example:8000",
        # The bypasses a substring or prefix check would let through.
        "http://localhost.evil.example",
        "http://localhost.evil.example:8000",
        "http://127.0.0.1.evil.example",
        "http://notlocalhost",
        # A public address that merely contains the digits.
        "http://10.127.0.1:8000",
        # Sandboxed iframes and file:// pages present this literal string.
        "null",
        "",
        # Non-web schemes.
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_non_loopback_origins_are_rejected(origin):
    assert is_loopback_origin(origin) is False


def test_absent_origin_is_allowed():
    """curl, native clients, and browsers that omit it on same-origin requests.

    Safe because a browser always sends Origin on the cross-origin requests
    this guards against, so nothing an attacker controls reaches this branch.
    """
    assert is_allowed_origin(None, settings=None) is True


def test_present_but_foreign_origin_is_rejected():
    assert is_allowed_origin("https://evil.example", settings=None) is False


@pytest.mark.parametrize(
    "origin,expected",
    [
        ("http://localhost:5173", True),
        ("http://127.0.0.1:8000", True),
        ("http://127.0.0.2:8000", True),
        ("http://[::1]:8000", True),
        ("http://localhost", True),
        ("https://evil.example", False),
        ("http://localhost.evil.example", False),
        ("http://127.0.0.1.evil.example", False),
        ("http://10.127.0.1:8000", False),
        ("null", False),
    ],
)
def test_cors_regex_agrees_with_the_python_check(origin, expected):
    """The two must not drift.

    Starlette's CORS middleware cannot take a predicate, so the same rule is
    expressed twice -- once in Python for the origin guard and the WebSocket,
    once as a regex for CORS. A disagreement would mean a request the guard
    allows but CORS refuses, or worse, the reverse.
    """
    assert bool(re.match(LOOPBACK_ORIGIN_REGEX, origin)) is expected
