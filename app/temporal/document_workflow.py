from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from app.temporal.document_activities import (
        embed_document,
        parse_document,
        set_document_status,
    )

STEP_TIMEOUT = timedelta(seconds=30)
RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class DocumentWorkflow:
    @workflow.run
    async def run(self, document_id: str) -> str:
        try:
            await self._publish(document_id, "parsing")
            await workflow.execute_activity(
                parse_document,
                args=[document_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY,
            )
            await self._publish(document_id, "embedding")
            await workflow.execute_activity(
                embed_document,
                args=[document_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY,
            )
            await self._publish(document_id, "indexed")
        except ActivityError as exc:
            cause = exc.cause
            status = "failed"
            if isinstance(cause, ApplicationError):
                error = cause.message
                if cause.type == "DocumentRejected":
                    status = "rejected"
            else:
                error = str(cause or exc)
            await self._publish(document_id, status, error)
            return status
        return "indexed"

    async def _publish(
        self,
        document_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        await workflow.execute_activity(
            set_document_status,
            args=[document_id, status, error],
            start_to_close_timeout=STEP_TIMEOUT,
            retry_policy=RETRY,
        )

