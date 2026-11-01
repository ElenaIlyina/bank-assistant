from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assistant import AssistantAnswer
from app.services import assistant

client = TestClient(app)
ANSWER = AssistantAnswer(
    intent="other",
    answer="Нужны уточнения",
    confidence=0.9,
)


@pytest.mark.parametrize(
    "bad",
    [
        "Не JSON",
        '{"answer": "текст",,}',
        '{"intent": "wrong"}',
    ],
)
def test_answer_is_repaired(monkeypatch, bad):
    calls = []
    history = [
        {"role": "user", "content": "Вопрос"},
        {"role": "assistant", "content": bad},
    ]

    async def run(agent, prompt, context=None):
        calls.append((agent, prompt, context))
        text = bad if len(calls) == 1 else ANSWER.model_dump_json()
        return SimpleNamespace(
            final_output=text,
            new_items=[],
            to_input_list=lambda: history,
        )

    monkeypatch.setattr(assistant, "run_agent", run)
    resp = client.post("/ask", json={"loan_id": 1, "question": "Вопрос"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == ANSWER.answer
    assert len(calls) == 2
    assert calls[0][1] == "Вопрос"
    assert calls[1][1][:-1] == history
    assert calls[1][1][-1]["role"] == "user"
    assert calls[1][2].loan_id == 1
    assert calls[1][0].tools == []

