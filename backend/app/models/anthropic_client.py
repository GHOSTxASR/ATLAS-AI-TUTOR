from __future__ import annotations

import asyncio
import json
import logging
from contextlib import aclosing
from typing import AsyncIterator

import httpx

from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.models.resilience import (
    DEFAULT_MAX_ATTEMPTS,
    ProviderError,
    backoff_delay,
    provider_error_from,
    raise_for_stream_status,
    retry_after_seconds,
    retry_async,
)

logger = logging.getLogger(__name__)


class AnthropicClient(BaseModelClient):
    """Anthropic Claude client using raw httpx with streaming support."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        default_model: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict:
        # Extract system message if present
        system_text = ""
        api_messages = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                api_messages.append({"role": m.role, "content": m.content})

        payload: dict = {
            "model": model or self.default_model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        return payload

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        payload = self._build_payload(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, stream=False
        )

        async def _request() -> dict:
            resp = await self._client.post("/v1/messages", json=payload)
            resp.raise_for_status()
            return resp.json()

        data = await retry_async(_request, provider="anthropic")
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        return ChatResponse(
            content=content,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            # Anthropic calls it stop_reason and says "max_tokens".
            finish_reason="length" if data.get("stop_reason") == "max_tokens" else str(data.get("stop_reason") or ""),
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        payload = self._build_payload(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, stream=True
        )
        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            produced = False
            try:
                async with self._client.stream("POST", "/v1/messages", json=payload) as resp:
                    await raise_for_stream_status(resp, "anthropic")
                    async with aclosing(resp.aiter_lines()) as lines:
                        async for line in lines:
                            if not line.startswith("data: "):
                                continue
                            try:
                                event = json.loads(line[6:])
                                event_type = event.get("type", "")
                                text = (
                                    event.get("delta", {}).get("text", "")
                                    if event_type == "content_block_delta"
                                    else ""
                                )
                            except (json.JSONDecodeError, KeyError):
                                continue
                            if event_type == "message_stop":
                                break
                            if text:
                                produced = True
                                yield StreamChunk(content=text, done=False)
            except Exception as exc:
                error = provider_error_from(exc, "anthropic")
                # Once tokens have reached the caller a retry would duplicate
                # the answer, so only retry a stream that never produced output.
                if produced or not error.retryable or attempt == DEFAULT_MAX_ATTEMPTS - 1:
                    raise error from None
                delay = retry_after_seconds(exc) or backoff_delay(attempt)
                logger.warning(
                    "anthropic stream failed (%s); retrying in %.1fs [attempt %d/%d]",
                    error.message,
                    delay,
                    attempt + 1,
                    DEFAULT_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            yield StreamChunk(content="", done=True)
            return

        raise ProviderError("Anthropic stream could not be established.", provider="anthropic")

    async def close(self) -> None:
        await self._client.aclose()

    def get_provider_name(self) -> str:
        return "anthropic"
