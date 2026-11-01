from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas.assistant import AskRequest, AssistantAnswer
from app.services import assistant
from app.services.json_utils import ModelJSONError

router = APIRouter(tags=["assistant"])


@router.post("/ask", response_model=AssistantAnswer)
async def ask(body: AskRequest):
    try:
        answer = await assistant.ask(body.loan_id, body.question)
    except ModelJSONError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(502, "ответ модели не по формату") from exc
    if answer is None:
        raise HTTPException(404, "кредит не найден")
    return answer

