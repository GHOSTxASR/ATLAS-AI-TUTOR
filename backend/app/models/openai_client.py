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


class OpenAIClient(BaseModelClient):
    """OpenAI-compatible chat client using raw httpx (works with OpenAI, Azure, any compatible API)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
        return {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
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
            messages, model=model, temperature=temperature, max_tokens=max_tokens, stream=False
        )

        async def _request() -> dict:
            resp = await self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()

        data = await retry_async(_request, provider=self.get_provider_name())
        return ChatResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            finish_reason=str(data["choices"][0].get("finish_reason") or ""),
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
        provider = self.get_provider_name()

        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            produced = False
            try:
                async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
                    await raise_for_stream_status(resp, provider)
                    async with aclosing(resp.aiter_lines()) as lines:
                        async for line in lines:
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk["choices"][0].get("delta", {}).get("content", "")
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                            if content:
                                produced = True
                                yield StreamChunk(content=content, done=False)
            except Exception as exc:
                error = provider_error_from(exc, provider)
                # Once tokens have reached the caller a retry would duplicate
                # the answer, so only retry a stream that never produced output.
                if produced or not error.retryable or attempt == DEFAULT_MAX_ATTEMPTS - 1:
                    raise error from None
                delay = retry_after_seconds(exc) or backoff_delay(attempt)
                logger.warning(
                    "%s stream failed (%s); retrying in %.1fs [attempt %d/%d]",
                    provider,
                    error.message,
                    delay,
                    attempt + 1,
                    DEFAULT_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            yield StreamChunk(content="", done=True)
            return

        raise ProviderError("Stream could not be established.", provider=provider)

    async def close(self) -> None:
        await self._client.aclose()

    def get_provider_name(self) -> str:
        return "openai"
