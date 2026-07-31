from dataclasses import dataclass
from typing import Any

@dataclass
class Document:
    id: str
    content: str
    metadata: dict[str, Any]
