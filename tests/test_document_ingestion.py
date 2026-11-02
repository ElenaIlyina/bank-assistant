from pathlib import Path
from uuid import uuid4

import pytest

from app.core import db
from app.parsers.blocks import NoTextLayer, ParseError
from app.repositories import chunks, documents
from app.services import document_ingestion as ingestion
from app.services.documents import UnsupportedFormat

DATA = Path(__file__).resolve().parent.parent / "data"


def store_file(cleanup_documents, filename, content=None):
    if content is None:
        content = (DATA / filename).read_bytes()
    content += b"\n% test: " + uuid4().hex.encode() + b"\n"
    document_id = uuid4().hex
    cleanup_documents.append(document_id)
    with db.connection() as conn:
        _, created = documents.create(
            conn, document_id, filename, content
        )
    assert created is True
    return document_id


@pytest.fixture
def fake_embeddings(monkeypatch):
    calls = []

    def encode(items):
        calls.append([row["id"] for row in items])
        return [[1.0] + [0.0] * 767 for _ in items]

    monkeypatch.setattr(ingestion.embeddings, "embed_documents", encode)
    return calls


@pytest.mark.parametrize(
    "filename",
    [
        "credit_agreement.pdf",
        "payment_date_reglament.pdf",
        "early_repayment_rules.docx",
        "tariffs.xlsx",
        "client_application.docx",
    ],
)
def test_text_files_are_parsed(cleanup_documents, filename):
    document_id = store_file(cleanup_documents, filename)
    count = ingestion.parse_document(document_id)
    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)
    assert count > 0
    assert len(rows) == count


def test_scan_is_rejected(cleanup_documents):
    document_id = store_file(
        cleanup_documents, "income_statement_scan.pdf"
    )
    with pytest.raises(NoTextLayer):
        ingestion.parse_document(document_id)
    with db.connection() as conn:
        assert chunks.list_for_document(conn, document_id) == []


def test_unsupported_format(cleanup_documents):
    document_id = store_file(
        cleanup_documents, "file.txt", b"Unsupported file"
    )
    with pytest.raises(UnsupportedFormat):
        ingestion.parse_document(document_id)


def test_empty_parse_is_rejected(monkeypatch, cleanup_documents):
    document_id = store_file(
        cleanup_documents, "empty.pdf", b"Unused"
    )
    monkeypatch.setattr(ingestion, "parse", lambda *args: [])
    with pytest.raises(ParseError, match="нет текстовых"):
        ingestion.parse_document(document_id)


def test_parse_retry_preserves_chunks(monkeypatch, cleanup_documents):
    document_id = store_file(cleanup_documents, "credit_agreement.pdf")
    count = ingestion.parse_document(document_id)
    with db.connection() as conn:
        before = chunks.list_for_document(conn, document_id)

    def blocked(*args):
        raise AssertionError("Повторный разбор не требуется")

    monkeypatch.setattr(ingestion, "parse", blocked)
    assert ingestion.parse_document(document_id) == count
    with db.connection() as conn:
        after = chunks.list_for_document(conn, document_id)
    assert after == before


def test_embedding_is_idempotent(cleanup_documents, fake_embeddings):
    document_id = store_file(cleanup_documents, "credit_agreement.pdf")
    count = ingestion.parse_document(document_id)
    assert ingestion.embed_document(document_id) == count
    assert ingestion.embed_document(document_id) == 0
    assert len(fake_embeddings) == 1


def test_other_model_is_recomputed(monkeypatch, cleanup_documents, fake_embeddings):
    document_id = store_file(cleanup_documents, "credit_agreement.pdf")
    count = ingestion.parse_document(document_id)
    assert ingestion.embed_document(document_id) == count
    monkeypatch.setattr(
        ingestion.settings, "embedding_model", "test-other-model"
    )
    assert ingestion.embed_document(document_id) == count
    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)
    assert len(fake_embeddings) == 2
    assert all(row["embedding_model"] == "test-other-model" for row in rows)


def test_only_missing_vectors_are_computed(cleanup_documents, fake_embeddings):
    document_id = store_file(cleanup_documents, "credit_agreement.pdf")
    count = ingestion.parse_document(document_id)
    assert count > 1
    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)
        chunks.save_embeddings(
            conn,
            [(rows[0]["id"], [1.0] + [0.0] * 767)],
            ingestion.settings.embedding_model,
        )
    assert ingestion.embed_document(document_id) == count - 1
    assert fake_embeddings == [[row["id"] for row in rows[1:]]]
    assert ingestion.embed_document(document_id) == 0

