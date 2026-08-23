from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

import httpx

from app.security.redaction import redact_secrets

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient conditions worth retrying. 429 (rate limited) and the 5xx family
# ("model overloaded") are what providers actually return under free-tier load,
# and a single un-retried blip is enough to kill a whole chat turn.
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 16.0

_MAX_DETAIL_CHARS = 200

# Hand-written explanations keep provider errors actionable without echoing
# whatever the provider happened to put in its response body.
_STATUS_MESSAGES: dict[int, str] = {
    400: "The AI provider rejected the request. The selected model may not be valid for this provider.",
    401: "The AI provider rejected the API key. Re-enter it on the Settings page.",
    403: "This API key is not authorised for the selected model. Check your provider plan.",
    404: "The AI provider has no model by that name. Choose a different model on the Settings page.",
    408: "The AI provider timed out. Try again.",
    413: "The request was too large for this model's context window.",
    422: "The AI provider rejected the request payload.",
    429: "The AI provider is rate limiting this API key. Wait a moment and try again.",
    500: "The AI provider hit an internal error. Try again.",
    502: "The AI provider is unreachable right now. Try again.",
    503: "The AI provider is overloaded right now. Try again in a moment.",
    504: "The AI provider timed out. Try again.",
}


def sanitize_provider_text(text: str) -> str:
    """Strip API keys and bearer tokens out of provider-derived text.

    Thin alias over :func:`app.security.redaction.redact_secrets` so callers in
    the models layer do not need to reach into the security package.
    """
    return redact_secrets(text)


class ProviderError(RuntimeError):
    """An AI provider failure carrying a message that is safe to show a user.

    Raw ``httpx`` errors embed the full request URL, which for key-in-query
    providers means the API key itself. Clients raise this instead, so callers
    can surface ``message`` directly without leaking credentials.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


def _response_detail(response: httpx.Response) -> str:
    """Extract a short, sanitized explanation from a provider error body."""
    try:
        body = response.text
    except Exception:
        # Streaming responses raise ResponseNotRead until the body is awaited.
        return ""
    if not body:
        return ""

    detail: object = body
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or error.get("type") or detail
        elif isinstance(error, str):
            detail = error
        elif "message" in payload:
            detail = payload["message"]

    collapsed = " ".join(str(detail).split())
    return _clip(sanitize_provider_text(collapsed))


def _clip(text: str) -> str:
    """Cut over-long provider detail at a word boundary, with an ellipsis.

    A hard slice lands mid-word -- users were shown "To monitor your current
    usa", which reads like the app mangled the message rather than shortened
    it.
    """
    if len(text) <= _MAX_DETAIL_CHARS:
        return text
    cut = text[:_MAX_DETAIL_CHARS]
    spaced = cut.rsplit(" ", 1)[0]
    # Only prefer the word boundary when it does not throw away real content.
    if len(spaced) >= _MAX_DETAIL_CHARS * 0.6:
        cut = spaced
    return cut.rstrip(" ,.;:") + "…"


def provider_error_from(exc: BaseException, provider: str = "") -> ProviderError:
    """Normalise any transport/HTTP failure into a credential-free ProviderError."""
    if isinstance(exc, ProviderError):
        return exc

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        message = _STATUS_MESSAGES.get(status, f"The AI provider returned HTTP {status}.")
        detail = _response_detail(exc.response)
        if detail:
            message = f"{message} ({detail})"
        return ProviderError(
            message,
            provider=provider,
            status_code=status,
            retryable=status in RETRYABLE_STATUS_CODES,
        )

    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(
            "The AI provider did not respond in time. Try again.",
            provider=provider,
            retryable=True,
        )

    if isinstance(exc, httpx.RequestError):
        return ProviderError(
            "Could not reach the AI provider. Check your network connection.",
            provider=provider,
            retryable=True,
        )

    return ProviderError(
        sanitize_provider_text(str(exc)) or "Unknown AI provider error.",
        provider=provider,
    )


def backoff_delay(
    attempt: int,
    *,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> float:
    """Exponential backoff with equal jitter. ``attempt`` is 0-based."""
    ceiling = min(max_delay, base_delay * (2**attempt))
    half = ceiling / 2.0
    return half + random.uniform(0.0, half)


def retry_after_seconds(exc: BaseException) -> float | None:
    """Honour a provider's ``Retry-After`` header when it sends one."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    raw = exc.response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, min(float(raw), DEFAULT_MAX_DELAY))
    except (TypeError, ValueError):
        return None


async def raise_for_stream_status(response: httpx.Response, provider: str = "") -> None:
    """Raise a sanitized ProviderError if a streaming response failed.

    The body is read first so the provider's own explanation can be included;
    ``response.text`` would otherwise raise ``ResponseNotRead``.
    """
    if response.status_code < 400:
        return
    try:
        await response.aread()
    except Exception:
        logger.debug(
            "Could not read error body from %s stream.", provider or "provider", exc_info=True
        )
    raise provider_error_from(
        httpx.HTTPStatusError(
            f"HTTP {response.status_code}",
            request=response.request,
            response=response,
        ),
        provider,
    )


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    provider: str = "",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> T:
    """Run ``operation``, retrying transient provider failures with backoff.

    Always raises :class:`ProviderError` rather than a raw ``httpx`` error, so
    no caller can accidentally surface a URL containing the API key.
    """
    last_error: ProviderError | None = None
    for attempt in range(max_attempts):
        try:
            return await operation()
        except Exception as exc:
            error = provider_error_from(exc, provider)
            last_error = error
            if not error.retryable or attempt == max_attempts - 1:
                raise error from None
            delay = retry_after_seconds(exc) or backoff_delay(attempt)
            logger.warning(
                "%s request failed (%s); retrying in %.1fs [attempt %d/%d]",
                provider or "provider",
                error.message,
                delay,
                attempt + 1,
                max_attempts,
            )
            await asyncio.sleep(delay)

    raise last_error or ProviderError("AI provider request failed.", provider=provider)
