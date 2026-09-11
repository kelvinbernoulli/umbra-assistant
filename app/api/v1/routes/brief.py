"""Morning brief HTTP routes."""

from fastapi import APIRouter, HTTPException
from app.models.schemas.brief import BriefResponse

router = APIRouter(prefix="/brief", tags=["Brief"])

@router.get("/today", response_model=BriefResponse)
async def get_today_brief():
    raise HTTPException(status_code=501, detail="Morning brief generation is not implemented.")
