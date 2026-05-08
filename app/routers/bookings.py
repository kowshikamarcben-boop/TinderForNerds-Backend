"""
/api/v1/bookings — create, list, state transitions.
"""
from uuid import UUID

from fastapi import APIRouter

from app.deps import Redis, UserDB, UserID
from app.models.bookings import BookingIn, BookingOut, BookingStatusUpdate
from app.services import bookings as booking_svc
from app.services.rate_limit import check_rate_limit

router = APIRouter(tags=["bookings"])


@router.get("/bookings", response_model=list[BookingOut])
async def list_bookings(uid: UserID, db: UserDB) -> list[BookingOut]:
    return await booking_svc.list_bookings(uid, db)


@router.post("/bookings", response_model=BookingOut, status_code=201)
async def create_booking(uid: UserID, db: UserDB, redis: Redis, body: BookingIn) -> BookingOut:
    if redis is not None:
        await check_rate_limit(redis, f"booking:{uid}", limit=20, window=86400)
    return await booking_svc.create_booking(uid, body, db)


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: UUID, uid: UserID, db: UserDB) -> BookingOut:
    return await booking_svc.get_booking(booking_id, uid, db)


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
async def update_booking_status(
    booking_id: UUID, uid: UserID, db: UserDB, body: BookingStatusUpdate
) -> BookingOut:
    return await booking_svc.update_status(booking_id, uid, body, db)
