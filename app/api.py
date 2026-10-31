"""HTTP API (routers): thin endpoints that delegate to services and repositories."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from app.calculator import EarlyRepayment
from app.db import Database
from app.repositories import loans as loans_repo
from app.schemas import LoanOut, ScheduleIn, ScheduleOut
from app.services import loans as loans_service

router = APIRouter()


def get_db(request: Request) -> Database:
    return request.app.state.db


@router.get("/loans", response_model=list[LoanOut])
async def list_loans(db: Database = Depends(get_db)) -> list[LoanOut]:
    records = await loans_repo.list_loans(db)
    return [LoanOut(**vars(r)) for r in records]


@router.post("/loans/{loan_id}/schedule", response_model=ScheduleOut)
async def loan_schedule(
    loan_id: int,
    body: ScheduleIn | None = None,
    db: Database = Depends(get_db),
) -> ScheduleOut:
    loan = await loans_repo.get_loan(db, loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="loan not found")

    if body is not None:
        ers = [EarlyRepayment(e.payment_date, e.amount_kop) for e in body.early_repayments]
        request = loans_service.ScheduleRequest(
            principal_kop=body.principal_kop,
            rate_bp=body.rate_bp,
            months=body.months,
            start_date=body.start_date,
            early_repayments=ers,
            mode=body.mode,
        )
        schedule = loans_service.schedule_for_loan(loan, start_date=date.today(), request=request)
        payment = loans_service.fixed_payment_kop(schedule)
    else:
        schedule = loans_service.schedule_for_loan(loan, start_date=date.today())
        payment = loans_service.fixed_payment_kop(schedule)

    return ScheduleOut.from_schedule(schedule, payment)
