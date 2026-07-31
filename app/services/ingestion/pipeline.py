from app.services.ingestion.normalizer import normalize_payload
from app.services.ingestion.chunker import chunk_document
from app.services.embeddings.hf_embedder import HuggingFaceEmbedder
from app.services.vectorstore.pinecone_client import PineconeClient
from app.models.domain.document import Document
from typing import List


def ingest_payload(payload: dict) -> List[str]:
    document = normalize_payload(payload)
    chunks = chunk_document(document)
    embedder = HuggingFaceEmbedder()
    vectors = embedder.embed([chunk.content for chunk in chunks])
    client = PineconeClient()
    ids = [client.upsert(chunk.id, vector, chunk.metadata) for chunk, vector in zip(chunks, vectors)]
    return ids
