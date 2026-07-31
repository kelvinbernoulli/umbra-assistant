from pydantic import BaseModel

class SearchResponse(BaseModel):
    id: str
    snippet: str
