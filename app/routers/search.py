from typing import Literal

from fastapi import APIRouter, Query

from app.schemas.search import SearchHit
from app.services import search as search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=1, max_length=2000, pattern=r"\S"),
    mode: Literal["hybrid", "vector", "fts"] = "hybrid",
    filename: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
):
    return search_service.search(
        q,
        mode=mode,
        filename=filename,
        limit=limit,
    )

