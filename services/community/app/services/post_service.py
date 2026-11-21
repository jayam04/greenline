import json
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ..db.models import CommunityPost
    from ..schemas.post import PostCreate
    from .user_service import get_user_uuid, get_or_create_user, update_user_pseudonym
except (ImportError, ValueError):
    from app.db.models import CommunityPost
    from app.schemas.post import PostCreate
    from app.services.user_service import get_user_uuid, get_or_create_user, update_user_pseudonym


async def create_post(
    db: AsyncSession,
    author_sub: str,
    post_in: PostCreate
) -> CommunityPost:
    """Create a new community post identifying author by standard UUID."""
    user_uuid = get_user_uuid(author_sub)

    media_json = None
    if post_in.media_attachments:
        media_json = json.dumps([m.model_dump() for m in post_in.media_attachments])

    if post_in.author_pseudonym and post_in.author_pseudonym.strip():
        # User specified or updated pseudonym; sync to user profile and update older posts
        await update_user_pseudonym(db, author_sub, post_in.author_pseudonym.strip())
        pseudonym = post_in.author_pseudonym.strip()
    else:
        # Retrieve configured pseudonym from community user profile
        user = await get_or_create_user(db, author_sub)
        pseudonym = user.pseudonym or "Anonymous"

    post = CommunityPost(
        user_id=user_uuid,
        author_pseudonym=pseudonym,
        content=post_in.content,
        media_attachments=media_json,
        comments_count=0
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def get_posts(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    sort: str = "latest"
) -> Tuple[List[CommunityPost], int]:
    """Retrieve paginated posts ordered by created_at."""
    # Count total
    count_stmt = select(func.count(CommunityPost.id))
    total_count_res = await db.execute(count_stmt)
    total = total_count_res.scalar() or 0

    # Query items
    stmt = select(CommunityPost)
    if sort == "oldest":
        stmt = stmt.order_by(CommunityPost.created_at.asc(), CommunityPost.id.asc())
    else:
        stmt = stmt.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    res = await db.execute(stmt)
    items = list(res.scalars().all())

    return items, total


async def get_post_by_id(
    db: AsyncSession,
    post_id: int
) -> Optional[CommunityPost]:
    """Retrieve single post by ID."""
    stmt = select(CommunityPost).where(CommunityPost.id == post_id)
    res = await db.execute(stmt)
    return res.scalars().first()


async def delete_post(
    db: AsyncSession,
    post_id: int,
    author_sub: Optional[str] = None
) -> bool:
    """Delete post and cascade associated comments."""
    post = await get_post_by_id(db, post_id)
    if not post:
        return False
    if author_sub:
        user_uuid = get_user_uuid(author_sub)
        if post.user_id not in (user_uuid, author_sub):
            return False

    await db.delete(post)
    await db.commit()
    return True
