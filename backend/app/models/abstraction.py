from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ChatMessage:
    """A single message in a conversation."""
    role: str   # "system", "user", "assistant"
    content: str


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    content: str = ""
    done: bool = False


@dataclass
class ChatResponse:
    """A complete (non-streaming) chat response."""
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    #: Why generation stopped, normalised across providers. "length" means the
    #: token limit cut the reply off. Without this a caller asking for JSON
    #: cannot tell a truncated object from a malformed one, and silently
    #: treats "the model ran out of room" as "the model failed".
    finish_reason: str = ""

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class BaseModelClient(ABC):
    """Abstract base class for all LLM provider clients."""

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Non-streaming chat completion."""
        raise NotImplementedError

    @abstractmethod
    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming chat completion. Yields chunks as they arrive."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close any open HTTP connections."""
        raise NotImplementedError

    @abstractmethod
    def get_provider_name(self) -> str:
        raise NotImplementedError
