from app.core.config import settings


class PineconeClient:
    def __init__(self):
        self.index_name = settings.PINECONE_INDEX_NAME

    def upsert(self, id: str, vector: list[float], metadata: dict) -> str:
        return id
