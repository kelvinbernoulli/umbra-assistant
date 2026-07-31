from fastapi import APIRouter
from app.models.schemas.brief import BriefResponse

router = APIRouter(prefix="/v1/brief", tags=["Brief"])

@router.get("/today", response_model=BriefResponse)
async def get_today_brief():
    return BriefResponse(title="Umbra Morning Brief", summary="This is a placeholder brief.")
