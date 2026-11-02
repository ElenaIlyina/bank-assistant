from uuid import uuid4

import pytest
from psycopg import DataError
from psycopg.errors import UniqueViolation

from app.core import db
from app.parsers.chunker import Chunk
from app.repositories import chunks, documents


def create_document(conn, cleanup_documents):
    document_id = uuid4().hex
    cleanup_documents.append(document_id)
    documents.create(conn, document_id, "file.pdf", uuid4().hex.encode())
    return document_id


def item(ordinal=0, text="Фрагмент"):
    return Chunk(
        ordinal=ordinal,
        text=text,
        kind="paragraph",
        section="Правила",
        page=2,
        sheet=None,
        row=None,
        program_code=None,
    )


def vector(index):
    return [float(i == index) for i in range(768)]


def test_metadata_and_order(cleanup_documents):
    table = Chunk(
        ordinal=1,
        text="Код программы: IP-FAMILY-6",
        kind="row",
        section="Программы",
        page=None,
        sheet="Программы",
        row=3,
        program_code="IP-FAMILY-6",
    )
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        assert chunks.replace(conn, document_id, [table, item()]) == 2
        rows = chunks.list_for_document(conn, document_id)
    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["section"] == "Правила"
    assert rows[0]["page"] == 2
    assert rows[0]["embedding"] is None
    assert rows[0]["embedding_model"] is None
    assert rows[1]["kind"] == "row"
    assert rows[1]["sheet"] == "Программы"
    assert rows[1]["row_number"] == 3
    assert rows[1]["program_code"] == "IP-FAMILY-6"


def test_replace_affects_only_selected_document(cleanup_documents):
    with db.connection() as conn:
        first = create_document(conn, cleanup_documents)
        second = create_document(conn, cleanup_documents)
        chunks.replace(conn, first, [item(), item(1)])
        chunks.replace(conn, second, [item(text="Другой документ")])
        chunks.replace(conn, first, [item(text="Новая версия")])
        first_rows = chunks.list_for_document(conn, first)
        second_rows = chunks.list_for_document(conn, second)
    assert len(first_rows) == 1
    assert first_rows[0]["text"] == "Новая версия"
    assert second_rows[0]["text"] == "Другой документ"


def test_failed_replacement_preserves_chunks(cleanup_documents):
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        chunks.replace(conn, document_id, [item()])
        before = chunks.list_for_document(conn, document_id)
        with pytest.raises(UniqueViolation):
            chunks.replace(conn, document_id, [item(), item()])
        after = chunks.list_for_document(conn, document_id)
    assert after == before


def test_save_and_read_vectors(cleanup_documents):
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        chunks.replace(conn, document_id, [item(), item(1)])
        rows = chunks.list_for_document(conn, document_id)
        count = chunks.save_embeddings(
            conn,
            [(rows[0]["id"], vector(0)), (rows[1]["id"], vector(1))],
            "test-model",
        )
        saved = chunks.list_for_document(conn, document_id)
    assert count == 2
    assert saved[0]["embedding"] == vector(0)
    assert saved[1]["embedding"] == vector(1)
    assert all(row["embedding_model"] == "test-model" for row in saved)


def test_wrong_vector_dimension_rolls_back_batch(cleanup_documents):
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        chunks.replace(conn, document_id, [item(), item(1)])
        before = chunks.list_for_document(conn, document_id)
        with pytest.raises(DataError):
            chunks.save_embeddings(
                conn,
                [(before[0]["id"], vector(0)), (before[1]["id"], [1.0])],
                "test-model",
            )
        after = chunks.list_for_document(conn, document_id)
    assert after == before


def test_unknown_chunk_rolls_back_batch(cleanup_documents):
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        chunks.replace(conn, document_id, [item()])
        before = chunks.list_for_document(conn, document_id)
        with pytest.raises(ValueError, match="не найдена"):
            chunks.save_embeddings(
                conn,
                [(before[0]["id"], vector(0)), (-1, vector(1))],
                "test-model",
            )
        after = chunks.list_for_document(conn, document_id)
    assert after == before


def test_full_text_column_is_updated(cleanup_documents):
    with db.connection() as conn:
        document_id = create_document(conn, cleanup_documents)
        chunks.replace(conn, document_id, [item(text="Изменение даты платежа")])
        found = conn.execute(
            """
            SELECT count(*) FROM chunks
            WHERE document_id = %s
              AND search_vector @@ plainto_tsquery('russian', 'изменения')
            """,
            (document_id,),
        ).fetchone()[0]
        chunks.replace(conn, document_id, [item(text="Комиссия по кредиту")])
        remaining = conn.execute(
            """
            SELECT count(*) FROM chunks
            WHERE document_id = %s
              AND search_vector @@ plainto_tsquery('russian', 'изменения')
            """,
            (document_id,),
        ).fetchone()[0]
    assert found == 1
    assert remaining == 0

