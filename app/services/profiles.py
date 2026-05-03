"""Profile service — get, update, avatar, projects, links, interests, badges."""
import asyncio
import hashlib
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from supabase import Client

from app.db.client import get_admin_client
from app.models.profiles import (
    AvatarUploadResponse,
    BadgeOut,
    InterestOut,
    ProfileLinkIn,
    ProfileLinkOut,
    ProfileOut,
    ProfileUpdate,
    ProjectIn,
    ProjectOut,
)


def _require(result: list, detail_code: str, msg: str) -> dict:  # type: ignore[type-arg]
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": detail_code, "message": msg},
        )
    return result[0]  # type: ignore[return-value]


def _attach_interests(row: dict, db: Client) -> dict:  # type: ignore[type-arg]
    """Join profile_interests → interests and attach name list to the row."""
    try:
        pi = db.table("profile_interests").select("interest_id").eq("profile_id", row["id"]).execute()
        if pi.data:
            ids = [r["interest_id"] for r in pi.data]
            i_res = db.table("interests").select("name").in_("id", ids).execute()
            row["interests"] = [r["name"] for r in i_res.data]
        else:
            row["interests"] = []
    except Exception:
        row["interests"] = []
    return row


async def get_profile_by_id(profile_id: str, db: Client) -> ProfileOut:
    result = db.table("profiles").select("*").eq("id", profile_id).execute()
    row = _require(result.data, "profile_not_found", "Profile not found")
    return ProfileOut(**_attach_interests(row, db))


async def get_profile_by_username(username: str, db: Client) -> ProfileOut:
    result = db.table("profiles").select("*").eq("username", username).execute()
    row = _require(result.data, "profile_not_found", f"No profile with username '{username}'")
    return ProfileOut(**_attach_interests(row, db))


async def update_profile(profile_id: str, body: ProfileUpdate, db: Client) -> ProfileOut:
    dirty = body.model_dump(exclude_none=True)
    if not dirty:
        return await get_profile_by_id(profile_id, db)

    result = (
        db.table("profiles")
        .update(dirty)
        .eq("id", profile_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "profile_not_found", "message": "Profile not found"},
        )

    # Enqueue re-embedding if relevant fields changed (best-effort; skips if Redis unavailable)
    embed_fields = {"bio", "headline", "looking_for"}
    if embed_fields & set(dirty.keys()):
        try:
            from app.worker import enqueue
            await enqueue("embed_profile", {"profile_id": profile_id})
        except Exception:
            pass

    return ProfileOut(**result.data[0])


async def upload_avatar(profile_id: str, file: UploadFile, db: Client) -> AvatarUploadResponse:
    admin = get_admin_client()
    content = await file.read()
    ext = (file.filename or "avatar").rsplit(".", 1)[-1].lower()
    allowed = {"jpg", "jpeg", "png", "webp"}
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_file_type", "message": f"Allowed: {allowed}"},
        )
    path = f"avatars/{profile_id}/{uuid.uuid4()}.{ext}"
    await asyncio.to_thread(
        admin.storage.from_("avatars").upload,
        path,
        content,
        {"content-type": file.content_type or "image/jpeg"},
    )
    public_url = admin.storage.from_("avatars").get_public_url(path)
    db.table("profiles").update({"avatar_url": public_url}).eq("id", profile_id).execute()
    return AvatarUploadResponse(avatar_url=public_url)


# ── Projects ────────────────────────────────────────────────

async def list_projects(profile_id: UUID, db: Client) -> list[ProjectOut]:
    result = db.table("projects").select("*").eq("profile_id", str(profile_id)).execute()
    return [ProjectOut(**r) for r in result.data]


async def create_project(profile_id: str, body: ProjectIn, db: Client) -> ProjectOut:
    row = {**body.model_dump(), "profile_id": profile_id}
    result = db.table("projects").insert(row).execute()
    return ProjectOut(**result.data[0])


async def update_project(profile_id: str, project_id: UUID, body: ProjectIn, db: Client) -> ProjectOut:
    result = (
        db.table("projects")
        .update(body.model_dump())
        .eq("id", str(project_id))
        .eq("profile_id", profile_id)
        .execute()
    )
    row = _require(result.data, "project_not_found", "Project not found")
    return ProjectOut(**row)


async def delete_project(profile_id: str, project_id: UUID, db: Client) -> None:
    db.table("projects").delete().eq("id", str(project_id)).eq("profile_id", profile_id).execute()


# ── Links ────────────────────────────────────────────────────

async def list_links(profile_id: UUID, db: Client) -> list[ProfileLinkOut]:
    result = db.table("profile_links").select("*").eq("profile_id", str(profile_id)).execute()
    return [ProfileLinkOut(**r) for r in result.data]


async def add_link(profile_id: str, body: ProfileLinkIn, db: Client) -> ProfileLinkOut:
    row = {**body.model_dump(), "profile_id": profile_id}
    result = db.table("profile_links").insert(row).execute()
    # Enqueue verification for GitHub/LinkedIn links
    link_out = ProfileLinkOut(**result.data[0])
    if str(body.kind).lower() in ("github", "linkedin"):
        try:
            from app.worker import enqueue
            await enqueue("verify_github_link", {"link_id": str(link_out.id), "platform": str(body.kind)})
        except Exception:
            pass
    return link_out


async def delete_link(profile_id: str, link_id: UUID, db: Client) -> None:
    db.table("profile_links").delete().eq("id", str(link_id)).eq("profile_id", profile_id).execute()


# ── Interests ────────────────────────────────────────────────

async def list_interests(db: Client) -> list[InterestOut]:
    result = db.table("interests").select("*").order("name").execute()
    return [InterestOut(**r) for r in result.data]


async def set_interests(profile_id: str, interest_ids: list[UUID], db: Client) -> None:
    # Replace all interests for this profile
    db.table("profile_interests").delete().eq("profile_id", profile_id).execute()
    if interest_ids:
        rows = [{"profile_id": profile_id, "interest_id": str(iid)} for iid in interest_ids]
        db.table("profile_interests").insert(rows).execute()
    try:
        from app.worker import enqueue
        await enqueue("embed_profile", {"profile_id": profile_id})
    except Exception:
        pass


async def set_interests_by_name(profile_id: str, names: list[str], db: Client) -> None:
    """Accept interest names (not UUIDs) — looks up IDs internally."""
    if names:
        name_res = db.table("interests").select("id").in_("name", names).execute()
        ids = [UUID(r["id"]) for r in name_res.data]
    else:
        ids = []
    await set_interests(profile_id, ids, db)


# ── Badges ────────────────────────────────────────────────────

async def list_badges(profile_id: UUID, db: Client) -> list[BadgeOut]:
    result = db.table("verification_badges").select("*").eq("profile_id", str(profile_id)).execute()
    return [BadgeOut(**r) for r in result.data]
