from datetime import datetime

from pydantic import BaseModel, Field


class PaymentDayRequest(BaseModel):
    loan_id: int = Field(gt=0)
    new_day: int = Field(ge=1, le=28)


class Decision(BaseModel):
    approve: bool


class Job(BaseModel):
    id: str
    kind: str
    loan_id: int
    status: str
    payload: dict
    result: dict | None
    created_at: datetime
    updated_at: datetime

