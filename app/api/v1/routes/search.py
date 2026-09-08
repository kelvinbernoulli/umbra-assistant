"""Workspace-scoped transactional search routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_id
from app.db.models import SourceItem
from app.db.session import get_db
from app.models.schemas.search import SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("", response_model=list[SearchResponse])
async def semantic_search(
    request: SearchRequest,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
) -> list[SearchResponse]:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    if request.limit < 1 or request.limit > 100:
        raise HTTPException(status_code=400, detail="Search limit must be between 1 and 100")

    statement = select(SourceItem).where(
        SourceItem.workspace_id == workspace_id,
        SourceItem.text.ilike(f"%{query}%"),
    )
    if request.source:
        statement = statement.where(SourceItem.source == request.source.strip().lower())
    if request.document_type:
        statement = statement.where(SourceItem.document_type == request.document_type.strip().lower())

    items = db.scalars(
        statement.order_by(SourceItem.created_at.desc()).limit(request.limit)
    ).all()
    return [SearchResponse(id=item.id, snippet=item.text[:280]) for item in items]
