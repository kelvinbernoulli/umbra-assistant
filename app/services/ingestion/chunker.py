from app.models.domain.document import Document
from typing import List


def chunk_document(document: Document, chunk_size: int = 500) -> List[Document]:
    text = document.content
    return [
        Document(
            id=f"{document.id}-{i}",
            content=text[i:i+chunk_size],
            metadata=document.metadata
        )
        for i in range(0, len(text), chunk_size)
    ]
