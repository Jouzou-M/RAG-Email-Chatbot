from __future__ import annotations

from dataclasses import dataclass

from email_rag.config import settings


@dataclass
class TextChunk:
    """A chunk of text with its position in the source document."""

    text: str
    chunk_index: int
    total_chunks: int = 0  # Set after all chunks are created
    char_start: int = 0
    char_end: int = 0


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks using recursive boundary-aware splitting.

    Strategy:
    1. If text fits in one chunk, return it as-is.
    2. Try splitting on paragraph boundaries (double newline).
    3. Fall back to sentence boundaries.
    4. Fall back to word boundaries.
    5. Last resort: character split.
    """
    chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    if not text.strip():
        return []

    if len(text) <= chunk_size:
        return [TextChunk(text=text, chunk_index=0, total_chunks=1)]

    chunks = _recursive_split(text, chunk_size, chunk_overlap)

    # Set total_chunks and position info.
    # Search forward only (never backwards) to avoid matching an earlier
    # duplicate occurrence in emails with repeated content.
    result: list[TextChunk] = []
    offset = 0
    for i, chunk_text_str in enumerate(chunks):
        start = text.find(chunk_text_str, offset)
        if start == -1:
            start = offset
        end = start + len(chunk_text_str)

        result.append(
            TextChunk(
                text=chunk_text_str,
                chunk_index=i,
                total_chunks=len(chunks),
                char_start=start,
                char_end=end,
            )
        )
        offset = start + len(chunk_text_str)

    for chunk in result:
        chunk.total_chunks = len(result)

    return result


SEPARATORS = [
    "\n\n",  # Paragraph
    "\n",    # Line
    ". ",    # Sentence
    ", ",    # Clause
    " ",     # Word
    "",      # Character
]


def _recursive_split(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Recursively split text using decreasingly granular separators."""
    if separators is None:
        separators = SEPARATORS

    if len(text) <= chunk_size:
        return [text]

    # Find the best separator for this text
    separator = separators[-1]
    for sep in separators:
        if sep in text:
            separator = sep
            break

    # Split on the chosen separator
    if separator:
        parts = text.split(separator)
    else:
        parts = list(text)

    # Merge parts into chunks of appropriate size
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for part in parts:
        part_with_sep = part + separator if separator else part
        part_len = len(part_with_sep)

        if current_len + part_len > chunk_size and current:
            chunk_text_str = separator.join(current) if separator else "".join(current)
            chunks.append(chunk_text_str.strip())

            # Keep overlap by retaining some trailing parts
            overlap_len = 0
            overlap_parts: list[str] = []
            for prev in reversed(current):
                if overlap_len + len(prev) > chunk_overlap:
                    break
                overlap_parts.insert(0, prev)
                overlap_len += len(prev) + len(separator)

            current = overlap_parts
            current_len = overlap_len

        current.append(part)
        current_len += part_len

    if current:
        chunk_text_str = separator.join(current) if separator else "".join(current)
        if chunk_text_str.strip():
            chunks.append(chunk_text_str.strip())

    # If any chunk is still too large, split with next separator
    if separators[1:]:
        refined: list[str] = []
        for chunk in chunks:
            if len(chunk) > chunk_size:
                refined.extend(
                    _recursive_split(chunk, chunk_size, chunk_overlap, separators[1:])
                )
            else:
                refined.append(chunk)
        return refined

    return chunks
