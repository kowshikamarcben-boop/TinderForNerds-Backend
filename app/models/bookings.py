"""Booking + availability models — column names match schema.sql (host_id, guest_id)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.types import BookingKind, BookingStatus, PaymentStatus


class BookingIn(BaseModel):
    host_id: UUID
    starts_at: datetime
    ends_at: datetime
    kind: BookingKind = BookingKind.coffee
    notes: str | None = Field(None, max_length=5000)
    is_paid: bool = False
    price_cents: int | None = None
    currency: str = "INR"

    @model_validator(mode="after")
    def ends_after_starts(self) -> "BookingIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self

    @model_validator(mode="after")
    def currency_whitelist(self) -> "BookingIn":
        _ALLOWED = {"INR", "USD", "EUR", "GBP", "CAD", "AUD", "SGD", "AED"}
        if self.currency not in _ALLOWED:
            raise ValueError(f"currency must be one of {sorted(_ALLOWED)}")
        return self


class BookingStatusUpdate(BaseModel):
    status: BookingStatus
    notes: str | None = None


class BookingOut(BaseModel):
    id: UUID
    host_id: UUID
    guest_id: UUID
    kind: BookingKind
    status: BookingStatus
    starts_at: datetime
    ends_at: datetime
    meeting_url: str | None = None
    notes: str | None = None
    is_paid: bool = False
    price_cents: int | None = None
    currency: str = "INR"
    payment_status: PaymentStatus | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AvailabilitySlotIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    is_recurring: bool = False
    rrule: str | None = None
    is_available: bool = True


class AvailabilitySlotOut(AvailabilitySlotIn):
    id: UUID
    profile_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
