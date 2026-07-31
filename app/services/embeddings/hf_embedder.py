from typing import List
from app.core.config import settings


class HuggingFaceEmbedder:
    def __init__(self):
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 384 for _ in texts]
