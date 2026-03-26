from email_rag.processing.chunker import chunk_text


class TestChunker:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("Short text.", chunk_size=512)
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_splits_long_text(self):
        text = "Word " * 200  # ~1000 chars
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

        # All chunks should have correct total
        for chunk in chunks:
            assert chunk.total_chunks == len(chunks)

        # Indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_paragraph_splitting(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_text(text, chunk_size=25, chunk_overlap=5)
        assert len(chunks) >= 2

    def test_preserves_content(self):
        text = "The quick brown fox jumps over the lazy dog."
        chunks = chunk_text(text, chunk_size=512)
        full = " ".join(c.text for c in chunks)
        assert "quick brown fox" in full

    def test_chunk_overlap(self):
        text = "A " * 500
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        if len(chunks) >= 2:
            # Check there's some overlap between consecutive chunks
            end_of_first = chunks[0].text[-20:]
            assert any(
                word in chunks[1].text for word in end_of_first.split() if word.strip()
            )
