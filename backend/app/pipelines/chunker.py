from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

# Conservative when no tokenizer is available. Prose averages ~4 chars/token,
# but code, maths and non-English run denser, and under-counting sends an
# over-long prompt to the provider.
CHARS_PER_TOKEN_ESTIMATE = 3.0

_encoder_cache: dict[str, object] = {}
_encoder_warning_issued = False


def _load_encoder(encoding_name: str):
    """Load (and cache) a tiktoken encoder, warning once if unavailable.

    ``tiktoken.get_encoding`` downloads its vocabulary on first use, so on an
    offline machine this silently fell back to a character estimate with no
    indication that token budgets had become guesses.
    """
    global _encoder_warning_issued

    if not _TIKTOKEN_AVAILABLE:
        if not _encoder_warning_issued:
            _encoder_warning_issued = True
            logger.warning("tiktoken is not installed; token counts are estimated from length.")
        return None

    if encoding_name in _encoder_cache:
        return _encoder_cache[encoding_name]

    try:
        encoder = tiktoken.get_encoding(encoding_name)
    except Exception as e:
        encoder = None
        if not _encoder_warning_issued:
            _encoder_warning_issued = True
            logger.warning(
                "Could not load the %r tokenizer (%s); token counts are estimated from "
                "length. tiktoken downloads its vocabulary on first use, so this is "
                "expected offline.",
                encoding_name,
                e,
            )

    _encoder_cache[encoding_name] = encoder
    return encoder


@dataclass
class Chunk:
    """A semantic segment of a document with token count and spatial offsets."""

    chunk_index: int
    text: str
    token_count: int
    page_number: int | None = None
    char_offset_start: int = 0
    char_offset_end: int = 0
    section_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "text": self.text,
            "token_count": self.token_count,
            "page_number": self.page_number,
            "char_offset_start": self.char_offset_start,
            "char_offset_end": self.char_offset_end,
            "section_title": self.section_title,
        }


