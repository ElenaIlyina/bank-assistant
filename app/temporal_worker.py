import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.worker import Worker

from app.core.config import settings
from app.core.logging import setup_logging
from app.temporal.activities import check_payment_day, set_job_status
from app.temporal.client import get_client
from app.temporal.workflows import PaymentDayWorkflow


async def main() -> None:
    setup_logging()
    client = await get_client()
    with ThreadPoolExecutor(max_workers=settings.temporal_activity_threads) as pool:
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[PaymentDayWorkflow],
            activities=[check_payment_day, set_job_status],
            activity_executor=pool,
            max_concurrent_activities=settings.temporal_activity_threads,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

