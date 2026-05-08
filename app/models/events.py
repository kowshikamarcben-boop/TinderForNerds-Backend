"""Event + attendee models — matches schema.sql exactly."""
from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from app.db.types import (
    EventApprovalStatus,
    EventAttendeeStatus,
    EventHostType,
    EventKind,
    EventMode,
)

_ALLOWED_CURRENCIES = {"INR", "USD", "EUR", "GBP", "CAD", "AUD", "SGD", "AED"}


class EventIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=160)
    description: str | None = Field(None, max_length=5000)
    host_type: EventHostType = EventHostType.user
    kind: EventKind = EventKind.meetup
    mode: EventMode = EventMode.offline
    venue_name: str | None = None
    venue_address: str | None = None
    city: str | None = None
    meeting_url: AnyHttpUrl | None = None
    starts_at: datetime
    ends_at: datetime
    capacity: int | None = Field(None, gt=0)
    cover_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_paid: bool = False
    price_cents: int | None = None
    currency: str = "INR"

    @model_validator(mode="after")
    def ends_after_starts(self) -> "EventIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self

    @model_validator(mode="after")
    def currency_whitelist(self) -> "EventIn":
        if self.currency not in _ALLOWED_CURRENCIES:
            raise ValueError(f"currency must be one of {sorted(_ALLOWED_CURRENCIES)}")
        return self


class EventUpdate(EventIn):
    pass


class EventOut(EventIn):
    id: UUID
    host_profile_id: UUID | None = None
    approval_status: EventApprovalStatus = EventApprovalStatus.draft
    attendee_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventReviewIn(BaseModel):
    approve: bool
    review_notes: str | None = None


class AttendeeOut(BaseModel):
    event_id: UUID
    profile_id: UUID
    status: EventAttendeeStatus
    created_at: datetime

    model_config = {"from_attributes": True}
