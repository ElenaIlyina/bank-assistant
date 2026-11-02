from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.core import db
from app.parsers.blocks import ParseError
from app.repositories import documents
from app.services import document_ingestion


@activity.defn
def parse_document(document_id: str) -> int:
    try:
        return document_ingestion.parse_document(document_id)
    except ParseError as exc:
        raise ApplicationError(
            str(exc),
            type="DocumentRejected",
            non_retryable=True,
        ) from exc


@activity.defn
def embed_document(document_id: str) -> int:
    return document_ingestion.embed_document(document_id)


@activity.defn
def set_document_status(
    document_id: str,
    status: str,
    error: str | None,
) -> None:
    with db.connection() as conn:
        documents.set_status(conn, document_id, status, error)

