from uuid import uuid4

import pytest

from app.core import db
from app.core.config import settings
from app.parsers.chunker import Chunk
from app.repositories import chunks, documents
from app.services import document_ingestion, reindex


@pytest.fixture
def document_id(cleanup_documents, monkeypatch):
    document_id = uuid4().hex
    cleanup_documents.append(document_id)

    items = [
        Chunk(
            ordinal=i,
            text=f"Текст {i}",
            kind="paragraph",
            section="Условия",
            page=1,
            sheet=None,
            row=None,
            program_code=None,
        )
        for i in range(2)
    ]

    with db.connection() as conn:
        documents.create(
            conn,
            document_id,
            "reindex.txt",
            uuid4().hex.encode(),
        )
        chunks.replace(conn, document_id, items)

    original = chunks.documents_to_reindex

    def only_test_document(conn, model):
        return [
            item
            for item in original(conn, model)
            if item == document_id
        ]

    monkeypatch.setattr(
        reindex.chunks,
        "documents_to_reindex",
        only_test_document,
    )
    return document_id


@pytest.fixture
def embed_calls(monkeypatch):
    calls = []

    def embed(items):
        calls.append([item["id"] for item in items])
        return [[1.0] + [0.0] * 767 for _ in items]

    monkeypatch.setattr(
        document_ingestion.embeddings,
        "embed_documents",
        embed,
    )
    return calls


def test_missing_vectors_and_repeated_run(document_id, embed_calls):
    assert reindex.reindex_documents() == 2
    assert reindex.reindex_documents() == 0
    assert len(embed_calls) == 1

    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)

    assert all(row["embedding"] is not None for row in rows)
    assert all(
        row["embedding_model"] == settings.embedding_model
        for row in rows
    )


def test_vectors_from_another_model(document_id, embed_calls):
    old_vector = [0.0, 1.0] + [0.0] * 766

    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)
        chunks.save_embeddings(
            conn,
            [(row["id"], old_vector) for row in rows],
            "old-model",
        )

    assert reindex.reindex_documents() == 2
    assert len(embed_calls) == 1

    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)

    assert all(
        row["embedding_model"] == settings.embedding_model
        for row in rows
    )
    assert all(row["embedding"][0] == 1.0 for row in rows)


def test_current_vector_is_preserved(document_id, embed_calls):
    current_vector = [0.0, 1.0] + [0.0] * 766

    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)
        first_id = rows[0]["id"]
        second_id = rows[1]["id"]
        chunks.save_embeddings(
            conn,
            [(first_id, current_vector)],
            settings.embedding_model,
        )

    assert reindex.reindex_documents() == 1
    assert embed_calls == [[second_id]]

    with db.connection() as conn:
        rows = chunks.list_for_document(conn, document_id)

    assert rows[0]["embedding"] == current_vector
    assert rows[1]["embedding"][0] == 1.0

