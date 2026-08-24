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


class OllamaClient(BaseModelClient):
    """Ollama local model client. Communicates with a locally running Ollama server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.1",
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None,
        temperature: float,
        stream: bool,
    ) -> dict:
        return {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": {"temperature": temperature},
        }

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        payload = self._build_payload(
            messages, model=model, temperature=temperature, stream=False
        )

        async def _request() -> dict:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

        data = await retry_async(_request, provider="ollama")
        return ChatResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", ""),
            finish_reason=str(data.get("done_reason") or ""),
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
            messages, model=model, temperature=temperature, stream=True
        )
        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            produced = False
            try:
                async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                    await raise_for_stream_status(resp, "ollama")
                    async with aclosing(resp.aiter_lines()) as lines:
                        async for line in lines:
                            if not line.strip():
                                continue
                            try:
                                data = json.loads(line)
                                done = bool(data.get("done"))
                                content = data.get("message", {}).get("content", "")
                            except (json.JSONDecodeError, KeyError):
                                continue
                            if done:
                                break
                            if content:
                                produced = True
                                yield StreamChunk(content=content, done=False)
            except Exception as exc:
                error = provider_error_from(exc, "ollama")
                # Once tokens have reached the caller a retry would duplicate
                # the answer, so only retry a stream that never produced output.
                if produced or not error.retryable or attempt == DEFAULT_MAX_ATTEMPTS - 1:
                    raise error from None
                delay = retry_after_seconds(exc) or backoff_delay(attempt)
                logger.warning(
                    "ollama stream failed (%s); retrying in %.1fs [attempt %d/%d]",
                    error.message,
                    delay,
                    attempt + 1,
                    DEFAULT_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            yield StreamChunk(content="", done=True)
            return

        raise ProviderError("Ollama stream could not be established.", provider="ollama")

    async def close(self) -> None:
        await self._client.aclose()

    def get_provider_name(self) -> str:
        return "ollama"
