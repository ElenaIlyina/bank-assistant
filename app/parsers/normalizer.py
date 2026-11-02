import re

from app.parsers.blocks import Block

REPLACE = {"­": "", " ": " ", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"}


def strip_running_lines(pages: list[list[str]]) -> list[list[str]]:
    if len(pages) < 2:
        return pages
    masked = [{re.sub(r"\d+", "#", line.strip()) for line in page} for page in pages]
    running = set.intersection(*masked)
    return [[line for line in page if re.sub(r"\d+", "#", line.strip()) not in running] for page in pages]


def clean_text(text: str) -> str:
    for src, dst in REPLACE.items():
        text = text.replace(src, dst)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def normalize(blocks: list[Block]) -> list[Block]:
    for b in blocks:
        b.text = clean_text(b.text)
    return [b for b in blocks if b.text]
