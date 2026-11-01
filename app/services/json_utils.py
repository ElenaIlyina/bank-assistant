import json
import re

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ModelJSONError(ValueError):
    pass


def strip_fence(text: str) -> str:
    fenced = FENCE.search(text)
    return fenced.group(1).strip() if fenced else text.strip()


def extract_json(text: str) -> dict:
    text = strip_fence(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise ModelJSONError("В ответе модели не найден JSON-объект") from None
        try:
            data, _ = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError as exc:
            raise ModelJSONError(
                f"Некорректный JSON в ответе модели: {exc.msg}"
            ) from exc
    if not isinstance(data, dict):
        raise ModelJSONError("Ответ модели должен содержать JSON-объект")
    return data

