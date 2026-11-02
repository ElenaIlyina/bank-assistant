from uuid import uuid4

import pytest

from app.core import db
from app.core.config import settings
from app.parsers.chunker import Chunk
from app.repositories import chunks, documents
from app.repositories import search as search_repo


def vector(x=1.0, y=0.0):
    return [x, y] + [0.0] * 766


@pytest.fixture
def search_data(cleanup_documents):
    token = uuid4().hex
    filename = f"search-{token}.xlsx"
    other_filename = f"other-{token}.xlsx"

    texts = [
        "Программа IP-FAMILY-6: ставка 6 процентов.",
        "Условия ипотеки и ставка по кредиту.",
        "Правила досрочного погашения кредита.",
        "Досрочное погашение без заявления.",
        "Старая служебная запись.",
        "Новая служебная запись.",
    ]
    items = [
        Chunk(
            ordinal=i,
            text=text,
            kind="row",
            section="Тарифы",
            page=None,
            sheet="Тарифы",
            row=i + 1,
            program_code="IP-FAMILY-6" if i == 0 else None,
        )
        for i, text in enumerate(texts)
    ]

    document_id = uuid4().hex
    other_id = uuid4().hex
    cleanup_documents.extend([document_id, other_id])

    with db.connection() as conn:
        for doc_id, name in [
            (document_id, filename),
            (other_id, other_filename),
        ]:
            documents.create(conn, doc_id, name, uuid4().bytes)
            documents.set_status(conn, doc_id, "indexed")

        chunks.replace(conn, document_id, items)
        rows = chunks.list_for_document(conn, document_id)

        values = [
            vector(0.0, 1.0),
            vector(),
            vector(0.8, 0.6),
            vector(0.6, 0.8),
        ]
        chunks.save_embeddings(
            conn,
            [(row["id"], value) for row, value in zip(rows[:4], values, strict=True)],
            settings.embedding_model,
        )
        chunks.save_embeddings(
            conn,
            [(rows[4]["id"], vector())],
            "old-model",
        )

        chunks.replace(conn, other_id, items[:1])
        other_rows = chunks.list_for_document(conn, other_id)
        chunks.save_embeddings(
            conn,
            [(other_rows[0]["id"], vector())],
            settings.embedding_model,
        )

    return {
        "id": document_id,
        "filename": filename,
        "other_filename": other_filename,
    }


@pytest.fixture
def run_search(search_data):
    def run(
        mode="hybrid",
        query="досрочное погашение",
        threshold=0.0,
        codes=(),
        filename=None,
        limit=10,
    ):
        with db.connection() as conn:
            return search_repo.search(
                conn,
                query=query,
                mode=mode,
                vector=None if mode == "fts" else vector(),
                model=settings.embedding_model,
                threshold=threshold,
                codes=list(codes),
                filename=filename or search_data["filename"],
                limit=limit,
            )

    return run


def test_vector_threshold(run_search):
    rows = run_search(mode="vector", threshold=0.7)
    assert [row["ordinal"] for row in rows] == [1, 2]
    assert rows[1]["similarity"] == pytest.approx(0.8)


def test_fts_ignores_vector_threshold(run_search):
    rows = run_search(mode="fts", threshold=1.0)
    assert {row["ordinal"] for row in rows} == {2, 3}
    assert all(row["similarity"] is None for row in rows)


def test_hybrid_finds_code_with_high_threshold(run_search):
    rows = run_search(
        query="ставка по IP-FAMILY-6",
        threshold=1.0,
        codes=["IP-FAMILY-6"],
    )
    assert rows[0]["program_code"] == "IP-FAMILY-6"
    assert rows[0]["code_match"] is True
    assert rows[0]["similarity"] is None
    assert rows[0]["sheet"] == "Тарифы"
    assert rows[0]["row_number"] == 1


def test_exact_code_is_first(run_search):
    rows = run_search(
        query="ставка по IP-FAMILY-6",
        codes=["IP-FAMILY-6"],
    )
    assert rows[0]["ordinal"] == 0


def test_rrf_combines_both_branches(run_search):
    vector_rows = run_search(mode="vector")
    fts_rows = run_search(mode="fts")
    hybrid_rows = run_search()

    assert hybrid_rows[0]["ordinal"] in (2, 3)

    for row in hybrid_rows:
        expected = sum(
            1 / (60 + position)
            for branch in [vector_rows, fts_rows]
            for position, item in enumerate(branch, 1)
            if item["id"] == row["id"]
        )
        assert row["score"] == pytest.approx(expected)


def test_fts_finds_chunks_without_current_vectors(run_search):
    rows = run_search(mode="fts", query="служебная запись")
    assert {row["ordinal"] for row in rows} == {4, 5}


def test_filename_filter(run_search, search_data):
    rows = run_search(
        mode="fts",
        query="IP-FAMILY-6",
        codes=["IP-FAMILY-6"],
        filename=search_data["other_filename"],
    )
    assert len(rows) == 1
    assert rows[0]["filename"] == search_data["other_filename"]

    assert run_search(filename=f"missing-{uuid4().hex}") == []


def test_unindexed_document_is_hidden(run_search, search_data):
    with db.connection() as conn:
        documents.set_status(conn, search_data["id"], "embedding")

    assert run_search(mode="fts") == []


def test_result_limit(run_search):
    assert len(run_search(mode="vector", limit=1)) == 1

