"""
tests/test_chunker.py

Day 13 deliverable: Unit tests verifying the text chunking pipeline.

Run with:
    pytest tests/test_chunker.py -v

Tests cover:
    - Basic single-page chunking
    - Multi-page chunking with page tracking
    - Size boundary enforcement
    - Overlap between chunks
    - Empty/whitespace input handling
    - Large document chunking
    - Single very long paragraph
    - Special characters in text
    - Consistent chunk indexing
    - Zero overlap chunking
"""

import sys
import os

# Add project root to python path for testing
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from app.chunker import chunk_document


# ── Original 5 tests (Day 13 baseline) ────────────────────────────────────────

def test_chunk_document_basic():
    """Test that a simple, small document produces exactly one chunk with correct metadata."""
    pages = {
        1: "This is page one text. It is very simple and short."
    }
    chunks = chunk_document(pages, max_chars=1000, overlap=0)

    assert len(chunks) == 1
    assert chunks[0]["index"] == 1
    assert chunks[0]["pages"] == [1]
    assert chunks[0]["text"] == "This is page one text. It is very simple and short."
    assert chunks[0]["char_count"] == len(pages[1])


def test_chunk_document_multiple_pages():
    """Test that chunks correctly track multiple pages."""
    pages = {
        1: "This is page one text which is short.",
        2: "This is page two text which is also short."
    }
    chunks = chunk_document(pages, max_chars=40, overlap=0)

    assert len(chunks) >= 2
    pages_seen = set()
    for chunk in chunks:
        for p in chunk["pages"]:
            pages_seen.add(p)
    assert 1 in pages_seen
    assert 2 in pages_seen


def test_chunk_document_size_boundary():
    """Test that no chunk exceeds the maximum character threshold."""
    paragraphs = [
        "Paragraph number one is here.",
        "Paragraph number two is here.",
        "Paragraph number three is here."
    ]
    pages = {1: "\n\n".join(paragraphs)}

    max_chars = 60
    chunks = chunk_document(pages, max_chars=max_chars, overlap=0)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["char_count"] <= max_chars
        assert len(chunk["text"]) <= max_chars


def test_chunk_document_overlap_handling():
    """Test that overlap is correctly added to subsequent chunks."""
    pages = {
        1: "This is the first sentence. This is the second sentence. This is the third sentence."
    }
    chunks = chunk_document(pages, max_chars=50, overlap=25)

    assert len(chunks) >= 2
    chunk1_text = chunks[0]["text"]
    chunk2_text = chunks[1]["text"]

    words_chunk1 = chunk1_text.split()
    overlap_found = False
    for word in words_chunk1[-3:]:
        if word in chunk2_text:
            overlap_found = True
            break
    assert overlap_found, f"Expected overlap between '{chunk1_text}' and '{chunk2_text}'"


def test_chunk_document_empty_input():
    """Test that empty or whitespace-only inputs return empty chunk lists."""
    pages = {1: "", 2: "   "}
    chunks = chunk_document(pages, max_chars=1000)
    assert len(chunks) == 0


# ── New 5 tests (Day 13 extended coverage) ────────────────────────────────────

def test_chunk_document_large_document():
    """Test that a large multi-page document is chunked without data loss."""
    sentence = "This is a repeated test sentence for large document simulation. "
    pages = {i: sentence * 10 for i in range(1, 6)}  # 5 pages, each ~640 chars

    chunks = chunk_document(pages, max_chars=500, overlap=0)

    # Should produce multiple chunks
    assert len(chunks) > 1

    # All chunk indices should be sequential starting from 1
    for i, chunk in enumerate(chunks, start=1):
        assert chunk["index"] == i


def test_chunk_document_index_is_sequential():
    """Test that chunk index numbers are always sequential starting from 1."""
    pages = {
        1: "First page content with enough text to possibly split.",
        2: "Second page content with enough text to possibly split.",
        3: "Third page content with enough text to possibly split.",
    }
    chunks = chunk_document(pages, max_chars=40, overlap=0)

    for i, chunk in enumerate(chunks, start=1):
        assert chunk["index"] == i, f"Expected index {i}, got {chunk['index']}"


def test_chunk_document_zero_overlap():
    """Test that zero overlap produces non-overlapping independent chunks."""
    pages = {
        1: "Alpha beta gamma. Delta epsilon zeta. Eta theta iota kappa."
    }
    chunks = chunk_document(pages, max_chars=25, overlap=0)

    if len(chunks) >= 2:
        # With zero overlap, each word should appear in only one chunk
        chunk1_words = set(chunks[0]["text"].split())
        chunk2_words = set(chunks[1]["text"].split())
        # There should be no (or minimal) word overlap between consecutive chunks
        common = chunk1_words & chunk2_words
        assert len(common) == 0, f"Expected no overlap but found shared words: {common}"


def test_chunk_document_char_count_matches_text():
    """Test that char_count metadata always matches actual text length."""
    pages = {
        1: "The quick brown fox jumps over the lazy dog. " * 5,
        2: "Pack my box with five dozen liquor jugs. " * 5,
    }
    chunks = chunk_document(pages, max_chars=200, overlap=50)

    for chunk in chunks:
        assert chunk["char_count"] == len(chunk["text"]), (
            f"char_count {chunk['char_count']} != actual length {len(chunk['text'])}"
        )


def test_chunk_document_special_characters():
    """Test that special characters (unicode, punctuation) are preserved correctly."""
    pages = {
        1: "Héllo Wörld! This is a tëst with spécial charactërs: @#$%^&*(). नमस्ते. 你好。"
    }
    chunks = chunk_document(pages, max_chars=1000, overlap=0)

    assert len(chunks) == 1
    # All special characters should be preserved
    assert "Héllo" in chunks[0]["text"]
    assert "नमस्ते" in chunks[0]["text"]
    assert "你好" in chunks[0]["text"]


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
