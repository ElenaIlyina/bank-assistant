from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core import db
from app.main import app
from app.repositories import documents
from app.services import document_process

client = TestClient(app)


@pytest.fixture
def file_data(cleanup_documents):
    content = b"Test document " + uuid4().hex.encode()
    yield content
    with db.connection() as conn:
        row = conn.execute(
            "SELECT id FROM documents WHERE sha256 = %s",
            (sha256(content).hexdigest(),),
        ).fetchone()
    if row is not None:
        cleanup_documents.append(row[0])


@pytest.fixture
def temporal_client(monkeypatch):
    fake = SimpleNamespace(calls=[], workflows={})

    async def start_workflow(workflow, **kwargs):
        fake.calls.append(kwargs)
        workflow_id = kwargs["id"]
        if workflow_id in fake.workflows:
            raise WorkflowAlreadyStartedError(
                workflow_id, "DocumentWorkflow"
            )
        fake.workflows[workflow_id] = kwargs

    async def get_client():
        return fake

    fake.start_workflow = start_workflow
    monkeypatch.setattr(document_process, "get_client", get_client)
    return fake


def test_upload_and_get_document(file_data, temporal_client):
    response = client.post(
        "/documents",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 202
    document = response.json()
    assert document["filename"] == "test.pdf"
    assert document["status"] == "uploaded"
    assert document["error"] is None
    assert document["sha256"] == sha256(file_data).hexdigest()
    assert "content" not in document

    response = client.get(f"/documents/{document['id']}")
    assert response.status_code == 200
    assert response.json() == document

    call = temporal_client.calls[0]
    assert call["args"] == [document["id"]]
    assert call["id"] == f"document:{document['id']}"
    assert call["id_reuse_policy"] == WorkflowIDReusePolicy.REJECT_DUPLICATE


def test_same_file_returns_same_document(file_data, temporal_client):
    first = client.post(
        "/documents",
        files={"file": ("first.pdf", file_data, "application/pdf")},
    )
    second = client.post(
        "/documents",
        files={"file": ("renamed.pdf", file_data, "application/pdf")},
    )
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["filename"] == "first.pdf"
    assert len(temporal_client.workflows) == 1


def test_unknown_document():
    response = client.get(f"/documents/{uuid4().hex}")
    assert response.status_code == 404


def test_empty_file(temporal_client):
    response = client.post(
        "/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert temporal_client.calls == []


def test_retry_after_temporal_unavailable(
    file_data, temporal_client, monkeypatch
):
    async def unavailable():
        raise OSError("Temporal недоступен")

    original = document_process.get_client
    monkeypatch.setattr(document_process, "get_client", unavailable)

    response = client.post(
        "/documents",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 503

    with db.connection() as conn:
        row = conn.execute(
            "SELECT id, status FROM documents WHERE sha256 = %s",
            (sha256(file_data).hexdigest(),),
        ).fetchone()
    assert row is not None
    assert row[1] == "uploaded"
    document_id = row[0]

    monkeypatch.setattr(document_process, "get_client", original)
    response = client.post(
        "/documents",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 202
    assert response.json()["id"] == document_id
    assert len(temporal_client.workflows) == 1


def test_indexed_document_is_not_started_again(file_data, temporal_client):
    response = client.post(
        "/documents",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 202
    document_id = response.json()["id"]

    with db.connection() as conn:
        documents.set_status(conn, document_id, "indexed")

    response = client.post(
        "/documents",
        files={"file": ("test.pdf", file_data, "application/pdf")},
    )
    assert response.status_code == 202
    assert response.json()["id"] == document_id
    assert response.json()["status"] == "indexed"
    assert len(temporal_client.calls) == 1

