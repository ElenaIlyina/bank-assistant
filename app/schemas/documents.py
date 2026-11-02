from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel):
    id: str
    filename: str
    sha256: str
    status: str
    error: str | None
    created_at: datetime
    updated_at: datetime

