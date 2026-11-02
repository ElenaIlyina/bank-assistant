from app.core import db
from app.core.config import settings
from app.llm import embeddings
from app.parsers.chunker import PROGRAM_CODE
from app.repositories import search as search_repo


def search(
    query: str,
    mode: str = "hybrid",
    filename: str | None = None,
    limit: int = 10,
) -> list[dict]:
    query = query.strip()
    if not query:
        raise ValueError("Пустой поисковый запрос")

    codes = sorted(set(PROGRAM_CODE.findall(query.upper())))
    vector = None if mode == "fts" else embeddings.embed_query(query)

    with db.connection() as conn:
        return search_repo.search(
            conn,
            query=query,
            mode=mode,
            vector=vector,
            model=settings.embedding_model,
            threshold=settings.search_similarity_threshold,
            codes=codes,
            filename=filename,
            limit=limit,
        )

