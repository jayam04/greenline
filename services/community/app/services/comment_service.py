from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ..db.models import CommunityPost, CommunityComment
    from ..schemas.comment import CommentCreate
except (ImportError, ValueError):
    from app.db.models import CommunityPost, CommunityComment
    from app.schemas.comment import CommentCreate


async def create_comment(
    db: AsyncSession,
    post_id: int,
    author_sub: str,
    comment_in: CommentCreate
) -> CommunityComment:
    """Create comment on post, verifying post and optional parent exist, and incrementing post comments_count."""
    # Verify post exists
    post_stmt = select(CommunityPost).where(CommunityPost.id == post_id)
    post_res = await db.execute(post_stmt)
    post = post_res.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )

    # Verify parent comment if provided
    if comment_in.parent_comment_id is not None:
        parent_stmt = select(CommunityComment).where(
            CommunityComment.id == comment_in.parent_comment_id,
            CommunityComment.post_id == post_id
        )
        parent_res = await db.execute(parent_stmt)
        parent = parent_res.scalars().first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent comment {comment_in.parent_comment_id} not found on post {post_id}"
            )

    pseudonym = comment_in.author_pseudonym.strip() if (comment_in.author_pseudonym and comment_in.author_pseudonym.strip()) else "Anonymous"

    comment = CommunityComment(
        post_id=post_id,
        parent_comment_id=comment_in.parent_comment_id,
        user_id=author_sub,
        author_pseudonym=pseudonym,
        content=comment_in.content
    )
    db.add(comment)

    # Increment post.comments_count
    post.comments_count = (post.comments_count or 0) + 1

    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comments(
    db: AsyncSession,
    post_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[CommunityComment]:
    """Retrieve comments for a post in chronological order."""
    # Verify post exists
    post_stmt = select(CommunityPost).where(CommunityPost.id == post_id)
    post_res = await db.execute(post_stmt)
    post = post_res.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )

    stmt = (
        select(CommunityComment)
        .where(CommunityComment.post_id == post_id)
        .order_by(CommunityComment.created_at.asc(), CommunityComment.id.asc())
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_comment_by_id(
    db: AsyncSession,
    comment_id: int
) -> Optional[CommunityComment]:
    """Retrieve comment by ID."""
    stmt = select(CommunityComment).where(CommunityComment.id == comment_id)
    res = await db.execute(stmt)
    return res.scalars().first()
