from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ResponseEnvelope(BaseModel):
    data: Any = None
    error: ErrorPayload | None = None
    meta: dict[str, Any] | None = None

