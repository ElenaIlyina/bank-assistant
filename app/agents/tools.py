from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import uuid4

from agents import RunContextWrapper, function_tool
from pydantic import Field

from app.services import application_process, applications, loans


@dataclass
class ClientContext:
    loan_id: int
    request_id: str = field(default_factory=lambda: uuid4().hex)


def _loan(ctx: RunContextWrapper[ClientContext]):
    loan = loans.get_loan(ctx.context.loan_id)
    if loan is None:
        raise ValueError("кредит не найден")
    return loan


@function_tool(description_override="Условия кредита клиента: сумма, ставка, срок, дата выдачи, день и размер платежа.")
def get_loan(ctx: RunContextWrapper[ClientContext]) -> dict:
    return loans.loan_terms(_loan(ctx))


@function_tool(description_override="Строки графика платежей: дата, платеж, проценты, тело долга, остаток после платежа.")
def get_schedule(
    ctx: RunContextWrapper[ClientContext],
    from_month: Annotated[int, Field(ge=1, description="номер первого платежа")] = 1,
    count: Annotated[int, Field(ge=1, le=12, description="сколько платежей показать")] = 3,
) -> list[dict]:
    return loans.schedule_slice(_loan(ctx), from_month, count)


@function_tool(
    description_override="Посчитать досрочное погашение: новый платеж или срок и экономию на процентах."
)
def simulate_early_repayment(
    ctx: RunContextWrapper[ClientContext],
    after_month: Annotated[int, Field(ge=1, description="номер платежа, после которого вносим деньги")],
    amount_rub: Annotated[int, Field(gt=0, description="сумма досрочного погашения в рублях")],
    mode: Annotated[Literal["term", "payment"], Field(description="term – сократить срок, payment – уменьшить платеж")],
) -> dict:
    return loans.simulate_early_repayment(_loan(ctx), after_month, amount_rub * 100, mode)


@function_tool(
    description_override="Проверить возможность смены даты платежа и проценты переходного периода."
)
def check_payment_date_change(
    ctx: RunContextWrapper[ClientContext],
    new_day: Annotated[int, Field(description="новое число месяца для платежа")],
) -> dict:
    return applications.check_payment_day(_loan(ctx).id, new_day)


@function_tool(
    description_override="Подать заявление на смену даты платежа по явной просьбе клиента."
)
async def create_payment_date_application(
    ctx: RunContextWrapper[ClientContext],
    new_day: Annotated[int, Field(ge=1, le=28, description="новое число месяца")],
) -> dict:
    loan_id = _loan(ctx).id
    key = f"ask:{ctx.context.request_id}:{loan_id}:{new_day}"
    job = await application_process.create_payment_day(loan_id, new_day, key)
    if job is None:
        raise ValueError("кредит не найден")
    return {"job_id": job["id"], "status": job["status"]}


TOOLS = [
    get_loan,
    get_schedule,
    simulate_early_repayment,
    check_payment_date_change,
    create_payment_date_application,
]
