"""
/api/v1/likes — like, pass, received likes.
"""
from fastapi import APIRouter

from app.deps import Redis, UserDB, UserID
from app.models.common import OkResponse
from app.models.likes import LikeIn, LikeResponse, PassIn, PassOut
from app.services import likes as likes_svc
from app.services.rate_limit import check_rate_limit

router = APIRouter(tags=["likes"])


@router.post("/likes", response_model=LikeResponse, status_code=201)
async def send_like(uid: UserID, db: UserDB, redis: Redis, body: LikeIn) -> LikeResponse:
    if redis is not None:
        await check_rate_limit(redis, f"like:{uid}", limit=200, window=86400)
    return await likes_svc.send_like(uid, body, db)


@router.post("/passes", response_model=OkResponse, status_code=201)
async def send_pass(uid: UserID, db: UserDB, redis: Redis, body: PassIn) -> OkResponse:
    if redis is not None:
        await check_rate_limit(redis, f"pass:{uid}", limit=500, window=86400)
    await likes_svc.send_pass(uid, body, db)
    return OkResponse()


@router.get("/likes/received", response_model=list)
async def received_likes(uid: UserID, db: UserDB) -> list:  # type: ignore[type-arg]
    return await likes_svc.get_received_likes(uid, db)
