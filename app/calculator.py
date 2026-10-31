"""Loan payment schedule calculator. All money in integer kopecks, rates in basis points.

Only this module contains fractional-kopeck logic (round_half_up), per hint_cents.txt.
The last installment absorbs the remaining balance so the schedule converges exactly.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

EarlyRepaymentMode = Literal["reduce_term", "reduce_payment"]


def round_half_up(numerator: int, denominator: int) -> int:
    """The single fractional-kopeck function for the whole project."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (2 * numerator + denominator) // (2 * denominator)


def annuity_payment_kop(principal_kop: int, rate_bp: int, months: int) -> int:
    """Monthly annuity payment in kopecks, rounded half-up."""
    if months <= 0:
        raise ValueError("months must be positive")
    if principal_kop <= 0:
        raise ValueError("principal must be positive")
    if rate_bp < 0:
        raise ValueError("rate must be non-negative")
    if rate_bp == 0:
        return round_half_up(principal_kop, months)
    monthly_bp = rate_bp // 12  # annual bp → monthly bp (12% = 1200 bp → 100 bp/mo)
    factor = (10_000 + monthly_bp) ** months
    numerator = principal_kop * monthly_bp * factor
    denominator = 10_000 * (factor - 10_000**months)
    return round_half_up(numerator, denominator)


@dataclass
class ScheduleRow:
    n: int
    payment_date: date
    payment_kop: int
    interest_kop: int
    principal_kop: int
    balance_kop: int


@dataclass
class Schedule:
    rows: list[ScheduleRow] = field(default_factory=list)

    @property
    def total_paid_kop(self) -> int:
        return sum(row.payment_kop for row in self.rows)

    @property
    def total_interest_kop(self) -> int:
        return sum(row.interest_kop for row in self.rows)


def add_months(d: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the end of the target month."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass
class EarlyRepayment:
    payment_date: date
    amount_kop: int

    def __post_init__(self) -> None:
        if self.amount_kop <= 0:
            raise ValueError("early repayment amount must be positive")


def build_schedule(
    principal_kop: int,
    rate_bp: int,
    months: int,
    start_date: date,
    early_repayments: list[EarlyRepayment] | None = None,
    mode: EarlyRepaymentMode = "reduce_term",
) -> Schedule:
    """Build the full annuity schedule.

    mode="reduce_term": payment stays the same, term shrinks.
    mode="reduce_payment": term stays the same, payment is recalculated.
    """
    early = sorted(early_repayments or [], key=lambda er: er.payment_date)
    original_term = months
    payment = annuity_payment_kop(principal_kop, rate_bp, months)
    balance = principal_kop
    schedule = Schedule()
    n = 0
    max_months = original_term + len(early) + 2  # hard stop; schedule must converge long before

    while balance > 0 and n < max_months:
        n += 1
        payment_date = add_months(start_date, n)
        interest = round_half_up(balance * rate_bp, 12 * 10_000)

        # on the final scheduled month (reduce_term without ER shift) the installment
        # absorbs whatever is left so the schedule converges exactly to the kopeck
        principal_part = balance if n >= original_term else min(balance, payment - interest)
        balance -= principal_part
        schedule.rows.append(
            ScheduleRow(
                n, payment_date, interest + principal_part, interest, principal_part, balance
            )
        )

        # early repayments due on this date are applied after the regular payment
        if balance > 0:
            due_total = sum(er.amount_kop for er in early if er.payment_date == payment_date)
            if due_total > 0:
                er_amount = min(balance, due_total)
                balance -= er_amount
                schedule.rows.append(ScheduleRow(n, payment_date, er_amount, 0, er_amount, balance))
                if mode == "reduce_payment" and balance > 0:
                    remaining = months - n
                    if remaining > 0:
                        payment = annuity_payment_kop(balance, rate_bp, remaining)
            # mode="reduce_term": payment stays, the term shrinks on its own

    if balance != 0:
        raise RuntimeError("schedule failed to converge")
    return schedule
