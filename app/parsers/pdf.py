import io
import re

import pdfplumber

from app.parsers.blocks import Block, NoTextLayer
from app.parsers.normalizer import strip_running_lines

HEADING = re.compile(r"^\d+\.\s+\S")


def parse_pdf(data: bytes) -> list[Block]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [[line for line in (p.extract_text() or "").split("\n") if line.strip()] for p in pdf.pages]
    if not any(pages):
        raise NoTextLayer("в PDF нет текстового слоя, похоже на скан: нужно распознавание")
    blocks, section = [], ""
    for page_no, lines in enumerate(strip_running_lines(pages), start=1):
        current: list[str] = []
        for line in lines:
            if HEADING.match(line):
                if current:
                    blocks.append(Block("text", "\n".join(current), page=page_no, section=section))
                section, current = line.strip(), []
            else:
                current.append(line)
        if current:
            blocks.append(Block("text", "\n".join(current), page=page_no, section=section))
    return blocks
