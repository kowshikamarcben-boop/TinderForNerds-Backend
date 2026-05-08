"""Profile service — get, update, avatar, projects, links, interests, badges."""
import asyncio
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
    """Attach interest names using a single nested JOIN (eliminates N+1)."""
    try:
        pi = db.table("profile_interests").select("interests(name)").eq("profile_id", row["id"]).execute()
        row["interests"] = [r["interests"]["name"] for r in pi.data if r.get("interests")]
    except Exception:
        row["interests"] = []
    return row


async def get_profile_by_id(profile_id: str, db: Client) -> ProfileOut:
    result = db.table("profiles").select("*").eq("id", profile_id).execute()
    row = _require(result.data, "profile_not_found", "Profile not found")
    return ProfileOut(**_attach_interests(row, db))


async def get_profile_by_id_with_visibility(profile_id: str, requester_id: str, db: Client) -> ProfileOut:
    """Get profile by UUID with visibility enforcement — prevents IDOR on private profiles."""
    result = db.table("profiles").select("*").eq("id", profile_id).execute()
    row = _require(result.data, "profile_not_found", "Profile not found")
    # Private profiles are only visible to the owner or mutual matches
    if row.get("visibility") == "private" and row["id"] != requester_id:
        admin = get_admin_client()
        match_res = admin.table("matches").select("id").or_(
            f"user_a_id.eq.{requester_id},user_b_id.eq.{requester_id}"
        ).or_(
            f"user_a_id.eq.{profile_id},user_b_id.eq.{profile_id}"
        ).eq("status", "active").execute()
        if not match_res.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "profile_private", "message": "This profile is private"},
            )
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


_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB
_MAGIC_BYTES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG": "png",
    b"RIFF": "webp",
}


async def upload_avatar(profile_id: str, file: UploadFile, db: Client) -> AvatarUploadResponse:
    admin = get_admin_client()
    content = await file.read()
    if len(content) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "file_too_large", "message": "Avatar must be under 5 MB"},
        )
    # Validate by magic bytes, not just extension
    detected = None
    for magic, fmt in _MAGIC_BYTES.items():
        if content[:len(magic)] == magic:
            detected = fmt
            break
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_file_type", "message": "Allowed formats: jpg, png, webp"},
        )
    ext = "jpeg" if detected == "jpg" else detected
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
    import structlog
    log = structlog.get_logger()
    row = {**body.model_dump(mode="json"), "profile_id": profile_id}
    # Upsert by (profile_id, kind) to avoid duplicate constraint errors
    result = (
        db.table("profile_links")
        .upsert(row, on_conflict="profile_id,kind")
        .execute()
    )
    link_out = ProfileLinkOut(**result.data[0])
    if str(body.kind).lower() in ("github", "linkedin"):
        try:
            from app.worker import enqueue
            await enqueue("verify_github_link", {"link_id": str(link_out.id), "platform": str(body.kind)})
        except Exception as exc:
            log.warning("profiles.enqueue_verify_failed", link_id=str(link_out.id), error=str(exc))
    return link_out


async def delete_link(profile_id: str, link_id: UUID, db: Client) -> None:
    db.table("profile_links").delete().eq("id", str(link_id)).eq("profile_id", profile_id).execute()


# ── Interests ────────────────────────────────────────────────

async def list_interests(db: Client) -> list[InterestOut]:
    result = db.table("interests").select("*").order("name").limit(500).execute()
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
    """Accept interest names (not UUIDs) — looks up IDs internally. Raises if any name unknown."""
    if names:
        name_res = db.table("interests").select("id,name").in_("name", names).execute()
        found = {r["name"] for r in name_res.data}
        unknown = set(names) - found
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "unknown_interests", "message": f"Unknown interests: {sorted(unknown)}"},
            )
        ids = [UUID(r["id"]) for r in name_res.data]
    else:
        ids = []
    await set_interests(profile_id, ids, db)


# ── Badges ────────────────────────────────────────────────────

async def list_badges(profile_id: UUID, db: Client) -> list[BadgeOut]:
    result = db.table("verification_badges").select("*").eq("profile_id", str(profile_id)).execute()
    return [BadgeOut(**r) for r in result.data]


# ── GDPR ──────────────────────────────────────────────────────

async def export_profile(profile_id: str) -> dict:  # type: ignore[type-arg]
    """Return all personal data for a user — GDPR Art. 20 data portability."""
    admin = get_admin_client()
    profile = admin.table("profiles").select("*").eq("id", profile_id).execute().data
    links = admin.table("profile_links").select("*").eq("profile_id", profile_id).execute().data
    projects = admin.table("projects").select("*").eq("profile_id", profile_id).execute().data
    interests_join = admin.table("profile_interests").select("interest_id").eq("profile_id", profile_id).execute().data
    interest_ids = [r["interest_id"] for r in interests_join]
    interests = (
        admin.table("interests").select("name").in_("id", interest_ids).execute().data
        if interest_ids else []
    )
    messages = admin.table("messages").select("*").eq("sender_id", profile_id).execute().data
    bookings = (
        admin.table("bookings")
        .select("*")
        .or_(f"host_id.eq.{profile_id},guest_id.eq.{profile_id}")
        .execute().data
    )
    return {
        "profile": profile[0] if profile else {},
        "links": links,
        "projects": projects,
        "interests": [i["name"] for i in interests],
        "messages": messages,
        "bookings": bookings,
    }


async def delete_account(profile_id: str) -> None:
    """Hard-delete all user data and revoke Supabase Auth account — GDPR Art. 17."""
    import structlog
    log = structlog.get_logger()
    admin = get_admin_client()
    # Cascading deletes handle most tables via FK constraints.
    # Delete profile row first, then auth user.
    admin.table("profiles").delete().eq("id", profile_id).execute()
    try:
        admin.auth.admin.delete_user(profile_id)
    except Exception as exc:
        log.error("delete_account.auth_delete_failed", profile_id=profile_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "delete_failed", "message": "Account deletion failed — contact support"},
        ) from exc
