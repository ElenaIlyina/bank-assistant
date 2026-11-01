from dataclasses import dataclass
from datetime import date
from fractions import Fraction

BP = 10_000


def round_div(num: int | Fraction, den: int = 1) -> int:
    q = Fraction(num) / den
    if q < 0:
        raise ValueError("деньги в калькуляторе не бывают отрицательными")
    return int(q + Fraction(1, 2))


def monthly_interest(balance: int, rate_bp: int) -> int:
    return round_div(balance * rate_bp, 12 * BP)


def annuity_payment(principal: int, rate_bp: int, months: int) -> int:
    if months <= 0:
        raise ValueError("срок должен быть положительным")
    if rate_bp == 0:
        return round_div(principal, months)
    r = Fraction(rate_bp, 12 * BP)
    return round_div(principal * r / (1 - (1 + r) ** -months))


@dataclass(frozen=True)
class Row:
    n: int
    payment: int
    interest: int
    principal: int
    balance: int


def build_schedule(principal: int, rate_bp: int, months: int, payment: int | None = None) -> list[Row]:
    payment = payment or annuity_payment(principal, rate_bp, months)
    rows, balance, n = [], principal, 0
    while balance > 0:
        n += 1
        interest = monthly_interest(balance, rate_bp)
        part = payment - interest
        if part <= 0:
            raise ValueError("платеж не покрывает проценты")
        if part >= balance or n == months:
            part = balance
        balance -= part
        rows.append(Row(n, interest + part, interest, part, balance))
    return rows


def total_interest(rows: list[Row]) -> int:
    return sum(r.interest for r in rows)


@dataclass(frozen=True)
class EarlyRepayment:
    mode: str
    payment: int
    months_total: int
    interest_total: int
    saved: int


def early_repayment(principal: int, rate_bp: int, months: int, after_month: int, amount: int,
                    mode: str) -> EarlyRepayment:
    if mode not in ("term", "payment"):
        raise ValueError("mode: term или payment")
    base = build_schedule(principal, rate_bp, months)
    if not 0 < after_month < len(base):
        raise ValueError("досрочка возможна только внутри срока")
    paid = base[:after_month]
    balance = paid[-1].balance - amount
    if balance <= 0:
        raise ValueError("сумма досрочки закрывает кредит целиком")
    left = months - after_month
    if mode == "payment":
        tail = build_schedule(balance, rate_bp, left)
    else:
        tail = build_schedule(balance, rate_bp, left, payment=base[0].payment)
    interest = total_interest(paid) + total_interest(tail)
    return EarlyRepayment(mode, tail[0].payment, after_month + len(tail), interest,
                          total_interest(base) - interest)


@dataclass(frozen=True)
class PaymentDayChange:
    new_date: date
    days: int
    transition_interest: int


def change_payment_day(
    balance: int,
    rate_bp: int,
    last_payment: date,
    new_day: int,
    *,
    not_before: date | None = None,
) -> PaymentDayChange:
    if not 1 <= new_day <= 28:
        raise ValueError("дата платежа: с 1 по 28 число")
    y, m = last_payment.year, last_payment.month
    if new_day <= last_payment.day:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    new_date = date(y, m, new_day)
    if not_before is not None and new_date < not_before:
        new_date = date(not_before.year, not_before.month, new_day)
        if new_date < not_before:
            new_date = add_months(new_date, 1, new_day)
    days = (new_date - last_payment).days
    return PaymentDayChange(
        new_date,
        days,
        round_div(balance * rate_bp * days, BP * 365),
    )


def add_months(start: date, k: int, day: int) -> date:
    total = start.month - 1 + k
    return date(start.year + total // 12, total % 12 + 1, day)
