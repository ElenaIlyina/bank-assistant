from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from app.core import db
from app.repositories import documents


def create_document(conn, cleanup_documents, filename, content):
    document_id = uuid4().hex
    cleanup_documents.append(document_id)
    return documents.create(conn, document_id, filename, content)


def test_same_content_returns_same_document(cleanup_documents):
    content = uuid4().hex.encode()
    with db.connection() as conn:
        first, created = create_document(
            conn, cleanup_documents, "first.pdf", content
        )
        second, created_again = create_document(
            conn, cleanup_documents, "renamed.pdf", content
        )
        row = documents.get(conn, first)
        count = conn.execute(
            "SELECT count(*) FROM documents WHERE content = %s",
            (content,),
        ).fetchone()[0]
    assert first == second
    assert (created, created_again) == (True, False)
    assert count == 1
    assert row["filename"] == "first.pdf"


def test_different_content_creates_different_documents(cleanup_documents):
    prefix = uuid4().hex.encode()
    with db.connection() as conn:
        first, created = create_document(
            conn, cleanup_documents, "file.pdf", prefix + b"1"
        )
        second, created_again = create_document(
            conn, cleanup_documents, "file.pdf", prefix + b"2"
        )
    assert first != second
    assert created is True
    assert created_again is True


def test_metadata_and_content_are_read_separately(cleanup_documents):
    content = b"\x00\xff" + uuid4().hex.encode()
    with db.connection() as conn:
        document_id, _ = create_document(
            conn, cleanup_documents, "file.pdf", content
        )
        row = documents.get(conn, document_id)
        original = documents.get_content(conn, document_id)
    assert row["status"] == "uploaded"
    assert row["error"] is None
    assert "content" not in row
    assert original == content


def test_status_and_error(cleanup_documents):
    with db.connection() as conn:
        document_id, _ = create_document(
            conn, cleanup_documents, "scan.pdf", uuid4().hex.encode()
        )
        documents.set_status(conn, document_id, "rejected", "Нет текстового слоя")
        rejected = documents.get(conn, document_id)
        documents.set_status(conn, document_id, "parsing")
        retried = documents.get(conn, document_id)
    assert rejected["status"] == "rejected"
    assert rejected["error"] == "Нет текстового слоя"
    assert retried["status"] == "parsing"
    assert retried["error"] is None


def test_parallel_uploads_return_same_document(cleanup_documents):
    content = uuid4().hex.encode()
    ids = [uuid4().hex, uuid4().hex]
    cleanup_documents.extend(ids)
    barrier = Barrier(2)

    def create(document_id):
        barrier.wait(timeout=5)
        with db.connection() as conn:
            return documents.create(conn, document_id, "file.pdf", content)

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(create, ids))

    assert len({document_id for document_id, _ in rows}) == 1
    assert sum(created for _, created in rows) == 1

