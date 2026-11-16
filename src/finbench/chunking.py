"""Chunking: page texts into chunks that know their filing and page span."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Chunk:
    id: str
    filing: str
    first_page: int  # zero-indexed, inclusive
    last_page: int  # zero-indexed, inclusive
    text: str


class Chunker(Protocol):
    def chunk(self, filing: str, pages: list[str]) -> list[Chunk]: ...


class FixedSizeChunker:
    """Windows of `size` words that start every `size - overlap` words and may cross pages."""

    def __init__(self, size: int, overlap: int) -> None:
        self._size = size
        self._step = size - overlap

    def chunk(self, filing: str, pages: list[str]) -> list[Chunk]:
        words = [(word, number) for number, text in enumerate(pages) for word in text.split()]
        chunks: list[Chunk] = []
        for start in range(0, len(words), self._step):
            window = words[start : start + self._size]
            chunks.append(
                Chunk(
                    id=f"{filing}:{len(chunks)}",
                    filing=filing,
                    first_page=window[0][1],
                    last_page=window[-1][1],
                    text=" ".join(word for word, _ in window),
                )
            )
            if start + self._size >= len(words):
                break  # the window reached the end; a further one would only repeat the overlap
        return chunks
