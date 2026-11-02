import io

from docx import Document

from app.parsers.blocks import Block


def parse_docx(data: bytes) -> list[Block]:
    doc = Document(io.BytesIO(data))
    blocks, section, current = [], "", []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.lower().startswith(("heading", "заголовок")):
            if current:
                blocks.append(Block("text", "\n".join(current), section=section))
            section, current = text, []
        else:
            current.append(text)
    if current:
        blocks.append(Block("text", "\n".join(current), section=section))
    return blocks
