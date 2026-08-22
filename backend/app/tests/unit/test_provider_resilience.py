"""Regression tests for AI provider retry/backoff and credential-safe errors.

Covers the two failure modes that made chat unusable:
  * a single transient 503/429 from the provider killed the whole turn;
  * the raw httpx error (which embeds the API key in the URL for Gemini) was
    forwarded to the browser and written to the logs.
"""

from __future__ import annotations

import httpx
import pytest

from app.models.abstraction import ChatMessage
from app.models.anthropic_client import AnthropicClient
from app.models.gemini_client import GeminiClient
from app.models.openai_client import OpenAIClient
from app.models.resilience import ProviderError, backoff_delay, sanitize_provider_text

# Bound before the autouse fixture stubs the module attribute, so the real
# backoff curve can still be asserted.
_real_backoff_delay = backoff_delay

FAKE_KEY = "AQ.Ab8RN6KItestkeyvalue1234567890"

OPENAI_OK = {
    "choices": [{"message": {"content": "hello"}}],
    "model": "gpt-4o",
    "usage": {},
}
GEMINI_OK = {
    "candidates": [{"content": {"parts": [{"text": "hello"}]}}],
    "usageMetadata": {},
}
OPENAI_SSE = (
    b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
    b"data: [DONE]\n\n"
)
GEMINI_SSE = b'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}\n\n'


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """Keep retry tests fast; the delay itself is covered by test_backoff_delay."""
    for target in (
        "app.models.resilience.backoff_delay",
        "app.models.openai_client.backoff_delay",
        "app.models.gemini_client.backoff_delay",
        "app.models.anthropic_client.backoff_delay",
    ):
        monkeypatch.setattr(target, lambda *args, **kwargs: 0.0)


def _scripted_transport(responses: list[httpx.Response], seen: list[httpx.Request]):
    """MockTransport that replays `responses` in order, recording each request."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen) - 1, len(responses) - 1)]

    return httpx.MockTransport(handler)


def _install(client, responses, seen):
    """Swap the client's real AsyncClient for a scripted one, keeping headers."""
    original = client._client
    client._client = httpx.AsyncClient(
        base_url=original.base_url,
        headers=original.headers,
        transport=_scripted_transport(responses, seen),
    )
    return client


async def _collect_stream(client) -> str:
    """Drain a chat_stream to its done chunk, closing the generator properly."""
    stream = client.chat_stream([ChatMessage(role="user", content="hi")])
    parts: list[str] = []
    try:
        async for chunk in stream:
            if chunk.done:
                break
            parts.append(chunk.content)
    finally:
        await stream.aclose()
    return "".join(parts)


# ── Retry on transient failures ───────────────────────────────────────


async def test_chat_complete_retries_transient_503_then_succeeds():
    seen: list[httpx.Request] = []
    client = _install(
        OpenAIClient(api_key="sk-test", base_url="https://example.test/v1"),
        [
            httpx.Response(503, json={"error": {"message": "overloaded"}}),
            httpx.Response(503, json={"error": {"message": "overloaded"}}),
            httpx.Response(200, json=OPENAI_OK),
        ],
        seen,
    )
    try:
        result = await client.chat_complete([ChatMessage(role="user", content="hi")])
    finally:
        await client.close()

    assert result.content == "hello"
    assert len(seen) == 3, "expected two retries before the successful attempt"


async def test_chat_stream_retries_when_stream_never_started():
    seen: list[httpx.Request] = []
    client = _install(
        OpenAIClient(api_key="sk-test", base_url="https://example.test/v1"),
        [
            httpx.Response(429, json={"error": {"message": "rate limited"}}),
            httpx.Response(200, content=OPENAI_SSE),
        ],
        seen,
    )
    try:
        text = await _collect_stream(client)
    finally:
        await client.close()

    assert text == "Hello"
    assert len(seen) == 2


async def test_gemini_stream_retries_transient_503():
    """The exact reproduction: Gemini 503 on a streaming turn must not end it."""
    seen: list[httpx.Request] = []
    client = _install(
        GeminiClient(api_key=FAKE_KEY, default_model="gemini-3.7-flash"),
        [httpx.Response(503, text="overloaded"), httpx.Response(200, content=GEMINI_SSE)],
        seen,
    )
    try:
        text = await _collect_stream(client)
    finally:
        await client.close()

    assert text == "Hello"
    assert len(seen) == 2


