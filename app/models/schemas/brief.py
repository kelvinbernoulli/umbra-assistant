from pydantic import BaseModel

class BriefResponse(BaseModel):
    title: str
    summary: str
