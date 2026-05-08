"""
arq worker entry point.
Job map: string name → coroutine function.
Enqueue via: await enqueue("job_name", payload)
"""
import hashlib
import json
import structlog
from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.worker.embed_profile import embed_profile
from app.worker.send_notification import send_notification
from app.worker.booking_reminder import booking_reminder
from app.worker.event_reminder import event_reminder
from app.worker.verify_github_link import verify_github_link
from app.worker.cleanup_stale_data import cleanup_stale_data

log = structlog.get_logger()

_pool = None


async def _get_pool():  # type: ignore[return]
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue(job_name: str, payload: dict) -> None:  # type: ignore[type-arg]
    # Deterministic job_id deduplicates identical enqueues (idempotency)
    job_id = hashlib.sha256(
        f"{job_name}:{json.dumps(payload, sort_keys=True)}".encode()
    ).hexdigest()[:32]
    try:
        pool = await _get_pool()
        await pool.enqueue_job(job_name, payload, _job_id=job_id)
        log.debug("worker.enqueued", job=job_name, job_id=job_id)
    except Exception as exc:
        log.warning("worker.enqueue_failed", job=job_name, error=str(exc))


class WorkerSettings:
    functions = [
        embed_profile,
        send_notification,
        booking_reminder,
        event_reminder,
        verify_github_link,
        cleanup_stale_data,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 120
    job_timeout_by_name = {"embed_profile": 300}


if __name__ == "__main__":
    from arq import run_worker

    run_worker(WorkerSettings)
