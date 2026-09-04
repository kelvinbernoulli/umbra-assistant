"""Natural-language command HTTP routes."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/commands", tags=["Commands"])

class CommandRequest(BaseModel):
    text: str

class CommandResponse(BaseModel):
    success: bool
    message: str

@router.post("", response_model=CommandResponse)
async def submit_command(request: CommandRequest):
    return CommandResponse(success=True, message=f"Command received: {request.text}")
