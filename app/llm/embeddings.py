import math
from threading import Lock

from app.core.config import settings

DIMENSIONS = 768
_model = None
_lock = Lock()


def _load_model():
    import torch
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        settings.embedding_model,
        device="cpu",
        model_kwargs={"dtype": torch.float32},
    )


def _encode(texts: list[str]) -> list[list[float]]:
    global _model
    if not texts:
        return []
    with _lock:
        if _model is None:
            _model = _load_model()
        vectors = _model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            prompt="",
        ).tolist()
    if len(vectors) != len(texts):
        raise ValueError("Количество векторов не совпадает с количеством текстов")
    if any(len(vector) != DIMENSIONS for vector in vectors):
        raise ValueError("Размерность вектора должна быть 768")
    vectors = [[float(value) for value in vector] for vector in vectors]
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("Вектор содержит NaN или бесконечность")
    return vectors


def embed_query(query: str) -> list[float]:
    return _encode([f"task: search result | query: {query}"])[0]


def embed_documents(items: list[dict]) -> list[list[float]]:
    texts = []
    for item in items:
        title = (item.get("section") or "").strip() or "none"
        texts.append(f"title: {title} | text: {item['text']}")
    return _encode(texts)

