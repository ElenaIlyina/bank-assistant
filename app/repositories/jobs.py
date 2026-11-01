from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def create(
    conn: psycopg.Connection,
    job_id: str,
    kind: str,
    loan_id: int,
    payload: dict,
    idempotency_key: str | None,
) -> tuple[str, bool]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, kind, loan_id, status, payload, idempotency_key)
            VALUES (%s, %s, %s, 'pending', %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            (job_id, kind, loan_id, Jsonb(payload), idempotency_key),
        )
        row = cur.fetchone()
        if row is not None:
            return row[0], True
        cur.execute(
            "SELECT id FROM jobs WHERE idempotency_key = %s",
            (idempotency_key,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Не удалось получить существующую задачу")
        return row[0], False


def get(conn: psycopg.Connection, job_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, kind, loan_id, status, payload, result, created_at, updated_at
            FROM jobs
            WHERE id = %s
            """,
            (job_id,),
        )
        return cur.fetchone()


def set_status(
    conn: psycopg.Connection,
    job_id: str,
    status: str,
    result: dict | None = None,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status = %s, result = COALESCE(%s, result), updated_at = now()
        WHERE id = %s
        """,
        (status, Jsonb(result) if result is not None else None, job_id),
    )


def last_approved_at(
    conn: psycopg.Connection,
    loan_id: int,
    kind: str,
) -> datetime | None:
    row = conn.execute(
        """
        SELECT max(updated_at)
        FROM jobs
        WHERE loan_id = %s AND kind = %s AND status = 'approved'
        """,
        (loan_id, kind),
    ).fetchone()
    return row[0]
