"""Natural-language command HTTP routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/commands", tags=["Commands"])

class CommandRequest(BaseModel):
    text: str

class CommandResponse(BaseModel):
    success: bool
    message: str

@router.post("", response_model=CommandResponse)
async def submit_command(request: CommandRequest):
    raise HTTPException(status_code=501, detail="Command execution is not implemented.")
