from fastapi import APIRouter, HTTPException, UploadFile
from temporalio.service import RPCError

from app.schemas.documents import Document
from app.services import document_process

router = APIRouter(tags=["documents"])


@router.post("/documents", status_code=202, response_model=Document)
async def upload_document(file: UploadFile):
    if not file.filename:
        raise HTTPException(400, "Не указано имя файла")

    content = await file.read()

    try:
        return await document_process.upload_document(
            file.filename, content
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (RPCError, OSError, RuntimeError) as exc:
        raise HTTPException(
            503,
            "Не удалось запустить обработку. Повторите загрузку того же файла",
        ) from exc


@router.get("/documents/{document_id}", response_model=Document)
def get_document(document_id: str):
    document = document_process.get_document(document_id)
    if document is None:
        raise HTTPException(404, "Документ не найден")
    return document