async def test_retries_are_bounded_and_raise_provider_error():
    seen: list[httpx.Request] = []
    client = _install(
        OpenAIClient(api_key="sk-test", base_url="https://example.test/v1"),
        [httpx.Response(503, text="overloaded")],
        seen,
    )
    try:
        with pytest.raises(ProviderError) as excinfo:
            await client.chat_complete([ChatMessage(role="user", content="hi")])
    finally:
        await client.close()

    assert excinfo.value.status_code == 503
    assert len(seen) == 4, "should stop after DEFAULT_MAX_ATTEMPTS"


async def test_non_retryable_status_fails_immediately():
    seen: list[httpx.Request] = []
    client = _install(
        OpenAIClient(api_key="sk-test", base_url="https://example.test/v1"),
        [httpx.Response(401, json={"error": {"message": "invalid key"}})],
        seen,
    )
    try:
        with pytest.raises(ProviderError) as excinfo:
            await client.chat_complete([ChatMessage(role="user", content="hi")])
    finally:
        await client.close()

    assert excinfo.value.status_code == 401
    assert excinfo.value.retryable is False
    assert len(seen) == 1, "auth failures must not be retried"
    assert "Settings page" in excinfo.value.message


class _DropsMidStream(httpx.AsyncByteStream):
    """Emits one complete SSE event, then drops the connection."""

    def __init__(self, prefix: bytes) -> None:
        self._prefix = prefix

    async def __aiter__(self):
        yield self._prefix
        raise httpx.ReadError("connection dropped mid-stream")


async def test_stream_does_not_retry_after_tokens_were_emitted():
    """Retrying mid-stream would duplicate the answer, so it must not happen."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_DropsMidStream(b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'),
        )

    client = OpenAIClient(api_key="sk-test", base_url="https://example.test/v1")
    client._client = httpx.AsyncClient(
        base_url="https://example.test/v1", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(ProviderError):
            await _collect_stream(client)
    finally:
        await client.close()

    assert len(seen) == 1, "a partially-delivered answer must not be re-requested"


# ── Credential safety ─────────────────────────────────────────────────


async def test_gemini_sends_key_in_header_not_query_string():
    seen: list[httpx.Request] = []
    client = _install(
        GeminiClient(api_key=FAKE_KEY, default_model="gemini-3.7-flash"),
        [httpx.Response(200, json=GEMINI_OK)],
        seen,
    )
    try:
        await client.chat_complete([ChatMessage(role="user", content="hi")])
    finally:
        await client.close()

    request = seen[0]
    assert FAKE_KEY not in str(request.url)
    assert "key=" not in str(request.url)
    assert request.headers["x-goog-api-key"] == FAKE_KEY


@pytest.mark.parametrize(
    "client_factory",
    [
        lambda: GeminiClient(api_key=FAKE_KEY, default_model="m"),
        lambda: OpenAIClient(api_key="sk-testkeyvalue1234567890", base_url="https://example.test/v1"),
        lambda: AnthropicClient(api_key="sk-ant-testkeyvalue123456", default_model="m"),
    ],
    ids=["gemini", "openai", "anthropic"],
)
async def test_provider_errors_never_expose_the_api_key(client_factory):
    seen: list[httpx.Request] = []
    client = _install(client_factory(), [httpx.Response(400, text="bad request")], seen)
    try:
        with pytest.raises(ProviderError) as excinfo:
            await client.chat_complete([ChatMessage(role="user", content="hi")])
    finally:
        await client.close()

    message = excinfo.value.message
    assert client.api_key not in message
    assert "REDACTED" not in message, "no key should have reached the message at all"


def test_sanitize_provider_text_redacts_keys_and_tokens():
    leaked = (
        "Server error '503' for url "
        "'https://generativelanguage.googleapis.com/v1beta/models/m:streamGenerateContent"
        f"?alt=sse&key={FAKE_KEY}'"
    )
    cleaned = sanitize_provider_text(leaked)
    assert FAKE_KEY not in cleaned
    assert "***REDACTED***" in cleaned
    # The rest of the diagnostic must survive so the error stays useful.
    assert "503" in cleaned

    assert "sk-proj-ABCDEFGHIJKL" not in sanitize_provider_text(
        "Authorization: Bearer sk-proj-ABCDEFGHIJKL"
    )
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWX" not in sanitize_provider_text(
        '{"x-goog-api-key": "AIzaSyABCDEFGHIJKLMNOPQRSTUVWX"}'
    )


def test_backoff_delay_grows_and_is_capped():
    from app.models.resilience import DEFAULT_MAX_DELAY

    assert 0.5 <= _real_backoff_delay(0) <= 1.0
    assert 1.0 <= _real_backoff_delay(1) <= 2.0
    assert _real_backoff_delay(20) <= DEFAULT_MAX_DELAY
