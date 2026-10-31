"""Acceptance tests on the canonical reference figures (criterias.txt, hint_cents.txt)."""

from datetime import date

import pytest

from app.calculator import (
    EarlyRepayment,
    annuity_payment_kop,
    build_schedule,
    round_half_up,
)


class TestRoundHalfUp:
    def test_basic(self) -> None:
        assert round_half_up(5, 2) == 3  # 2.5 → 3 (half up)
        assert round_half_up(3, 2) == 2  # 1.5 → 2
        assert round_half_up(7, 2) == 4  # 3.5 → 4

    def test_negative_rounds_up(self) -> None:
        # -2.5 → -2 (half away from zero is NOT used; round half up toward +inf)
        assert round_half_up(-5, 2) == -2

    def test_zero_denominator(self) -> None:
        with pytest.raises(ValueError):
            round_half_up(1, 0)


class TestAnnuityPayment:
    def test_reference_figure(self) -> None:
        """Canonical example: 5,000,000 RUB at 12% (rate_bp=1200) for 240 months."""
        assert annuity_payment_kop(500_000_000, 1200, 240) == 5_505_431

    def test_zero_rate(self) -> None:
        assert annuity_payment_kop(1_200_000, 0, 12) == 100_000

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(ValueError):
            annuity_payment_kop(0, 1200, 12)
        with pytest.raises(ValueError):
            annuity_payment_kop(100, -5, 12)
        with pytest.raises(ValueError):
            annuity_payment_kop(100, 1200, 0)


class TestBuildSchedule:
    P = 500_000_000
    RATE = 1200
    MONTHS = 240

    def test_reference_shape(self) -> None:
        schedule = build_schedule(self.P, self.RATE, self.MONTHS, date(2026, 1, 15))
        assert len(schedule.rows) == self.MONTHS
        assert all(row.balance_kop > 0 for row in schedule.rows[:-1])
        assert schedule.rows[-1].balance_kop == 0
        regular = {row.payment_kop for row in schedule.rows[:-1]}
        assert regular == {5_505_431}

    def test_converges_to_kopeck(self) -> None:
        schedule = build_schedule(self.P, self.RATE, self.MONTHS, date(2026, 1, 15))
        assert sum(row.principal_kop for row in schedule.rows) == self.P
        assert schedule.rows[-1].payment_kop == (
            schedule.rows[-1].interest_kop + schedule.rows[-1].principal_kop
        )
        # last installment absorbs the remainder, it may differ from the annuity payment
        assert schedule.rows[-1].payment_kop <= 5_505_431

    def test_balance_chain(self) -> None:
        schedule = build_schedule(self.P, self.RATE, self.MONTHS, date(2026, 1, 15))
        balance = self.P
        for row in schedule.rows:
            interest = round_half_up(balance * self.RATE, 12 * 10_000)
            assert row.interest_kop == interest
            assert row.balance_kop == balance - row.principal_kop
            balance = row.balance_kop

    def test_interest_matches_hint_formula(self) -> None:
        """interest = round_half_up(balance * rate_bp, 12 * 10_000), exactly per hint_cents.txt."""
        schedule = build_schedule(self.P, self.RATE, self.MONTHS, date(2026, 1, 15))
        first = schedule.rows[0]
        assert first.interest_kop == round_half_up(self.P * self.RATE, 12 * 10_000)
        assert first.interest_kop == 5_000_000  # 1% of 500,000,000

    def test_reduce_term(self) -> None:
        er = EarlyRepayment(date(2027, 1, 15), 100_000_000)
        schedule = build_schedule(
            self.P, self.RATE, self.MONTHS, date(2026, 1, 15), [er], "reduce_term"
        )
        assert len(schedule.rows) < self.MONTHS
        assert schedule.rows[-1].balance_kop == 0
        assert sum(row.principal_kop for row in schedule.rows) == self.P
        # payment level unchanged
        regular = [row.payment_kop for row in schedule.rows if row.interest_kop > 0]
        assert set(regular[:-1]) == {5_505_431}

    def test_reduce_payment(self) -> None:
        er = EarlyRepayment(date(2027, 1, 15), 100_000_000)
        schedule = build_schedule(
            self.P, self.RATE, self.MONTHS, date(2026, 1, 15), [er], "reduce_payment"
        )
        assert schedule.rows[-1].balance_kop == 0
        assert sum(row.principal_kop for row in schedule.rows) == self.P
        # after the ER the payment is recalculated downward
        after = [r.payment_kop for r in schedule.rows if r.n > 12 and r.interest_kop > 0]
        assert max(after) < 5_505_431

    def test_workshop_reduce_payment_figure(self) -> None:
        """Workshop WS1 (p.10/33): 5 000 000 RUB, 12%, 240 mo, ER 500 000 RUB after 1 year,
        reduce_payment -> payment 4 947 738 kop (49 477.38 RUB), term stays 240,
        interest saving 771 538.25 RUB."""
        schedule = build_schedule(
            500_000_000,
            1200,
            240,
            date(2026, 1, 15),
            [EarlyRepayment(date(2027, 1, 15), 50_000_000)],
            "reduce_payment",
        )
        assert schedule.rows[-1].balance_kop == 0
        assert max(r.n for r in schedule.rows) == 240
        after = [r.payment_kop for r in schedule.rows if r.n > 12 and r.interest_kop > 0]
        assert after[0] == 4_947_738
        assert sum(r.principal_kop for r in schedule.rows) == 500_000_000
        no_er = build_schedule(500_000_000, 1200, 240, date(2026, 1, 15))
        saving = no_er.total_interest_kop - schedule.total_interest_kop
        assert saving == 77_153_825  # 771 538.25 RUB

    def test_multiple_early_repayments(self) -> None:
        ers = [
            EarlyRepayment(date(2026, 6, 15), 10_000_000),
            EarlyRepayment(date(2028, 3, 15), 200_000_000),
        ]
        for mode in ("reduce_term", "reduce_payment"):
            schedule = build_schedule(
                self.P, self.RATE, self.MONTHS, date(2026, 1, 15), list(ers), mode
            )
            assert schedule.rows[-1].balance_kop == 0
            assert sum(row.principal_kop for row in schedule.rows) == self.P

    def test_date_shift_month_end(self) -> None:
        """Jan 31 start clamps to Feb 28, then keeps day 31 from March."""
        schedule = build_schedule(600_000_000, self.RATE, 12, date(2026, 1, 31))
        dates = [row.payment_date for row in schedule.rows]
        assert dates[0] == date(2026, 2, 28)
        assert dates[1] == date(2026, 3, 31)
        assert dates[-1] == date(2027, 1, 31)
        assert schedule.rows[-1].balance_kop == 0

    def test_total_paid_equals_principal_plus_interest(self) -> None:
        schedule = build_schedule(self.P, self.RATE, self.MONTHS, date(2026, 1, 15))
        assert schedule.total_paid_kop == self.P + schedule.total_interest_kop