class DocumentChunker:
    """Splits document text into semantic token-sized chunks with sentence snapping."""

    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_CHUNK_OVERLAP = 64
    ENCODING_NAME = "cl100k_base"

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        encoding_name: str = ENCODING_NAME,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name

        self._encoder = _load_encoder(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in `text`.

        Approximate for non-OpenAI providers: `cl100k_base` is OpenAI's
        tokenizer, and Gemini/Claude segment differently. Callers that budget a
        context window should keep headroom rather than filling it exactly.
        """
        if not text:
            return 0
        if self._encoder is not None:
            return len(self._encoder.encode(text, disallowed_special=()))
        # No tokenizer available. Deliberately pessimistic: under-counting here
        # would let an over-long prompt reach the provider and be rejected.
        return max(1, math.ceil(len(text) / CHARS_PER_TOKEN_ESTIMATE))

    def _encode(self, text: str) -> list[int]:
        if self._encoder is not None:
            return self._encoder.encode(text, disallowed_special=())
        # Word/character surrogate token IDs
        words = text.split()
        return list(range(len(words)))

    def _decode(self, token_ids: list[int], original_text: str) -> str:
        if self._encoder is not None:
            return self._encoder.decode(token_ids)
        words = original_text.split()
        selected = [words[i] for i in token_ids if i < len(words)]
        return " ".join(selected)

    def _find_sentence_boundary(self, text: str, max_chars: int) -> int:
        """Find the nearest sentence or paragraph boundary within text up to max_chars."""
        if len(text) <= max_chars:
            return len(text)

        search_window = text[:max_chars]

        # Check for paragraph break
        para_idx = search_window.rfind("\n\n")
        if para_idx > int(max_chars * 0.6):
            return para_idx + 2

        # Check for sentence end followed by space or newline (. ! ?)
        patterns = [". ", "! ", "? ", ".\n", "!\n", "?\n"]
        best_idx = -1
        for p in patterns:
            idx = search_window.rfind(p)
            if idx > best_idx:
                best_idx = idx + len(p)

        if best_idx > int(max_chars * 0.5):
            return best_idx

        # Fall back to single newline
        nl_idx = search_window.rfind("\n")
        if nl_idx > int(max_chars * 0.5):
            return nl_idx + 1

        # Fall back to space
        space_idx = search_window.rfind(" ")
        if space_idx > int(max_chars * 0.5):
            return space_idx + 1

        return max_chars

    def chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        base_offset: int = 0,
        start_index: int = 0,
    ) -> list[Chunk]:
        """Split a single block of text into overlapping semantic chunks."""
        text = text.strip()
        if not text:
            return []

        total_tokens = self.count_tokens(text)
        if total_tokens <= self.chunk_size:
            return [
                Chunk(
                    chunk_index=start_index,
                    text=text,
                    token_count=total_tokens,
                    page_number=page_number,
                    char_offset_start=base_offset,
                    char_offset_end=base_offset + len(text),
                )
            ]

        chunks: list[Chunk] = []
        current_char_start = 0
        current_index = start_index

        if self._encoder is not None:
            # Tokenizer-based slicing
            token_ids = self._encoder.encode(text, disallowed_special=())
            num_tokens = len(token_ids)
            i = 0

            while i < num_tokens:
                # Window range
                window_tokens = token_ids[i : i + self.chunk_size]
                chunk_raw_text = self._encoder.decode(window_tokens)

                if i + self.chunk_size >= num_tokens:
                    # Final chunk
                    c_text = chunk_raw_text.strip()
                    if c_text:
                        char_pos = text.find(c_text, current_char_start)
                        if char_pos == -1:
                            char_pos = current_char_start
                        c_start = base_offset + char_pos
                        c_end = c_start + len(c_text)
                        chunks.append(
                            Chunk(
                                chunk_index=current_index,
                                text=c_text,
                                token_count=len(window_tokens),
                                page_number=page_number,
                                char_offset_start=c_start,
                                char_offset_end=c_end,
                            )
                        )
                    break

                # Snap boundary for non-final chunk
                boundary = self._find_sentence_boundary(chunk_raw_text, len(chunk_raw_text))
                snapped_text = chunk_raw_text[:boundary].strip()

                if not snapped_text:
                    snapped_text = chunk_raw_text.strip()

                snapped_tokens = len(self._encoder.encode(snapped_text, disallowed_special=()))
                char_pos = text.find(snapped_text, current_char_start)
                if char_pos == -1:
                    char_pos = current_char_start
                c_start = base_offset + char_pos
                c_end = c_start + len(snapped_text)

                chunks.append(
                    Chunk(
                        chunk_index=current_index,
                        text=snapped_text,
                        token_count=snapped_tokens,
                        page_number=page_number,
                        char_offset_start=c_start,
                        char_offset_end=c_end,
                    )
                )
                current_index += 1

                # Advance index with overlap
                advance_tokens = max(1, snapped_tokens - self.chunk_overlap)
                i += advance_tokens
                current_char_start = char_pos + max(1, len(snapped_text) // 2)

        else:
            # Character/word fallback slicing
            approx_chars = self.chunk_size * 4
            approx_overlap_chars = self.chunk_overlap * 4
            pos = 0

            while pos < len(text):
                end_pos = pos + approx_chars
                if end_pos >= len(text):
                    c_text = text[pos:].strip()
                    if c_text:
                        chunks.append(
                            Chunk(
                                chunk_index=current_index,
                                text=c_text,
                                token_count=self.count_tokens(c_text),
                                page_number=page_number,
                                char_offset_start=base_offset + pos,
                                char_offset_end=base_offset + len(text),
                            )
                        )
                    break

                boundary = self._find_sentence_boundary(text[pos:end_pos], approx_chars)
                c_text = text[pos : pos + boundary].strip()
                if not c_text:
                    c_text = text[pos:end_pos].strip()
                    boundary = len(c_text)

                chunks.append(
                    Chunk(
                        chunk_index=current_index,
                        text=c_text,
                        token_count=self.count_tokens(c_text),
                        page_number=page_number,
                        char_offset_start=base_offset + pos,
                        char_offset_end=base_offset + pos + len(c_text),
                    )
                )
                current_index += 1
                pos += max(1, boundary - approx_overlap_chars)

        return chunks

    def chunk_document(
        self,
        full_text: str,
        pages: list[Any] | None = None,
    ) -> list[Chunk]:
        """Chunk entire document, using page breakdown when available."""
        if not pages:
            return self.chunk_text(full_text)

        all_chunks: list[Chunk] = []
        global_index = 0
        base_offset = 0

        for page in pages:
            page_num = getattr(page, "page_number", None)
            page_text = getattr(page, "text", "")
            if not page_text or not page_text.strip():
                continue

            page_chunks = self.chunk_text(
                text=page_text,
                page_number=page_num,
                base_offset=base_offset,
                start_index=global_index,
            )
            all_chunks.extend(page_chunks)
            global_index += len(page_chunks)
            base_offset += len(page_text) + 1

        if not all_chunks and full_text.strip():
            return self.chunk_text(full_text)

        return all_chunks


# Backward compatibility alias
Chunker = DocumentChunker
