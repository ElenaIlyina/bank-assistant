import json

from psycopg.rows import dict_row


def search(
    conn,
    query: str,
    mode: str,
    vector: list[float] | None,
    model: str,
    threshold: float,
    codes: list[str],
    filename: str | None = None,
    limit: int = 10,
) -> list[dict]:
    params = {
        "query": query,
        "mode": mode,
        "vector": json.dumps(vector, allow_nan=False) if vector is not None else None,
        "model": model,
        "threshold": threshold,
        "codes": codes,
        "filename": filename,
        "limit": limit,
        "pool": max(50, limit * 5),
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH base AS (
                SELECT c.*, d.filename,
                       COALESCE(c.program_code = ANY(%(codes)s::text[]), false)
                           AS code_match
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.status = 'indexed'
                  AND (%(filename)s::text IS NULL OR d.filename = %(filename)s)
            ), vector_candidates AS (
                SELECT id, 1 - (embedding <=> %(vector)s::vector) AS similarity
                FROM base
                WHERE %(mode)s IN ('vector', 'hybrid')
                  AND embedding IS NOT NULL
                  AND embedding_model = %(model)s
                  AND 1 - (embedding <=> %(vector)s::vector) >= %(threshold)s
                ORDER BY similarity DESC, id
                LIMIT %(pool)s
            ), vector_ranked AS (
                SELECT id, similarity,
                       row_number() OVER (ORDER BY similarity DESC, id) AS rank
                FROM vector_candidates
            ), fts_candidates AS (
                SELECT id, code_match,
                       ts_rank_cd(
                           search_vector,
                           websearch_to_tsquery('russian', %(query)s)
                       ) AS relevance
                FROM base
                WHERE %(mode)s IN ('fts', 'hybrid')
                  AND (
                      search_vector @@ websearch_to_tsquery('russian', %(query)s)
                      OR code_match
                  )
                ORDER BY code_match DESC, relevance DESC, id
                LIMIT %(pool)s
            ), fts_ranked AS (
                SELECT id,
                       row_number() OVER (
                           ORDER BY code_match DESC, relevance DESC, id
                       ) AS rank
                FROM fts_candidates
            ), ranks AS (
                SELECT id, 1.0 / (60 + rank) AS score, similarity
                FROM vector_ranked
                UNION ALL
                SELECT id, 1.0 / (60 + rank), NULL::double precision
                FROM fts_ranked
            ), fused AS (
                SELECT id, sum(score)::double precision AS score,
                       max(similarity) AS similarity
                FROM ranks
                GROUP BY id
            )
            SELECT b.id, b.document_id, b.filename, b.ordinal,
                   b.text, b.kind, b.section, b.page, b.sheet,
                   b.row_number, b.program_code, b.code_match,
                   f.score, f.similarity
            FROM fused f
            JOIN base b ON b.id = f.id
            ORDER BY b.code_match DESC, f.score DESC, b.id
            LIMIT %(limit)s
            """,
            params,
        )
        return cur.fetchall()

