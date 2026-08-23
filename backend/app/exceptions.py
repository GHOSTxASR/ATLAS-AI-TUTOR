from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AtlasError(Exception):
    code: str
    message: str
    status_code: int = 500
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class ConfigurationError(AtlasError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("CONFIGURATION_ERROR", message, 500, details or {})


class NotFoundError(AtlasError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("NOT_FOUND", message, 404, details or {})

