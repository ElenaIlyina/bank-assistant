from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from app.core import db
from app.repositories import jobs


def create_job(conn, cleanup_jobs, key):
    job_id = uuid4().hex
    cleanup_jobs.append(job_id)
    return jobs.create(
        conn, job_id, "payment_day", 1, {"new_day": 20}, key
    )


def test_same_key_returns_same_job(cleanup_jobs):
    key = uuid4().hex
    with db.connection() as conn:
        first, created = create_job(conn, cleanup_jobs, key)
        second, created_again = create_job(conn, cleanup_jobs, key)
        count = conn.execute(
            "SELECT count(*) FROM jobs WHERE idempotency_key = %s",
            (key,),
        ).fetchone()[0]
    assert first == second
    assert (created, created_again) == (True, False)
    assert count == 1


def test_different_keys_create_different_jobs(cleanup_jobs):
    with db.connection() as conn:
        first, created = create_job(conn, cleanup_jobs, uuid4().hex)
        second, created_again = create_job(conn, cleanup_jobs, uuid4().hex)
    assert first != second
    assert created is True
    assert created_again is True


def test_status_and_result(cleanup_jobs):
    with db.connection() as conn:
        job_id, _ = create_job(conn, cleanup_jobs, uuid4().hex)
        jobs.set_status(conn, job_id, "awaiting_staff", {"allowed": True})
        jobs.set_status(conn, job_id, "approved")
        row = jobs.get(conn, job_id)
    assert row is not None
    assert row["status"] == "approved"
    assert row["payload"] == {"new_day": 20}
    assert row["result"] == {"allowed": True}


def test_parallel_requests_return_same_job(cleanup_jobs):
    key = uuid4().hex
    ids = [uuid4().hex, uuid4().hex]
    cleanup_jobs.extend(ids)
    barrier = Barrier(2)

    def create(job_id):
        barrier.wait(timeout=5)
        with db.connection() as conn:
            return jobs.create(
                conn, job_id, "payment_day", 1, {"new_day": 20}, key
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(create, ids))

    assert len({job_id for job_id, _ in rows}) == 1
    assert sum(created for _, created in rows) == 1

