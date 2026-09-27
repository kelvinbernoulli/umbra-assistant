from typing import Any, Literal

from pydantic import BaseModel, Field


class BriefResponse(BaseModel):
    title: str
    summary: str
    summary_source: Literal["factual", "ai"] = "factual"
    summary_notice: str | None = None
    calendar_events: list[dict[str, Any]] = Field(default_factory=list)
    calendar_count: int | None = None
    calendar_has_more: bool = False
    calendar_notice: str | None = None
