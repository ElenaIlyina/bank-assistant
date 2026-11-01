import json

import pytest

from app.services.json_utils import ModelJSONError, extract_json

DATA = {
    "intent": "other",
    "answer": "Нужны уточнения",
    "needs_human": True,
    "confidence": 0.4,
}
JSON = json.dumps(DATA, ensure_ascii=False)


@pytest.mark.parametrize(
    "text",
    [
        JSON,
        f"```json\n{JSON}\n```",
        f"Вот ответ:\n{JSON}\nКонец ответа.",
    ],
)
def test_extract_json(text):
    assert extract_json(text) == DATA


def test_extract_json_rejects_garbage():
    with pytest.raises(ModelJSONError, match="Некорректный JSON"):
        extract_json('{"answer": "текст",,}')
