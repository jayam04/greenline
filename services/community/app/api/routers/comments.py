from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ...db.database import get_db
    from ...schemas.comment import CommentCreate, CommentResponse
    from ...services.comment_service import (
        create_comment as create_comment_service,
        get_comments as get_comments_service
    )
    from ..deps import get_current_author_sub, get_optional_author_sub
except (ImportError, ValueError):
    from app.db.database import get_db
    from app.schemas.comment import CommentCreate, CommentResponse
    from app.services.comment_service import (
        create_comment as create_comment_service,
        get_comments as get_comments_service
    )
    from app.api.deps import get_current_author_sub, get_optional_author_sub

router = APIRouter(tags=["comments"])


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_comment(
    post_id: int,
    comment_in: CommentCreate,
    author_sub: str = Depends(get_current_author_sub),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a comment or threaded reply on a post.
    Increments post comments_count and links parent comment if supplied.
    """
    comment = await create_comment_service(
        db=db,
        post_id=post_id,
        author_sub=author_sub,
        comment_in=comment_in
    )
    return comment


@router.get(
    "/posts/{post_id}/comments",
    response_model=List[CommentResponse],
    status_code=status.HTTP_200_OK
)
async def list_comments(
    post_id: int,
    limit: int = Query(50, ge=1, le=200, description="Max comments to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    _author_sub: Optional[str] = Depends(get_optional_author_sub)
):
    """
    Retrieve chronological comments list for a post.
    """
    comments = await get_comments_service(
        db=db,
        post_id=post_id,
        limit=limit,
        offset=offset
    )
    return comments
