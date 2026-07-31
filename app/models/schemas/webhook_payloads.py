from pydantic import BaseModel
from typing import Any

class WebhookPayload(BaseModel):
    provider: str
    payload: dict[str, Any]
