from app.core import db
from app.core.config import settings
from app.llm import embeddings
from app.parsers.blocks import ParseError
from app.repositories import chunks as chunks_repo
from app.repositories import documents as documents_repo
from app.services.documents import parse


def parse_document(document_id: str) -> int:
    with db.connection() as conn:
        document = documents_repo.get(conn, document_id)
        if document is None:
            raise ValueError("Документ не найден")
        existing = chunks_repo.list_for_document(conn, document_id)
        if existing:
            return len(existing)
        content = documents_repo.get_content(conn, document_id)
    if content is None:
        raise ValueError("Исходный файл не найден")
    items = parse(document["filename"], content)
    if not items:
        raise ParseError("В документе нет текстовых фрагментов")
    with db.connection() as conn:
        return chunks_repo.save_parsed(conn, document_id, items)


def embed_document(document_id: str) -> int:
    model = settings.embedding_model
    with db.connection() as conn:
        if documents_repo.get(conn, document_id) is None:
            raise ValueError("Документ не найден")
        rows = chunks_repo.list_for_document(conn, document_id)
    pending = [
        row
        for row in rows
        if row["embedding"] is None or row["embedding_model"] != model
    ]
    if not pending:
        return 0
    vectors = embeddings.embed_documents(pending)
    values = [
        (row["id"], vector)
        for row, vector in zip(pending, vectors, strict=True)
    ]
    with db.connection() as conn:
        return chunks_repo.save_embeddings(conn, values, model)

