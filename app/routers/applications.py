from fastapi import APIRouter, Header, HTTPException
from temporalio.client import WorkflowUpdateFailedError
from temporalio.service import RPCError

from app.schemas.applications import Decision, Job, PaymentDayRequest
from app.services import application_process, applications

router = APIRouter(tags=["applications"])


@router.post("/applications/payment-day", status_code=202, response_model=Job)
async def create_payment_day(
    body: PaymentDayRequest,
    idempotency_key: str = Header(min_length=1, max_length=200),
):
    try:
        job = await application_process.create_payment_day(
            body.loan_id, body.new_day, idempotency_key
        )
    except (RPCError, OSError, RuntimeError) as exc:
        raise HTTPException(
            503,
            "Не удалось запустить процесс. Повторите запрос с тем же Idempotency-Key",
        ) from exc
    if job is None:
        raise HTTPException(404, "кредит не найден")
    return job


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = applications.get_job(job_id)
    if job is None:
        raise HTTPException(404, "задача не найдена")
    return job


@router.post("/applications/{job_id}/decision")
async def decide(job_id: str, body: Decision):
    job = applications.get_job(job_id)
    if job is None:
        raise HTTPException(404, "заявление не найдено")
    if job["status"] in ("approved", "rejected"):
        raise HTTPException(409, "решение по заявлению уже принято")
    try:
        status = await application_process.decide(job_id, body.approve)
    except WorkflowUpdateFailedError as exc:
        raise HTTPException(409, str(exc.cause or exc)) from exc
    except RPCError as exc:
        latest = applications.get_job(job_id)
        if latest is not None and latest["status"] in ("approved", "rejected"):
            raise HTTPException(409, "решение по заявлению уже принято") from exc
        raise HTTPException(503, "Temporal временно недоступен") from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, "Temporal временно недоступен") from exc
    return {"status": status}

