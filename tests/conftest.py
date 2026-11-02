from datetime import date
from uuid import uuid4

import pytest

from app.core import db
from app.llm import embeddings


@pytest.fixture
def cleanup_jobs():
    ids = []
    yield ids
    if ids:
        with db.connection() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ANY(%s)", (ids,))


@pytest.fixture
def application_loan():
    with db.connection() as conn, conn.transaction():
        client_id = conn.execute(
            "INSERT INTO clients (full_name) VALUES (%s) RETURNING id",
            (f"Workflow test {uuid4().hex}",),
        ).fetchone()[0]
        loan_id = conn.execute(
            """
                INSERT INTO loans (
                    client_id, principal, rate_bp,
                    term_months, issued_on, payment_day
                )
                VALUES (%s, 500000000, 1200, 240, %s, 1)
                RETURNING id
                """,
            (client_id, date(date.today().year - 1, 1, 1)),
        ).fetchone()[0]
    try:
        yield loan_id
    finally:
        with db.connection() as conn, conn.transaction():
            conn.execute("DELETE FROM jobs WHERE loan_id = %s", (loan_id,))
            conn.execute("DELETE FROM loans WHERE id = %s", (loan_id,))
            conn.execute("DELETE FROM clients WHERE id = %s", (client_id,))


@pytest.fixture
def cleanup_documents():
    ids = []
    yield ids
    if ids:
        with db.connection() as conn:
            conn.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids,))


@pytest.fixture(autouse=True)
def no_real_embedding_model(monkeypatch):
    def blocked():
        raise AssertionError("Загрузка настоящей модели в тестах запрещена")

    monkeypatch.setattr(embeddings, "_model", None)
    monkeypatch.setattr(embeddings, "_load_model", blocked)

