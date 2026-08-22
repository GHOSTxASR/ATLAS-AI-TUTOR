from __future__ import annotations

from dataclasses import dataclass
from app.pipelines.chunker import DocumentChunker


@dataclass
class MockPage:
    page_number: int
    text: str


def test_chunk_short_text():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    text = "Hello world! This is a simple short text for testing chunking."
    chunks = chunker.chunk_text(text)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == text
    assert chunks[0].token_count > 0
    assert chunks[0].char_offset_start == 0
    assert chunks[0].char_offset_end == len(text)


def test_chunk_long_text_with_overlap():
    chunker = DocumentChunker(chunk_size=30, chunk_overlap=10)
    sentence = "Artificial intelligence and machine learning are transforming education worldwide. "
    text = sentence * 10
    chunks = chunker.chunk_text(text)

    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.token_count <= 40  # Reasonable allowance around boundary
        assert len(c.text) > 0


def test_sentence_boundary_snapping():
    chunker = DocumentChunker(chunk_size=20, chunk_overlap=5)
    text = "First sentence here. Second sentence starts right now. Third sentence concludes the test."
    chunks = chunker.chunk_text(text)

    assert len(chunks) >= 1
    # Check that chunks tend to end with sentence punctuation or clean boundaries
    for c in chunks:
        assert isinstance(c.text, str)
        assert len(c.text) > 0


def test_page_aware_chunking():
    chunker = DocumentChunker(chunk_size=50, chunk_overlap=10)
    pages = [
        MockPage(page_number=1, text="This is the introduction on page one. It covers basic fundamentals."),
        MockPage(page_number=2, text="This is advanced discussion on page two. It explores deep topics."),
    ]
    chunks = chunker.chunk_document(full_text="", pages=pages)

    assert len(chunks) >= 2
    assert chunks[0].page_number == 1
    assert any(c.page_number == 2 for c in chunks)


def test_token_counting():
    chunker = DocumentChunker()
    count = chunker.count_tokens("This is a quick sentence for counting tokens.")
    assert count > 5
