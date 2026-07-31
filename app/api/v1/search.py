from fastapi import APIRouter
from app.models.schemas.search import SearchResponse
from typing import List

router = APIRouter(prefix="/v1/search", tags=["Search"])

@router.post("", response_model=List[SearchResponse])
async def semantic_search(query: str):
    return [
        SearchResponse(id="result-1", snippet="Placeholder result for semantic search.")
    ]
