import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from temporalio.client import WorkflowUpdateFailedError
from temporalio.service import RPCError
from temporalio.worker import Worker

from app.core import db
from app.repositories import jobs
from app.temporal.activities import check_payment_day, set_job_status
from app.temporal.client import get_client
from app.temporal.workflows import PaymentDayWorkflow


async def wait_status(handle, expected):
    async def poll():
        while True:
            status = await handle.query(PaymentDayWorkflow.status)
            if status == expected:
                return
            if status in ("approved", "rejected"):
                raise AssertionError(f"Ожидали {expected}, получили {status}")
            await asyncio.sleep(0.1)

    await asyncio.wait_for(poll(), timeout=15)


@pytest.mark.parametrize(
    "new_day,approve,final",
    [
        (20, True, "approved"),
        (20, False, "rejected"),
        (29, None, "rejected"),
    ],
)
async def test_payment_day_workflow(application_loan, new_day, approve, final):
    job_id = uuid4().hex
    with db.connection() as conn:
        jobs.create(
            conn,
            job_id,
            "payment_day",
            application_loan,
            {"new_day": new_day},
            job_id,
        )

    client = await get_client()
    queue = f"test-payment-day-{uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        async with Worker(
            client,
            task_queue=queue,
            workflows=[PaymentDayWorkflow],
            activities=[check_payment_day, set_job_status],
            activity_executor=pool,
            max_concurrent_activities=2,
        ):
            handle = client.get_workflow_handle(job_id)
            try:
                await client.start_workflow(
                    PaymentDayWorkflow.run,
                    args=[job_id, application_loan, new_day],
                    id=job_id,
                    task_queue=queue,
                )
                if approve is not None:
                    await wait_status(handle, "awaiting_staff")
                    with db.connection() as conn:
                        row = jobs.get(conn, job_id)
                    assert row["status"] == "awaiting_staff"
                    assert row["result"]["allowed"] is True
                    assert "transition_interest" in row["result"]
                    assert await handle.execute_update(
                        PaymentDayWorkflow.decide, approve
                    ) == final

                result = await asyncio.wait_for(handle.result(), timeout=20)
                assert result == final

                with pytest.raises((WorkflowUpdateFailedError, RPCError)):
                    await handle.execute_update(PaymentDayWorkflow.decide, True)
            finally:
                try:
                    await handle.terminate(reason="test cleanup")
                except RPCError:
                    pass

    with db.connection() as conn:
        row = jobs.get(conn, job_id)
    assert row["status"] == final
    assert row["result"]["allowed"] is (approve is not None)

