from hashlib import sha256

import psycopg
from psycopg.rows import dict_row


def create(
    conn: psycopg.Connection,
    document_id: str,
    filename: str,
    content: bytes,
) -> tuple[str, bool]:
    digest = sha256(content).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, filename, sha256, content)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (sha256) DO NOTHING
            RETURNING id
            """,
            (document_id, filename, digest, content),
        )
        row = cur.fetchone()
        if row is not None:
            return row[0], True
        cur.execute(
            "SELECT id FROM documents WHERE sha256 = %s",
            (digest,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Не удалось получить существующий документ")
        return row[0], False


def get(conn: psycopg.Connection, document_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, filename, sha256, status, error, created_at, updated_at
            FROM documents
            WHERE id = %s
            """,
            (document_id,),
        )
        return cur.fetchone()


def get_content(conn: psycopg.Connection, document_id: str) -> bytes | None:
    row = conn.execute(
        "SELECT content FROM documents WHERE id = %s",
        (document_id,),
    ).fetchone()
    return row[0] if row is not None else None


def set_status(
    conn: psycopg.Connection,
    document_id: str,
    status: str,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE documents
        SET status = %s, error = %s, updated_at = now()
        WHERE id = %s
        """,
        (status, error, document_id),
    )
