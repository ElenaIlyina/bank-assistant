from dataclasses import dataclass


@dataclass
class Block:
    kind: str
    text: str
    page: int | None = None
    section: str = ""
    sheet: str | None = None
    row: int | None = None


class ParseError(Exception):
    pass


class NoTextLayer(ParseError):
    pass
