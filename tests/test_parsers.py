from pathlib import Path

import pytest

from app.parsers.blocks import NoTextLayer
from app.parsers.chunker import split_text
from app.services.documents import UnsupportedFormat, parse

DATA = Path(__file__).resolve().parent.parent / "data"


def chunks(name):
    return parse(name, (DATA / name).read_bytes())


def test_running_header_and_footer_removed():
    text = " ".join(c.text for c in chunks("credit_agreement.pdf"))
    assert "Страница" not in text
    assert "Банк «Ипотека Плюс»" not in text


def test_hyphenation_joined():
    text = " ".join(c.text for c in chunks("credit_agreement.pdf"))
    assert "не позднее чем за 1 рабочий день" in text
    assert "позд-" not in text


def test_section_and_page_metadata():
    early = next(c for c in chunks("credit_agreement.pdf") if "досрочно" in c.text)
    assert (early.section, early.page) == ("3. Досрочное погашение", 2)


def test_two_page_document_keeps_body():
    sections = {c.section for c in chunks("payment_date_reglament.pdf")}
    assert {"2. Условия изменения даты", "3. Расчет процентов за переходный период"} <= sections


def test_table_row_is_one_chunk_with_headers():
    row = next(c for c in chunks("tariffs.xlsx") if c.program_code == "IP-FAMILY-6")
    assert "Ставка, % годовых: 6" in row.text
    assert (row.sheet, row.row) == ("Программы", 3)


def test_docx_headings_are_sections():
    assert {c.section for c in chunks("early_repayment_rules.docx")} >= {"Минимальная сумма", "Комиссии"}


def test_hidden_text_is_still_parsed():
    assert any("SYSTEM:" in c.text for c in chunks("client_application.docx"))


def test_scan_is_rejected():
    with pytest.raises(NoTextLayer):
        chunks("income_statement_scan.pdf")


def test_unsupported_format():
    with pytest.raises(UnsupportedFormat):
        parse("photo.jpg", b"")


def test_split_text_overlaps_without_cutting_words():
    text = " ".join(f"слово{i}" for i in range(300))
    pieces = split_text(text, size=200, overlap=50)
    assert len(pieces) > 1
    assert all(len(p) <= 200 for p in pieces)
    assert all(w.startswith("слово") for p in pieces for w in p.split())
    assert pieces[0].split()[-1] in pieces[1]
