import sys
from pathlib import Path

from app.parsers.blocks import ParseError
from app.parsers.chunker import Chunk, chunk_blocks
from app.parsers.docx import parse_docx
from app.parsers.normalizer import normalize
from app.parsers.pdf import parse_pdf
from app.parsers.xlsx import parse_xlsx

PARSERS = {".pdf": parse_pdf, ".docx": parse_docx, ".xlsx": parse_xlsx}


class UnsupportedFormat(ParseError):
    pass


def parse(filename: str, data: bytes) -> list[Chunk]:
    parser = PARSERS.get(Path(filename).suffix.lower())
    if parser is None:
        raise UnsupportedFormat(f"формат {Path(filename).suffix or 'без расширения'} не поддерживается")
    return chunk_blocks(normalize(parser(data)))


if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        chunks = parse(path.name, path.read_bytes())
    except ParseError as exc:
        print(f"отказ: {exc}")
        sys.exit(1)
    for c in chunks:
        where = f"стр. {c.page}" if c.page else (f"{c.sheet}, строка {c.row}" if c.sheet else "")
        code = f" · {c.program_code}" if c.program_code else ""
        print(f"[{c.ordinal}] {c.section or '—'} · {where}{code}\n    {c.text}\n")
