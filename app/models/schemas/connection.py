from pydantic import BaseModel

class ConnectionResponse(BaseModel):
    id: str
    provider: str
    status: str
