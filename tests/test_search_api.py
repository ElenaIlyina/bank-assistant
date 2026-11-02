import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import search as search_service

client = TestClient(app)


@pytest.fixture
def search_calls(monkeypatch):
    embedded = []
    requested = []

    def embed(query):
        embedded.append(query)
        return [1.0] + [0.0] * 767

    def search(conn, **kwargs):
        requested.append(kwargs)
        return []

    monkeypatch.setattr(search_service.embeddings, "embed_query", embed)
    monkeypatch.setattr(search_service.search_repo, "search", search)
    return embedded, requested


def test_fts_does_not_use_embedder(search_calls):
    embedded, requested = search_calls

    result = search_service.search(
        "  ставка по ip-family-6 и IP-FAMILY-6  ",
        mode="fts",
    )

    assert result == []
    assert embedded == []
    assert requested[0]["vector"] is None
    assert requested[0]["codes"] == ["IP-FAMILY-6"]
    assert requested[0]["query"] == "ставка по ip-family-6 и IP-FAMILY-6"


@pytest.mark.parametrize("mode", ["vector", "hybrid"])
def test_query_embedding_and_settings(mode, search_calls, monkeypatch):
    embedded, requested = search_calls
    monkeypatch.setattr(settings, "search_similarity_threshold", 0.73)

    search_service.search(
        "досрочное погашение",
        mode=mode,
        filename="rules.docx",
        limit=3,
    )

    assert embedded == ["досрочное погашение"]
    assert requested[0]["vector"] == [1.0] + [0.0] * 767
    assert requested[0]["mode"] == mode
    assert requested[0]["threshold"] == 0.73
    assert requested[0]["model"] == settings.embedding_model
    assert requested[0]["filename"] == "rules.docx"
    assert requested[0]["limit"] == 3


def test_search_endpoint(monkeypatch):
    calls = []
    hit = {
        "id": 123,
        "document_id": "test-document",
        "filename": "tariffs.xlsx",
        "ordinal": 2,
        "text": "IP-FAMILY-6: ставка 6 процентов",
        "kind": "row",
        "section": "Программы",
        "page": None,
        "sheet": "Программы",
        "row_number": 3,
        "program_code": "IP-FAMILY-6",
        "code_match": True,
        "score": 1 / 61,
        "similarity": None,
    }

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [hit]

    monkeypatch.setattr(search_service, "search", search)

    response = client.get(
        "/search",
        params={
            "q": "ставка по IP-FAMILY-6",
            "mode": "fts",
            "filename": "tariffs.xlsx",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == [hit]
    assert calls == [
        (
            "ставка по IP-FAMILY-6",
            {"mode": "fts", "filename": "tariffs.xlsx", "limit": 3},
        )
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"q": ""},
        {"q": "   "},
        {"q": "ставка", "mode": "wrong"},
        {"q": "ставка", "limit": 0},
        {"q": "ставка", "limit": 101},
    ],
)
def test_invalid_search_parameters(params, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Поиск не должен запускаться")

    monkeypatch.setattr(search_service, "search", blocked)
    response = client.get("/search", params=params)
    assert response.status_code == 422

