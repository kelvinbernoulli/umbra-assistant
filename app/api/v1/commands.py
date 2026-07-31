from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/commands", tags=["Commands"])

class CommandRequest(BaseModel):
    text: str

class CommandResponse(BaseModel):
    success: bool
    message: str

@router.post("", response_model=CommandResponse)
async def submit_command(request: CommandRequest):
    return CommandResponse(success=True, message=f"Command received: {request.text}")
