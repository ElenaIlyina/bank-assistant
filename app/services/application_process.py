from uuid import uuid4

from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core import db
from app.core.config import settings
from app.repositories import jobs as jobs_repo
from app.services import loans
from app.services.applications import PAYMENT_DAY
from app.temporal.client import get_client
from app.temporal.workflows import PaymentDayWorkflow


async def create_payment_day(
    loan_id: int,
    new_day: int,
    idempotency_key: str,
) -> dict | None:
    if loans.get_loan(loan_id) is None:
        return None
    with db.connection() as conn:
        job_id, _ = jobs_repo.create(
            conn,
            uuid4().hex,
            PAYMENT_DAY,
            loan_id,
            {"new_day": new_day},
            idempotency_key,
        )
        job = jobs_repo.get(conn, job_id)
    if job is None:
        raise RuntimeError("Созданная задача не найдена")
    if job["status"] == "pending":
        client = await get_client()
        try:
            await client.start_workflow(
                PaymentDayWorkflow.run,
                args=[job_id, job["loan_id"], job["payload"]["new_day"]],
                id=job_id,
                task_queue=settings.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            pass
    return job


async def decide(job_id: str, approve: bool) -> str:
    client = await get_client()
    handle = client.get_workflow_handle(job_id)
    return await handle.execute_update(PaymentDayWorkflow.decide, approve)

