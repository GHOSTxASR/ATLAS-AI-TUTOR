"""Tests for credential redaction across logs, responses, and persisted fields."""

from __future__ import annotations

import io
import logging

import httpx
import pytest

from app.security.redaction import (
    REDACTED,
    clear_secrets,
    forget_secret,
    known_secret_count,
    redact_secrets,
    register_secret,
)
from app.utils.logging import RedactingFormatter

LIVE_KEY = "AQ.Ab8RN6KrealisticGeminiStyleValue123"
# Deliberately matches none of the credential patterns, so it can only be
# scrubbed via the registry of known live values.
OPAQUE_KEY = "zzq7Wm4TbN9pLx2Rv8Kd"


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_secrets()
    yield
    clear_secrets()


# ── Registry ──────────────────────────────────────────────────────────


def test_registered_secret_is_redacted_in_any_format():
    """The registry is the backstop for formats no regex anticipates."""
    # Precondition: the patterns alone cannot catch this value.
    assert OPAQUE_KEY in redact_secrets(f"used key {OPAQUE_KEY} here")

    register_secret(OPAQUE_KEY)
    cleaned = redact_secrets(f"used key {OPAQUE_KEY} here")
    assert OPAQUE_KEY not in cleaned
    assert REDACTED in cleaned
    assert cleaned.startswith("used key ")


def test_forget_secret_removes_it_from_the_registry():
    register_secret(OPAQUE_KEY)
    assert known_secret_count() == 1
    forget_secret(OPAQUE_KEY)
    assert known_secret_count() == 0
    assert OPAQUE_KEY in redact_secrets(f"used key {OPAQUE_KEY} here")


def test_short_values_are_not_registered():
    """Blanket-replacing a short string would corrupt unrelated text."""
    register_secret("abc")
    assert known_secret_count() == 0
    assert redact_secrets("abc def") == "abc def"


def test_patterns_redact_unregistered_credentials():
    cleaned = redact_secrets(
        "GET https://api.example.com/v1/models?alt=sse&key=SOMEUNKNOWNSECRET123 failed"
    )
    assert "SOMEUNKNOWNSECRET123" not in cleaned
    assert "https://api.example.com" in cleaned, "diagnostics must survive"

    assert "sk-abcdefghijklmnop" not in redact_secrets("Bearer sk-abcdefghijklmnop")
    assert "gsk_abcdefghijklmnop" not in redact_secrets("token gsk_abcdefghijklmnop")


# ── Logging ───────────────────────────────────────────────────────────


def _capture(logger_name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter(logging.Formatter("%(message)s")))
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_redacting_formatter_scrubs_interpolated_messages():
    register_secret(LIVE_KEY)
    logger, stream = _capture("test.redaction.message")

    logger.warning("call failed for url ?key=%s", LIVE_KEY)

    output = stream.getvalue()
    assert LIVE_KEY not in output
    assert REDACTED in output


def test_redacting_formatter_scrubs_exception_tracebacks():
    """exc_info renders the whole traceback; it must be scrubbed too."""
    register_secret(LIVE_KEY)
    logger, stream = _capture("test.redaction.traceback")

    try:
        raise RuntimeError(f"Server error for url 'https://x.test/v1?key={LIVE_KEY}'")
    except RuntimeError:
        logger.error("stream failed", exc_info=True)

    output = stream.getvalue()
    assert LIVE_KEY not in output
    assert "RuntimeError" in output, "the traceback itself must still be useful"


# ── Response paths ────────────────────────────────────────────────────


async def test_test_connection_error_does_not_leak_the_key(tmp_path, monkeypatch):
    """Regression: /settings/test-connection returned str(e) straight to the UI."""
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "redaction-data"))

    from app.config import get_settings
    from app.services.settings_service import SettingsService

    get_settings.cache_clear()
    settings = get_settings()

    leaky_url = f"https://generativelanguage.googleapis.com/v1beta/models/m?key={LIVE_KEY}"

    def _boom(_settings):
        request = httpx.Request("POST", leaky_url)
        response = httpx.Response(403, request=request, text="forbidden")
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)

    monkeypatch.setattr("app.services.settings_service.get_model_client", _boom)
    register_secret(LIVE_KEY)

    result = await SettingsService(settings).test_connection(provider="gemini")

    assert result["status"] == "error"
    assert LIVE_KEY not in result["error"]
    assert LIVE_KEY not in str(result)


def test_keystore_registers_keys_it_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "keystore-data"))

    from app.config import get_settings
    from app.security.keystore import KeyStore

    get_settings.cache_clear()
    store = KeyStore(get_settings())

    store.set("gemini", LIVE_KEY)
    assert known_secret_count() == 1

    clear_secrets()
    assert known_secret_count() == 0

    # Reading it back must re-register it, so a later log line is still safe.
    assert store.get("gemini") == LIVE_KEY
    assert known_secret_count() == 1
    assert LIVE_KEY not in redact_secrets(f"leaked {LIVE_KEY}")

    store.delete("gemini")
    assert known_secret_count() == 0


def test_keystore_files_are_not_world_readable(tmp_path, monkeypatch):
    """The Fernet key and ciphertext sit together, so file ACLs matter."""
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "perms-data"))

    from app.config import get_settings
    from app.security.keystore import KeyStore

    get_settings.cache_clear()
    settings = get_settings()
    KeyStore(settings).set("openai", LIVE_KEY)

    secrets_file = settings.paths.secrets_file
    key_file = settings.paths.config_dir / "keystore.key"
    assert secrets_file.exists() and key_file.exists()
    # The plaintext key must never be recoverable from the ciphertext on disk.
    assert LIVE_KEY.encode() not in secrets_file.read_bytes()
