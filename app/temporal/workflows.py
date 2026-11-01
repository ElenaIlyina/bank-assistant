from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import check_payment_day, set_job_status

STEP_TIMEOUT = timedelta(seconds=30)
RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class PaymentDayWorkflow:
    def __init__(self) -> None:
        self._status = "checking"
        self._approved: bool | None = None

    @workflow.run
    async def run(self, job_id: str, loan_id: int, new_day: int) -> str:
        check = await workflow.execute_activity(
            check_payment_day,
            args=[loan_id, new_day],
            start_to_close_timeout=STEP_TIMEOUT,
            retry_policy=RETRY,
        )
        if not check["allowed"]:
            await self._publish(job_id, "rejected", check)
            return self._status
        await self._publish(job_id, "awaiting_staff", check)
        await workflow.wait_condition(lambda: self._approved is not None)
        status = "approved" if self._approved else "rejected"
        await self._publish(job_id, status, None)
        return self._status

    async def _publish(
        self,
        job_id: str,
        status: str,
        result: dict | None,
    ) -> None:
        await workflow.execute_activity(
            set_job_status,
            args=[job_id, status, result],
            start_to_close_timeout=STEP_TIMEOUT,
            retry_policy=RETRY,
        )
        self._status = status

    @workflow.update
    def decide(self, approve: bool) -> str:
        self._approved = approve
        return "approved" if approve else "rejected"

    @decide.validator
    def check_decide(self, approve: bool) -> None:
        if self._status != "awaiting_staff" or self._approved is not None:
            raise ValueError(
                f"Заявление в статусе {self._status}, решение не принимается"
            )

    @workflow.query
    def status(self) -> str:
        return self._status

