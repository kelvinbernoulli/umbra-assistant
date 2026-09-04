from datetime import datetime
from pydantic import BaseModel

class ConnectionResponse(BaseModel):
    id: str | None = None
    provider: str
    status: str
    connected_at: datetime | None = None
