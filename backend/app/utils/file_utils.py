from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from a display filename.

    Prevents path traversal from user-controlled upload filenames.
    """
    name = Path(filename).name  # drop any directory components (.., /, \)
    name = name.strip().strip(".")
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    return name or "upload"


def unique_storage_name(display_filename: str) -> str:
    """Build a UUID-prefixed, collision-free storage filename."""
    return f"{uuid.uuid4()}_{sanitize_filename(display_filename)}"


def ensure_within_directory(base: Path, target: Path) -> Path:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if resolved_base not in resolved_target.parents and resolved_target != resolved_base:
        raise ValueError(f"Path escapes base directory: {target}")
    return resolved_target

