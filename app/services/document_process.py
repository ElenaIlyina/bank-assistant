from uuid import uuid4

from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core import db
from app.core.config import settings
from app.repositories import documents
from app.temporal.client import get_client
from app.temporal.document_workflow import DocumentWorkflow


def get_document(document_id: str) -> dict | None:
    with db.connection() as conn:
        return documents.get(conn, document_id)


async def upload_document(filename: str, content: bytes) -> dict:
    if not content:
        raise ValueError("Файл пустой")

    with db.connection() as conn:
        document_id, _ = documents.create(
            conn, uuid4().hex, filename, content
        )
        document = documents.get(conn, document_id)

    if document is None:
        raise RuntimeError("Сохранённый документ не найден")

    if document["status"] == "uploaded":
        client = await get_client()
        try:
            await client.start_workflow(
                DocumentWorkflow.run,
                args=[document_id],
                id=f"document:{document_id}",
                task_queue=settings.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            pass

    return document

