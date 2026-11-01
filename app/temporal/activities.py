from temporalio import activity

from app.core import db
from app.repositories import jobs as jobs_repo
from app.services import applications


@activity.defn
def check_payment_day(loan_id: int, new_day: int) -> dict:
    return applications.check_payment_day(loan_id, new_day)


@activity.defn
def set_job_status(job_id: str, status: str, result: dict | None) -> None:
    with db.connection() as conn:
        jobs_repo.set_status(conn, job_id, status, result)

