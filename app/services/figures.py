import json
import re

NUM = r"[+\-−]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)"
MONEY = re.compile(
    rf"(?<![\w.,+\-−])({NUM})(?:[.,](\d{{1,2}}))?\s*(?:₽|руб(?:лей|ля|ль|\.)?|RUB)(?!\w)",
    re.IGNORECASE,
)
NUMBER = re.compile(rf"(?<![\w.,+\-−])({NUM})(?:[.,](\d{{1,2}}))?(?![\w.,])")


def _kopecks(rub: str, kop: str | None) -> int:
    rub = re.sub(r"[ \u00a0\u202f]", "", rub).replace("−", "-")
    sign = -1 if rub.startswith("-") else 1
    return sign * (abs(int(rub)) * 100 + int((kop or "0").ljust(2, "0")))


def money_in(text: str) -> set[int]:
    return {_kopecks(rub, kop) for rub, kop in MONEY.findall(text)}


def numbers_in(text: str) -> set[int]:
    return {_kopecks(rub, kop) for rub, kop in NUMBER.findall(text)}


def tool_money(result) -> set[int]:
    amounts = set()
    for item in result.new_items:
        if item.type != "tool_call_output_item":
            continue
        output = item.output
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                pass
        text = json.dumps(output, ensure_ascii=False, default=str)
        amounts.update(money_in(text))
    return amounts

