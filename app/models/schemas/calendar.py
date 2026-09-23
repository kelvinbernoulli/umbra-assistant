"""Editable fields for timed and all-day Google Calendar events."""
from datetime import date as Date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class EventTime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: Date | None = None
    dateTime: AwareDatetime | None = None

    @model_validator(mode="after")
    def one_time_format(self):
        if (self.date is None) == (self.dateTime is None):
            raise ValueError("Provide either date or dateTime with a UTC offset")
        return self


class EventChanges(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str | None = Field(default=None, min_length=1, max_length=1024)
    description: str | None = Field(default=None, max_length=8192)
    location: str | None = Field(default=None, max_length=1024)
    start: EventTime | None = None
    end: EventTime | None = None

    @model_validator(mode="after")
    def valid_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one event field")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Event fields cannot be null; use an empty string to clear description or location")
        if (self.start is None) != (self.end is None):
            raise ValueError("Provide both start and end when changing event times")
        if self.start is not None and self.end is not None:
            if (self.start.date is None) != (self.end.date is None):
                raise ValueError("Start and end must use the same time format")
            start = self.start.date or self.start.dateTime
            end = self.end.date or self.end.dateTime
            if end <= start:
                raise ValueError("End must be after start; all-day end dates are exclusive")
        return self


class EventCreate(EventChanges):
    summary: str = Field(min_length=1, max_length=1024)
    start: EventTime
    end: EventTime
