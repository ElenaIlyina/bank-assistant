"""Pydantic request/response schemas. All money as JSON integers (kopecks)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.calculator import EarlyRepaymentMode


class LoanOut(BaseModel):
    id: int
    code: str
    principal_kop: int
    rate_bp: int
    months: int


class EarlyRepaymentIn(BaseModel):
    payment_date: date
    amount_kop: int = Field(gt=0)


class ScheduleIn(BaseModel):
    principal_kop: int = Field(gt=0)
    rate_bp: int = Field(ge=0)
    months: int = Field(gt=0)
    start_date: date
    early_repayments: list[EarlyRepaymentIn] = Field(default_factory=list)
    mode: EarlyRepaymentMode = "reduce_term"


class ScheduleRowOut(BaseModel):
    n: int
    payment_date: date
    payment_kop: int
    interest_kop: int
    principal_kop: int
    balance_kop: int


class ScheduleOut(BaseModel):
    rows: list[ScheduleRowOut]
    total_paid_kop: int
    total_interest_kop: int
    payment_kop: int

    @classmethod
    def from_schedule(cls, schedule, payment_kop: int) -> ScheduleOut:
        return cls(
            rows=[
                ScheduleRowOut(
                    n=r.n,
                    payment_date=r.payment_date,
                    payment_kop=r.payment_kop,
                    interest_kop=r.interest_kop,
                    principal_kop=r.principal_kop,
                    balance_kop=r.balance_kop,
                )
                for r in schedule.rows
            ],
            total_paid_kop=schedule.total_paid_kop,
            total_interest_kop=schedule.total_interest_kop,
            payment_kop=payment_kop,
        )
