from pydantic import BaseModel
from datetime import datetime

class TimelineEventResponse(BaseModel):
    id: str
    source: str
    type: str
    timestamp: datetime
    title: str
    detail: str
