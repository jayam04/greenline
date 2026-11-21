import uuid
from typing import Optional, Dict, Any
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ..db.models import CommunityUser, CommunityPost, CommunityComment
except (ImportError, ValueError):
    from app.db.models import CommunityUser, CommunityPost, CommunityComment

# Canonical Greenline User Namespace (RFC 4122 UUIDv5)
GREENLINE_USER_NAMESPACE = uuid.UUID("a3bb189e-8bf9-3888-9912-ace4e6543002")


def get_user_uuid(sub_or_id: str) -> str:
    """
    Return a canonical RFC 4122 UUID string representing a user.
    If sub_or_id is already a valid UUID string, returns its normalized lowercase form.
    Otherwise, generates a deterministic UUIDv5 using the Greenline user namespace.
    """
    if not sub_or_id or not str(sub_or_id).strip():
        return str(uuid.uuid5(GREENLINE_USER_NAMESPACE, "anonymous"))
    val = str(sub_or_id).strip()
    try:
        parsed = uuid.UUID(val)
        return str(parsed)
    except (ValueError, AttributeError):
        return str(uuid.uuid5(GREENLINE_USER_NAMESPACE, val))


async def get_or_create_user(
    db: AsyncSession,
    author_sub: str,
    default_pseudonym: Optional[str] = None
) -> CommunityUser:
    """Retrieve existing CommunityUser by user_uuid / auth0_sub, or create a new record."""
    user_uuid = get_user_uuid(author_sub)

    # 1. Look up by user_uuid or auth0_sub
    stmt = select(CommunityUser).where(
        or_(CommunityUser.user_uuid == user_uuid, CommunityUser.auth0_sub == author_sub)
    )
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        pseudo = (
            default_pseudonym.strip()
            if (default_pseudonym and default_pseudonym.strip())
            else "Anonymous"
        )
        user = CommunityUser(
            user_uuid=user_uuid,
            auth0_sub=author_sub,
            pseudonym=pseudo
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception:
            await db.rollback()
            # If concurrent insert occurred, re-query
            res = await db.execute(stmt)
            user = res.scalars().first()
            if not user:
                raise
    return user


async def get_user_profile(
    db: AsyncSession,
    author_sub: str
) -> Dict[str, Any]:
    """Retrieve user UUID and current pseudonym."""
    user = await get_or_create_user(db, author_sub)
    return {
        "user_uuid": user.user_uuid,
        "pseudonym": user.pseudonym
    }


async def update_user_pseudonym(
    db: AsyncSession,
    author_sub: str,
    new_pseudonym: str
) -> Dict[str, Any]:
    """
    Update a user's pseudonym in community_users, and cascade the updated pseudonym
    to all older posts and comments created by this user across the community database.
    """
    cleaned_pseudonym = new_pseudonym.strip()
    if not cleaned_pseudonym:
        cleaned_pseudonym = "Anonymous"

    user_uuid = get_user_uuid(author_sub)

    # 1. Update or create CommunityUser entry
    user = await get_or_create_user(db, author_sub, default_pseudonym=cleaned_pseudonym)
    user.pseudonym = cleaned_pseudonym

    # 2. Update all older community posts created by this user
    # Match both user_uuid and legacy author_sub to guarantee seamless backwards compatibility
    stmt_posts = (
        update(CommunityPost)
        .where(or_(CommunityPost.user_id == user_uuid, CommunityPost.user_id == author_sub))
        .values(
            user_id=user_uuid,
            author_pseudonym=cleaned_pseudonym
        )
    )
    res_posts = await db.execute(stmt_posts)
    posts_updated = res_posts.rowcount or 0

    # 3. Update all older community comments created by this user
    stmt_comments = (
        update(CommunityComment)
        .where(or_(CommunityComment.user_id == user_uuid, CommunityComment.user_id == author_sub))
        .values(
            user_id=user_uuid,
            author_pseudonym=cleaned_pseudonym
        )
    )
    res_comments = await db.execute(stmt_comments)
    comments_updated = res_comments.rowcount or 0

    await db.commit()
    await db.refresh(user)

    return {
        "user_uuid": user.user_uuid,
        "pseudonym": user.pseudonym,
        "updated_posts": posts_updated,
        "updated_comments": comments_updated
    }
