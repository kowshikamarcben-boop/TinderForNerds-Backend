"""
/api/v1/me — current-user profile CRUD.
Thin router. All logic in app/services/profiles.py.
"""
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.deps import UserDB, UserID
from app.models.common import OkResponse
from app.models.profiles import AvatarUploadResponse, ProfileOut, ProfileUpdate
from app.services import profiles as profile_svc

router = APIRouter(tags=["users"])


@router.get("/me", response_model=ProfileOut)
async def get_me(uid: UserID, db: UserDB) -> ProfileOut:
    return await profile_svc.get_profile_by_id(uid, db)


@router.patch("/me", response_model=ProfileOut)
async def update_me(uid: UserID, db: UserDB, body: ProfileUpdate) -> ProfileOut:
    return await profile_svc.update_profile(uid, body, db)


@router.post("/me/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(uid: UserID, db: UserDB, file: UploadFile = File(...)) -> AvatarUploadResponse:
    return await profile_svc.upload_avatar(uid, file, db)


@router.get("/me/export")
async def export_my_data(uid: UserID) -> JSONResponse:
    data = await profile_svc.export_profile(uid)
    return JSONResponse(content=data, headers={"Content-Disposition": 'attachment; filename="my_data.json"'})


@router.delete("/me", response_model=OkResponse)
async def delete_my_account(uid: UserID) -> OkResponse:
    await profile_svc.delete_account(uid)
    return OkResponse()
