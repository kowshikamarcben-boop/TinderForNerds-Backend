"""
/api/v1/ai — starter message, bio rewrite, interest suggestions.
"""
from uuid import UUID

from fastapi import APIRouter

from app.deps import Redis, UserID
from app.models.ai import (
    BioRewriteRequest,
    BioRewriteResponse,
    InterestSuggestRequest,
    InterestSuggestResponse,
    StarterResponse,
)
from app.services import starter_gen, embeddings as embed_svc
from app.services.rate_limit import check_rate_limit

router = APIRouter(tags=["ai"])


@router.get("/ai/starter/{match_id}", response_model=StarterResponse)
async def get_starter(match_id: UUID, uid: UserID, redis: Redis) -> StarterResponse:
    if redis is not None:
        await check_rate_limit(redis, f"ai_starter:{uid}", limit=30, window=3600)
    return await starter_gen.get_starter(match_id, uid, redis)


@router.post("/ai/bio/rewrite", response_model=BioRewriteResponse)
async def rewrite_bio(uid: UserID, redis: Redis, body: BioRewriteRequest) -> BioRewriteResponse:
    if redis is not None:
        await check_rate_limit(redis, f"ai_bio:{uid}", limit=10, window=3600)
    return await embed_svc.rewrite_bio(body)


@router.post("/ai/interests/suggest", response_model=InterestSuggestResponse)
async def suggest_interests(uid: UserID, redis: Redis, body: InterestSuggestRequest) -> InterestSuggestResponse:
    if redis is not None:
        await check_rate_limit(redis, f"ai_suggest:{uid}", limit=20, window=3600)
    return await embed_svc.suggest_interests(body)
