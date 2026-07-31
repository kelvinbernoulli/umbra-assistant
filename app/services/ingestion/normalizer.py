from app.models.domain.document import Document


def normalize_payload(payload: dict) -> Document:
    return Document(
        id=payload.get("id", "unknown"),
        content=payload.get("text", ""),
        metadata={"source": payload.get("source", "unknown")}
    )
