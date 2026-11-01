from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assistant import AssistantAnswer
from app.services import assistant

client = TestClient(app)


@pytest.mark.parametrize(
    "threshold,confidence,human,expected",
    [
        (0.6, 0.3, False, True),
        (0.6, 0.6, False, False),
        (0.6, 0.9, False, False),
        (0.6, 0.9, True, True),
        (0.95, 0.9, False, True),
    ],
)
def test_confidence_threshold(monkeypatch, threshold, confidence, human, expected):
    monkeypatch.setattr(assistant.settings, "confidence_threshold", threshold)
    calls = []
    answer = AssistantAnswer(
        intent="other",
        answer="Уточните вопрос",
        needs_human=human,
        confidence=confidence,
    )

    async def run(agent, prompt, context=None):
        calls.append(prompt)
        return SimpleNamespace(
            final_output=answer.model_dump_json(),
            new_items=[],
        )

    monkeypatch.setattr(assistant, "run_agent", run)
    resp = client.post("/ask", json={"loan_id": 1, "question": "Вопрос"})
    assert resp.status_code == 200
    assert resp.json()["needs_human"] is expected
    assert resp.json()["confidence"] == confidence
    assert len(calls) == 1
