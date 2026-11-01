from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.core import db
from app.repositories import jobs
from app.services import applications

TODAY = date(2026, 10, 20)


@pytest.fixture
def no_previous_change(monkeypatch):
    monkeypatch.setattr(
        applications.jobs_repo,
        "last_approved_at",
        lambda *args: None,
    )


def test_allowed_with_transition_interest(no_previous_change):
    check = applications.check_payment_day(1, 20, today=TODAY)
    assert check["allowed"] is True
    assert check["new_payment_date"] == "2026-10-20"
    assert check["transition_days"] == 5
    assert check["transition_interest"] == "8 113,81 ₽"


def test_same_day_rejected():
    check = applications.check_payment_day(1, 15, today=TODAY)
    assert check["allowed"] is False


@pytest.mark.parametrize("day", [0, 29])
def test_day_out_of_range(day):
    check = applications.check_payment_day(1, day, today=TODAY)
    assert check["allowed"] is False
    assert "с 1 по 28" in check["reason"]


def test_unknown_loan():
    check = applications.check_payment_day(999999, 20, today=TODAY)
    assert check["allowed"] is False


@pytest.mark.parametrize(
    "last,today,allowed",
    [
        (datetime(2025, 10, 20, tzinfo=UTC), date(2026, 10, 19), False),
        (datetime(2025, 10, 20, tzinfo=UTC), date(2026, 10, 20), True),
        (datetime(2027, 3, 1, tzinfo=UTC), date(2028, 2, 29), False),
        (datetime(2028, 2, 29, tzinfo=UTC), date(2029, 2, 28), True),
    ],
)
def test_calendar_year_rule(monkeypatch, last, today, allowed):
    monkeypatch.setattr(
        applications.jobs_repo,
        "last_approved_at",
        lambda *args: last,
    )
    check = applications.check_payment_day(1, 20, today=today)
    assert check["allowed"] is allowed


def test_recent_approved_job_blocks_change(cleanup_jobs):
    job_id = uuid4().hex
    cleanup_jobs.append(job_id)
    with db.connection() as conn:
        jobs.create(
            conn, job_id, applications.PAYMENT_DAY,
            1, {"new_day": 10}, uuid4().hex,
        )
        jobs.set_status(conn, job_id, "approved")
        conn.execute(
            "UPDATE jobs SET updated_at = %s WHERE id = %s",
            (datetime(2026, 10, 19, tzinfo=UTC), job_id),
        )
    check = applications.check_payment_day(1, 20, today=TODAY)
    assert check["allowed"] is False
    assert "12 месяцев" in check["reason"]


def test_new_payment_date_is_not_in_past(no_previous_change):
    check = applications.check_payment_day(1, 20, today=date(2026, 10, 31))
    assert check["allowed"] is True
    assert check["new_payment_date"] == "2026-11-20"
    assert check["transition_days"] == 36

