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


class GeminiClient(BaseModelClient):
    """Google Gemini (AI Studio) client using the REST API with streaming support.

    Uses the generativelanguage.googleapis.com endpoint which works with
    a free API key from https://aistudio.google.com/app/apikey
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3.7-flash",
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        # The key goes in a header, never the query string: httpx echoes the
        # full URL in HTTPStatusError messages, which would leak the key into
        # logs and error responses.
        self._client = httpx.AsyncClient(
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        )

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        # Extract system instruction if present
        system_text = ""
        contents = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                # Gemini uses "user" and "model" roles
                role = "model" if m.role == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": m.content}],
                })

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }
        return payload

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        model_name = model or self.default_model
        url = f"{self.base_url}/models/{model_name}:generateContent"
        payload = self._build_payload(messages, temperature=temperature, max_tokens=max_tokens)

        async def _request() -> dict:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

        data = await retry_async(_request, provider="gemini")

        # Extract text from response
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                content += part.get("text", "")

        return ChatResponse(
            content=content,
            model=model_name,
            usage=data.get("usageMetadata", {}),
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        model_name = model or self.default_model
        url = f"{self.base_url}/models/{model_name}:streamGenerateContent?alt=sse"
        payload = self._build_payload(messages, temperature=temperature, max_tokens=max_tokens)

        for attempt in range(DEFAULT_MAX_ATTEMPTS):
            produced = False
            try:
                async with self._client.stream("POST", url, json=payload) as resp:
                    await raise_for_stream_status(resp, "gemini")
                    async with aclosing(resp.aiter_lines()) as lines:
                        async for line in lines:
                            if not line.startswith("data: "):
                                continue
                            try:
                                chunk = json.loads(line[6:])
                                candidates = chunk.get("candidates", [])
                                parts = (
                                    candidates[0].get("content", {}).get("parts", [])
                                    if candidates
                                    else []
                                )
                                texts = [part.get("text", "") for part in parts]
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                            for text in texts:
                                if text:
                                    produced = True
                                    yield StreamChunk(content=text, done=False)
            except Exception as exc:
                error = provider_error_from(exc, "gemini")
                # Once tokens have reached the caller a retry would duplicate
                # the answer, so only retry a stream that never produced output.
                if produced or not error.retryable or attempt == DEFAULT_MAX_ATTEMPTS - 1:
                    raise error from None
                delay = retry_after_seconds(exc) or backoff_delay(attempt)
                logger.warning(
                    "gemini stream failed (%s); retrying in %.1fs [attempt %d/%d]",
                    error.message,
                    delay,
                    attempt + 1,
                    DEFAULT_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            yield StreamChunk(content="", done=True)
            return

        raise ProviderError("Gemini stream could not be established.", provider="gemini")

    async def close(self) -> None:
        await self._client.aclose()

    def get_provider_name(self) -> str:
        return "gemini"
