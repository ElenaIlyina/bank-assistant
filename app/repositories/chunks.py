import json

import psycopg
from psycopg.rows import dict_row

from app.parsers.chunker import Chunk


def replace(
    conn: psycopg.Connection,
    document_id: str,
    items: list[Chunk],
) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM documents WHERE id = %s FOR UPDATE",
            (document_id,),
        )
        if cur.fetchone() is None:
            raise ValueError("Документ не найден")
        cur.execute(
            "DELETE FROM chunks WHERE document_id = %s",
            (document_id,),
        )
        cur.executemany(
            """
            INSERT INTO chunks (
                document_id, ordinal, text, kind, section,
                page, sheet, row_number, program_code
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    document_id, item.ordinal, item.text, item.kind,
                    item.section, item.page, item.sheet, item.row,
                    item.program_code,
                )
                for item in items
            ],
        )
    return len(items)


def list_for_document(
    conn: psycopg.Connection,
    document_id: str,
) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, document_id, ordinal, text, kind, section,
                   page, sheet, row_number, program_code,
                   embedding::text AS embedding, embedding_model
            FROM chunks
            WHERE document_id = %s
            ORDER BY ordinal
            """,
            (document_id,),
        )
        rows = cur.fetchall()
    for row in rows:
        if row["embedding"] is not None:
            row["embedding"] = json.loads(row["embedding"])
    return rows


def save_embeddings(
    conn: psycopg.Connection,
    values: list[tuple[int, list[float]]],
    model: str,
) -> int:
    if not values:
        return 0
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE chunks
            SET embedding = %s::vector, embedding_model = %s
            WHERE id = %s
            """,
            [
                (json.dumps(vector, allow_nan=False), model, chunk_id)
                for chunk_id, vector in values
            ],
        )
        if cur.rowcount != len(values):
            raise ValueError("Часть чанков не найдена")
        return cur.rowcount


def save_parsed(
    conn: psycopg.Connection,
    document_id: str,
    items: list[Chunk],
) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM documents WHERE id = %s FOR UPDATE",
            (document_id,),
        )
        if cur.fetchone() is None:
            raise ValueError("Документ не найден")
        cur.execute(
            "SELECT count(*) FROM chunks WHERE document_id = %s",
            (document_id,),
        )
        count = cur.fetchone()[0]
        if count:
            return count
        return replace(conn, document_id, items)


def documents_to_reindex(conn, model: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT document_id
        FROM chunks
        WHERE embedding IS NULL
           OR embedding_model IS DISTINCT FROM %s
        ORDER BY document_id
        """,
        (model,),
    ).fetchall()
    return [row[0] for row in rows]

