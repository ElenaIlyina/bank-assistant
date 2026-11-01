from agents import MaxTurnsExceeded
from pydantic import ValidationError

from app.agents.prompts import assistant_agent
from app.agents.tools import ClientContext
from app.core.config import settings
from app.llm.client import run_agent
from app.schemas.assistant import AssistantAnswer
from app.services import loans
from app.services.figures import money_in, numbers_in, tool_money
from app.services.json_utils import ModelJSONError, extract_json

HANDOFF = AssistantAnswer(
    intent="other",
    answer="Не смог разобраться с вопросом, передаю его сотруднику банка.",
    needs_human=True,
    confidence=0,
)


async def ask(loan_id: int, question: str) -> AssistantAnswer | None:
    if loans.get_loan(loan_id) is None:
        return None
    context = ClientContext(loan_id)
    prompt = question
    agent = assistant_agent
    allowed = numbers_in(question)
    for attempt in range(2):
        try:
            result = await run_agent(agent, prompt, context)
        except MaxTurnsExceeded:
            return HANDOFF
        allowed.update(tool_money(result))
        try:
            answer = AssistantAnswer.model_validate(extract_json(result.final_output))
        except (ModelJSONError, ValidationError) as exc:
            error = str(exc)
        else:
            missing = money_in(answer.answer) - allowed
            if not missing:
                if answer.confidence < settings.confidence_threshold:
                    return answer.model_copy(update={"needs_human": True})
                return answer
            error = f"Неподтверждённые суммы в копейках: {sorted(missing)}"
        if attempt == 1:
            return HANDOFF
        prompt = result.to_input_list() + [
            {
                "role": "user",
                "content": f"Ответ не прошёл проверку: {error}. Верни корректный JSON по заданной схеме.",
            }
        ]
        agent = assistant_agent.clone(tools=[])
    return HANDOFF

