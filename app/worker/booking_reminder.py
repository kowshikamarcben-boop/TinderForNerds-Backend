"""Worker job: send booking reminders at 1h and 15min before starts_at."""
from datetime import datetime, timezone, timedelta

import structlog

from app.db.client import get_admin_client
from app.services.notifications import send_notification_to

log = structlog.get_logger()


async def booking_reminder(ctx: dict, payload: dict) -> None:  # type: ignore[type-arg]
    booking_id = payload.get("booking_id")
    if not booking_id:
        log.warning("booking_reminder.missing_id")
        return
    log.info("booking_reminder.start", booking_id=booking_id)
    try:
        admin = get_admin_client()
        result = admin.table("bookings").select("*").eq("id", booking_id).execute()
        if not result.data:
            log.info("booking_reminder.not_found", booking_id=booking_id)
            return
        b = result.data[0]
        if b["status"] != "confirmed":
            log.info("booking_reminder.skip_not_confirmed", booking_id=booking_id, status=b["status"])
            return

        starts_at = datetime.fromisoformat(b["starts_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = starts_at - now

        if timedelta(minutes=10) <= delta <= timedelta(hours=1, minutes=5):
            for pid in (b["host_id"], b["guest_id"]):
                await send_notification_to(pid, "booking_reminder", {
                    "booking_id": booking_id,
                    "starts_at": b["starts_at"],
                    "minutes_until": int(delta.total_seconds() / 60),
                })
            log.info("booking_reminder.sent", booking_id=booking_id)
        else:
            log.info("booking_reminder.outside_window", booking_id=booking_id, delta_minutes=int(delta.total_seconds() / 60))
    except Exception:
        log.exception("booking_reminder.error", booking_id=booking_id)
