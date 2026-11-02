import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from temporalio.service import RPCError
from temporalio.worker import Worker

from app.core import db
from app.repositories import chunks, documents
from app.services import document_ingestion as ingestion
from app.temporal.client import get_client
from app.temporal.document_activities import (
    embed_document,
    parse_document,
    set_document_status,
)
from app.temporal.document_workflow import DocumentWorkflow

DATA = Path(__file__).resolve().parent.parent / "data"


def store_file(cleanup_documents, filename, content=None):
    if content is None:
        content = (DATA / filename).read_bytes()
    content += b"\n% test: " + uuid4().hex.encode() + b"\n"
    document_id = uuid4().hex
    cleanup_documents.append(document_id)
    with db.connection() as conn:
        _, created = documents.create(conn, document_id, filename, content)
    assert created is True
    return document_id


@pytest.fixture
async def document_worker():
    client = await get_client()
    queue = f"test-documents-{uuid4().hex}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        async with Worker(
            client,
            task_queue=queue,
            workflows=[DocumentWorkflow],
            activities=[parse_document, embed_document, set_document_status],
            activity_executor=pool,
            max_concurrent_activities=2,
        ):
            yield client, queue


@pytest.fixture
def fake_embeddings(monkeypatch):
    calls = []

    def encode(items):
        calls.append(len(items))
        return [[1.0] + [0.0] * 767 for _ in items]

    monkeypatch.setattr(ingestion.embeddings, "embed_documents", encode)
    return calls


async def run_document(worker, document_id):
    client, queue = worker
    workflow_id = f"document:{document_id}"
    handle = client.get_workflow_handle(workflow_id)
    try:
        await client.start_workflow(
            DocumentWorkflow.run,
            args=[document_id],
            id=workflow_id,
            task_queue=queue,
        )
        status = await asyncio.wait_for(handle.result(), timeout=45)
        history = await handle.fetch_history()
        states = []
        for event in history.events:
            attrs = event.activity_task_scheduled_event_attributes
            if attrs.activity_type.name == "set_document_status":
                values = await client.data_converter.decode(attrs.input.payloads)
                states.append(values[1])
        return status, states
    finally:
        try:
            await handle.terminate(reason="test cleanup")
        except RPCError:
            pass


@pytest.mark.parametrize(
    "filename",
    [
        "credit_agreement.pdf",
        "payment_date_reglament.pdf",
        "early_repayment_rules.docx",
        "tariffs.xlsx",
        "client_application.docx",
    ],
)
async def test_text_files_are_indexed(
    cleanup_documents, document_worker, fake_embeddings, filename
):
    document_id = store_file(cleanup_documents, filename)
    status, states = await run_document(document_worker, document_id)
    with db.connection() as conn:
        document = documents.get(conn, document_id)
        rows = chunks.list_for_document(conn, document_id)
    assert status == "indexed"
    assert states == ["parsing", "embedding", "indexed"]
    assert document["status"] == "indexed"
    assert document["error"] is None
    assert rows
    assert all(row["embedding"] is not None for row in rows)
    assert all(
        row["embedding_model"] == ingestion.settings.embedding_model
        for row in rows
    )
    assert len(fake_embeddings) == 1


@pytest.mark.parametrize(
    "filename,content,reason",
    [
        ("income_statement_scan.pdf", None, "текстового слоя"),
        ("unsupported.txt", b"Unsupported", "не поддерживается"),
    ],
)
async def test_permanent_parse_error_is_rejected(
    cleanup_documents, document_worker, fake_embeddings,
    filename, content, reason,
):
    document_id = store_file(cleanup_documents, filename, content)
    status, states = await run_document(document_worker, document_id)
    with db.connection() as conn:
        document = documents.get(conn, document_id)
    assert status == "rejected"
    assert states == ["parsing", "rejected"]
    assert document["status"] == "rejected"
    assert reason in document["error"]
    assert fake_embeddings == []


async def test_embedding_failure_after_retries(
    monkeypatch, cleanup_documents, document_worker
):
    calls = []

    def broken(items):
        calls.append(1)
        raise RuntimeError("Тестовая ошибка эмбеддера")

    monkeypatch.setattr(ingestion.embeddings, "embed_documents", broken)
    document_id = store_file(cleanup_documents, "credit_agreement.pdf")
    status, states = await run_document(document_worker, document_id)
    with db.connection() as conn:
        document = documents.get(conn, document_id)
    assert status == "failed"
    assert states == ["parsing", "embedding", "failed"]
    assert document["status"] == "failed"
    assert "Тестовая ошибка эмбеддера" in document["error"]
    assert len(calls) == 3

