
from dataclasses import dataclass


CHUNK_SIZE = 10_000
CHUNK_OVERLAP = 500


@dataclass
class TextChunk:
    chunk_index: int
    total_chunks: int
    text: str


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Split text into overlapping character-based chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be >= 0 and smaller than chunk_size"
        )

    text = text.strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [
            TextChunk(
                chunk_index=1,
                total_chunks=1,
                text=text,
            )
        ]

    chunks = []
    start = 0
    text_length = len(text)
    step = chunk_size - overlap

    while start < text_length:
        end = min(start + chunk_size, text_length)

        # Prefer splitting at a paragraph boundary when practical.
        if end < text_length:
            boundary = text.rfind("\n\n", start + step // 2, end)

            if boundary > start:
                end = boundary

        piece = text[start:end].strip()

        if piece:
            chunks.append(piece)

        if end >= text_length:
            break

        start = max(start + 1, end - overlap)

    total = len(chunks)

    return [
        TextChunk(
            chunk_index=index,
            total_chunks=total,
            text=piece,
        )
        for index, piece in enumerate(chunks, start=1)
    ]
