from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

from app.exceptions import AtlasError

if TYPE_CHECKING:
    from fastapi import UploadFile


#: Read in bounded pieces rather than one `await file.read()`. That call
#: materialises the entire body as a single bytes object regardless of how the
#: transport received it, so checking the size limit afterwards has already
#: paid the memory cost the limit exists to avoid -- a large enough POST could
#: exhaust memory before the configured cap ever got a chance to reject it.
_UPLOAD_CHUNK_SIZE = 1024 * 1024


async def read_upload_within_limit(
    file: "UploadFile",
    max_bytes: int,
    *,
    error_message: str,
    error_details: dict[str, Any] | None = None,
    chunk_size: int = _UPLOAD_CHUNK_SIZE,
) -> bytes:
    """Read an upload's body, aborting as soon as it exceeds `max_bytes`.

    Memory use is bounded to roughly `max_bytes + chunk_size` even for a client
    that declares a small `Content-Length` and then keeps streaming, or omits
    it entirely -- the check is on bytes actually received, not on a header
    the client controls.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AtlasError(
                status_code=422,
                code="VALIDATION_ERROR",
                message=error_message,
                details=error_details or {},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@asynccontextmanager
async def upload_to_temp_file(
    file: "UploadFile",
    max_bytes: int,
    *,
    error_message: str,
    error_details: dict[str, Any] | None = None,
    suffix: str = "",
    chunk_size: int = _UPLOAD_CHUNK_SIZE,
) -> AsyncIterator[Path]:
    """Stream an upload to a temporary file and yield its path.

    For uploads that are consumed by something able to work from disk -- a ZIP
    archive, say. `read_upload_within_limit` still has to hold the whole body
    in memory to return it; this never holds more than one chunk, so the size
    limit stops being what protects memory and becomes an ordinary policy
    choice.

    The file is removed when the block exits, on success or on failure.
    """
    fd, temp_name = tempfile.mkstemp(prefix="atlas-upload-", suffix=suffix)
    temp_path = Path(temp_name)
    try:
        total = 0
        # fdopen takes ownership of the descriptor, so the file is closed
        # exactly once even if the limit check raises mid-write.
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AtlasError(
                        status_code=422,
                        code="VALIDATION_ERROR",
                        message=error_message,
                        details=error_details or {},
                    )
                out.write(chunk)
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


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

