import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.llm import embeddings


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        values = [[1.0] + [0.0] * 767 for _ in texts]
        return SimpleNamespace(tolist=lambda: values)


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(embeddings, "_load_model", lambda: model)
    return model


def test_query_prefix(fake_model):
    result = embeddings.embed_query("Когда платёж?")
    texts, options = fake_model.calls[0]
    assert texts == ["task: search result | query: Когда платёж?"]
    assert options["prompt"] == ""
    assert options["normalize_embeddings"] is True
    assert len(result) == 768


def test_document_prefixes_and_batch(monkeypatch, fake_model):
    monkeypatch.setattr(embeddings.settings, "embedding_batch_size", 4)
    result = embeddings.embed_documents([
        {"section": "Правила", "text": "Первый фрагмент"},
        {"text": "Второй фрагмент"},
    ])
    assert len(fake_model.calls) == 1
    texts, options = fake_model.calls[0]
    assert texts == [
        "title: Правила | text: Первый фрагмент",
        "title: none | text: Второй фрагмент",
    ]
    assert options["batch_size"] == 4
    assert len(result) == 2


def test_empty_documents_do_not_load_model():
    assert embeddings.embed_documents([]) == []


@pytest.mark.parametrize("values", [[], [[1.0]]])
def test_wrong_output_is_rejected(monkeypatch, fake_model, values):
    monkeypatch.setattr(
        fake_model,
        "encode",
        lambda texts, **kwargs: SimpleNamespace(tolist=lambda: values),
    )
    with pytest.raises(ValueError, match="вектор"):
        embeddings.embed_query("Вопрос")


def test_nonfinite_vector_is_rejected(monkeypatch, fake_model):
    values = [[float("nan")] + [0.0] * 767]
    monkeypatch.setattr(
        fake_model,
        "encode",
        lambda texts, **kwargs: SimpleNamespace(tolist=lambda: values),
    )
    with pytest.raises(ValueError, match="NaN"):
        embeddings.embed_query("Вопрос")


def test_concurrent_requests_load_model_once(monkeypatch, fake_model):
    loads = []
    barrier = Barrier(2)

    def load():
        loads.append(1)
        time.sleep(0.02)
        return fake_model

    def run(_):
        barrier.wait(timeout=5)
        return embeddings.embed_query("Вопрос")

    monkeypatch.setattr(embeddings, "_load_model", load)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert len(loads) == 1
    assert len(fake_model.calls) == 2
    assert all(len(result) == 768 for result in results)

