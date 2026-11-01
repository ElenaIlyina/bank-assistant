from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assistant import AssistantAnswer
from app.services import assistant

client = TestClient(app)


def stub_agent(monkeypatch, responses):
    calls = []

    async def run(agent, prompt, context=None):
        calls.append(prompt)
        assert len(calls) <= len(responses)
        text, outputs = responses[len(calls) - 1]
        raw = AssistantAnswer(
            intent="early_repayment",
            answer=text,
            confidence=0.9,
        ).model_dump_json()
        return SimpleNamespace(
            final_output=raw,
            new_items=[
                SimpleNamespace(type="tool_call_output_item", output=output)
                for output in outputs
            ],
            to_input_list=lambda: [
                {"role": "assistant", "content": raw},
            ],
        )

    monkeypatch.setattr(assistant, "run_agent", run)
    return calls


def test_money_from_tool_is_allowed(monkeypatch):
    calls = stub_agent(monkeypatch, [
        ("Новый платёж 49477.38 руб.", [{"payment": "49 477,38 ₽"}]),
    ])
    resp = client.post("/ask", json={"loan_id": 1, "question": "Какой платёж?"})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is False
    assert len(calls) == 1


def test_money_from_question_is_allowed(monkeypatch):
    calls = stub_agent(monkeypatch, [
        ("Внесите 500 000 ₽", []),
    ])
    resp = client.post("/ask", json={"loan_id": 1, "question": "Внесу 500 000"})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is False
    assert len(calls) == 1


def test_invented_money_twice_goes_to_human(monkeypatch):
    calls = stub_agent(monkeypatch, [
        ("Новый платёж 48 900 ₽", [{"payment": "49 477,38 ₽"}]),
        ("Новый платёж 48 000 ₽", []),
    ])
    resp = client.post("/ask", json={"loan_id": 1, "question": "Какой платёж?"})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is True
    assert len(calls) == 2


def test_repair_keeps_previous_tool_money(monkeypatch):
    calls = stub_agent(monkeypatch, [
        ("Новый платёж 48 900 ₽", [{"payment": "49 477,38 ₽"}]),
        ("Новый платёж 49 477,38 ₽", []),
    ])
    resp = client.post("/ask", json={"loan_id": 1, "question": "Какой платёж?"})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is False
    assert len(calls) == 2

