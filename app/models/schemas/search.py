from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    source: str | None = None
    document_type: str | None = None
    limit: int = 20


class SearchResponse(BaseModel):
    id: str
    snippet: str
