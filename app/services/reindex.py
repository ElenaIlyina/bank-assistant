from app.core import db
from app.core.config import settings
from app.repositories import chunks
from app.services.document_ingestion import embed_document


def reindex_documents() -> int:
    with db.connection() as conn:
        document_ids = chunks.documents_to_reindex(
            conn, settings.embedding_model
        )

    total = 0
    for document_id in document_ids:
        total += embed_document(document_id)
    return total


if __name__ == "__main__":
    print(f"Обновлено векторов: {reindex_documents()}")

