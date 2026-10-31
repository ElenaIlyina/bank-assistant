"""Loan application logic: builds schedules and turns requests into calculator calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.calculator import (
    EarlyRepayment,
    EarlyRepaymentMode,
    Schedule,
    build_schedule,
)
from app.repositories.loans import LoanRecord


@dataclass(frozen=True)
class ScheduleRequest:
    principal_kop: int
    rate_bp: int
    months: int
    start_date: date
    early_repayments: list[EarlyRepayment] = ()
    mode: EarlyRepaymentMode = "reduce_term"


def schedule_for_loan(
    loan: LoanRecord, start_date: date, *, request: ScheduleRequest | None = None
) -> Schedule:
    """Build a schedule either from explicit request params or from the seeded loan."""
    if request is not None:
        principal = request.principal_kop
        rate = request.rate_bp
        months = request.months
        start = request.start_date
        ers = list(request.early_repayments)
        mode = request.mode
    else:
        principal = loan.principal_kop
        rate = loan.rate_bp
        months = loan.months
        start = start_date
        ers = []
        mode = "reduce_term"

    return build_schedule(principal, rate, months, start, ers, mode)


def fixed_payment_kop(schedule: Schedule, fallback: int) -> int:
    """Annuity payment for the whole schedule (all rows equal except possibly the last)."""
    regular = {r.payment_kop for r in schedule.rows[:-1]}
    if len(regular) == 1:
        return regular.pop()
    return fallback if schedule.rows else 0
