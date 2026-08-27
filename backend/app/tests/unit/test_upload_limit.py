"""read_upload_within_limit aborts an oversized upload without fully buffering it.

Both upload endpoints used to `await file.read()` with no size argument -- that
call materialises the entire body as one bytes object regardless of how the
transport received it, so the size check that ran afterwards had already paid
the memory cost it exists to avoid. A large enough POST could exhaust memory
before the configured cap ever got a chance to reject it.

The regression this pins is specifically the *timing*: not just that an
oversized upload is eventually rejected (the old code did that too), but that
it is rejected after only a little more than the limit has actually been
pulled from the stream.
"""

from __future__ import annotations

import pytest

from app.exceptions import AtlasError
from app.utils.file_utils import read_upload_within_limit


class _CountingUpload:
    """A minimal upload-like object that reports how much of it was consumed.

    Standing in for FastAPI's ``UploadFile`` -- only the async ``read(size)``
    method is used by the function under test.
    """

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self.bytes_read = 0

    async def read(self, size: int) -> bytes:
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        self.bytes_read += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected_without_full_buffering():
    max_bytes = 1000
    chunk_size = 100
    # Far larger than the limit; if this were ever fully read, the assertion
    # on `bytes_read` below would fail.
    oversized = _CountingUpload(b"x" * 1_000_000)

    with pytest.raises(AtlasError) as excinfo:
        await read_upload_within_limit(
            oversized,
            max_bytes,
            error_message="File exceeds the limit.",
            error_details={"max_file_size_mb": 1},
            chunk_size=chunk_size,
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.details == {"max_file_size_mb": 1}
    # Stopped within one chunk of the limit, not after draining the source.
    assert oversized.bytes_read <= max_bytes + chunk_size


@pytest.mark.asyncio
async def test_upload_at_exactly_the_limit_is_accepted():
    data = b"y" * 1000
    result = await read_upload_within_limit(
        _CountingUpload(data), 1000, error_message="too big", chunk_size=100
    )
    assert result == data


@pytest.mark.asyncio
async def test_upload_one_byte_over_the_limit_is_rejected():
    with pytest.raises(AtlasError):
        await read_upload_within_limit(
            _CountingUpload(b"y" * 1001), 1000, error_message="too big", chunk_size=100
        )


@pytest.mark.asyncio
async def test_small_upload_content_is_returned_unchanged():
    data = b"hello world"
    result = await read_upload_within_limit(
        _CountingUpload(data), 1_000_000, error_message="too big"
    )
    assert result == data


@pytest.mark.asyncio
async def test_empty_upload_returns_empty_bytes():
    result = await read_upload_within_limit(
        _CountingUpload(b""), 1_000_000, error_message="too big"
    )
    assert result == b""
