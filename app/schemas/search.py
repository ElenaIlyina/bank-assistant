from pydantic import BaseModel


class SearchHit(BaseModel):
    id: int
    document_id: str
    filename: str
    ordinal: int
    text: str
    kind: str
    section: str
    page: int | None
    sheet: str | None
    row_number: int | None
    program_code: str | None
    code_match: bool
    score: float
    similarity: float | None

