from fastapi import APIRouter
from app.models.schemas.connection import ConnectionResponse
from typing import List

router = APIRouter(prefix="/v1/connections", tags=["Connections"])

@router.get("", response_model=List[ConnectionResponse])
async def list_connections():
    return [
        ConnectionResponse(id="conn-1", provider="gmail", status="connected")
    ]
