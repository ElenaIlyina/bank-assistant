from types import SimpleNamespace

import pytest
from agents import MaxTurnsExceeded
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assistant import AssistantAnswer
from app.services import assistant

client = TestClient(app)

ANSWER = AssistantAnswer(intent="early_repayment", answer="Новый платеж 49 477,38 ₽", confidence=0.9)


def agent_result(text, *outputs):
    return SimpleNamespace(
        final_output=text,
        new_items=[
            SimpleNamespace(type="tool_call_output_item", output=output)
            for output in outputs
        ],
        to_input_list=lambda: [
            {"role": "assistant", "content": text},
        ],
    )


@pytest.fixture
def fake_agent(monkeypatch):
    calls = []

    async def run(agent, prompt, context=None):
        calls.append(context)
        return agent_result(
            ANSWER.model_dump_json(),
            {"new_payment": "49 477,38 ₽"},
        )

    monkeypatch.setattr(assistant, "run_agent", run)
    return calls


def test_ask_passes_loan_in_context(fake_agent):
    resp = client.post("/ask", json={"loan_id": 1, "question": "Какой будет платеж после досрочки?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == ANSWER.answer
    assert fake_agent[0].loan_id == 1


def test_ask_unknown_loan(fake_agent):
    assert client.post("/ask", json={"loan_id": 999999, "question": "?"}).status_code == 404
    assert fake_agent == []


def test_turn_budget_goes_to_human(monkeypatch):
    async def run(agent, prompt, context=None):
        raise MaxTurnsExceeded("6 ходов")

    monkeypatch.setattr(assistant, "run_agent", run)
    body = client.post("/ask", json={"loan_id": 1, "question": "..."}).json()
    assert body["needs_human"] is True


def test_answer_not_in_format(monkeypatch):
    calls = []

    async def run(agent, prompt, context=None):
        calls.append(prompt)
        assert len(calls) <= 2
        return agent_result("Не JSON")

    monkeypatch.setattr(assistant, "run_agent", run)
    resp = client.post("/ask", json={"loan_id": 1, "question": "..."})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is True
    assert len(calls) == 2


def test_fenced_answer_is_accepted(monkeypatch):
    async def run(agent, prompt, context=None):
        return agent_result(
            "```json\n" + ANSWER.model_dump_json() + "\n```",
            {"new_payment": "49 477,38 ₽"},
        )

    monkeypatch.setattr(assistant, "run_agent", run)
    assert client.post("/ask", json={"loan_id": 1, "question": "..."}).json()["answer"] == ANSWER.answer
