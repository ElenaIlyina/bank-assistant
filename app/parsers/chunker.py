import re
from dataclasses import dataclass

from app.parsers.blocks import Block

PROGRAM_CODE = re.compile(r"\bIP-[A-Z]+-\d+\b")


@dataclass
class Chunk:
    ordinal: int
    text: str
    kind: str
    section: str
    page: int | None
    sheet: str | None
    row: int | None
    program_code: str | None


def split_text(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    pieces, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            space = text.rfind(" ", start + size // 2, end)
            end = space if space > start else end
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(text.rfind(" ", start, end - overlap) + 1, start + 1)
    return pieces


def chunk_blocks(blocks: list[Block], size: int = 600, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    for b in blocks:
        pieces = [b.text] if b.kind == "row" else split_text(b.text, size, overlap)
        for piece in pieces:
            code = PROGRAM_CODE.search(piece)
            chunks.append(
                Chunk(len(chunks), piece, b.kind, b.section, b.page, b.sheet, b.row, code.group(0) if code else None)
            )
    return chunks
