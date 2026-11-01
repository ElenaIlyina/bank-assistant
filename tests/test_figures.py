import json
from types import SimpleNamespace

from app.services.figures import money_in, numbers_in, tool_money


def result_with(*outputs):
    return SimpleNamespace(
        new_items=[
            SimpleNamespace(type="tool_call_output_item", output=output)
            for output in outputs
        ]
    )


def test_money_in():
    text = "Платёж 49 477,38 ₽, экономия 771\u202f538.25 руб., возврат -10,50 ₽"
    assert money_in(text) == {4_947_738, 77_153_825, -1_050}


def test_numbers_in_question():
    assert numbers_in("Внесу 500 000 или 49\u202f477.38") == {
        50_000_000,
        4_947_738,
    }


def test_tool_money_reads_dict_and_json():
    result = result_with(
        {"new_payment": "49 477,38 ₽"},
        json.dumps({"saved": "771\u00a0538,25 ₽"}),
    )
    assert tool_money(result) == {4_947_738, 77_153_825}


def test_model_message_is_not_tool_output():
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(type="message_output_item", output="48 900 ₽"),
        ]
    )
    assert tool_money(result) == set()
