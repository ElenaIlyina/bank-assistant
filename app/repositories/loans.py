"""Loan data access. Only this layer touches the loans table."""

from __future__ import annotations

from dataclasses import dataclass

from app.db import Database


@dataclass(frozen=True)
class LoanRecord:
    id: int
    code: str
    principal_kop: int
    rate_bp: int
    months: int


async def list_loans(db: Database) -> list[LoanRecord]:
    rows = await db.pool.fetch(
        "SELECT id, code, principal_kop, rate_bp, months FROM loans ORDER BY id"
    )
    return [LoanRecord(**dict(r)) for r in rows]


async def get_loan(db: Database, loan_id: int) -> LoanRecord | None:
    row = await db.pool.fetchrow(
        "SELECT id, code, principal_kop, rate_bp, months FROM loans WHERE id = $1", loan_id
    )
    return LoanRecord(**dict(row)) if row else None
