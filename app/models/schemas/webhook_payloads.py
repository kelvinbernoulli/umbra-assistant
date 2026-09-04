from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class WebhookPayload(BaseModel):
    provider: str
    payload: dict[str, Any]


class CalendarEventPayload(BaseModel):
    id: str
    summary: str | None = None
    description: str | None = None


class InboundEmail(BaseModel):
    """Canonical JSON contract accepted by the inbound email webhook."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    email_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("email_id", "id"),
    )
    from_address: str = Field(
        min_length=1,
        validation_alias=AliasChoices("from", "sender"),
        serialization_alias="from",
    )
    to: str = Field(min_length=1)
    subject: str = "(no subject)"
    text: str = Field(
        default="",
        validation_alias=AliasChoices("text", "body"),
        serialization_alias="text",
    )
    html: str = ""
    timestamp: int = Field(default=0, ge=0)
    cc: str = ""

    @field_validator("subject", mode="before")
    @classmethod
    def default_empty_subject(cls, value: object) -> object:
        return value or "(no subject)"

    @field_validator("text", "html", "cc", mode="before")
    @classmethod
    def default_optional_text(cls, value: object) -> object:
        return "" if value is None else value
