from pathlib import Path

import pytest

from app.utils.file_utils import (
    ensure_within_directory,
    sanitize_filename,
    sha256_bytes,
    unique_storage_name,
)


def test_sanitize_filename_strips_directory_components():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\evil.dll") == "evil.dll"


def test_sanitize_filename_strips_unsafe_characters():
    # Consecutive unsafe characters collapse into a single underscore.
    assert sanitize_filename("my notes (final)!.txt") == "my_notes_final_.txt"


def test_sanitize_filename_never_empty():
    assert sanitize_filename("...") == "upload"
    assert sanitize_filename("") == "upload"


def test_unique_storage_name_is_prefixed_and_safe():
    name = unique_storage_name("../secrets.txt")
    assert name.endswith("_secrets.txt")
    assert "/" not in name and "\\" not in name


def test_sha256_bytes_is_deterministic():
    a = sha256_bytes(b"hello world")
    b = sha256_bytes(b"hello world")
    c = sha256_bytes(b"different content")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_ensure_within_directory_allows_nested_path(tmp_path: Path):
    base = tmp_path / "raw"
    base.mkdir()
    target = base / "file.txt"
    assert ensure_within_directory(base, target) == target.resolve()


def test_ensure_within_directory_rejects_escape(tmp_path: Path):
    base = tmp_path / "raw"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    with pytest.raises(ValueError):
        ensure_within_directory(base, outside)
