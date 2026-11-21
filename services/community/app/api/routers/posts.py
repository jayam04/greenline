from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ...db.database import get_db
    from ...schemas.post import PostCreate, PostResponse, PostListResponse
    from ...services.post_service import (
        create_post as create_post_service,
        get_posts as get_posts_service,
        get_post_by_id as get_post_by_id_service,
        delete_post as delete_post_service
    )
    from ...services.user_service import get_user_uuid
    from ..deps import get_current_author_sub, get_optional_author_sub
except (ImportError, ValueError):
    from app.db.database import get_db
    from app.schemas.post import PostCreate, PostResponse, PostListResponse
    from app.services.post_service import (
        create_post as create_post_service,
        get_posts as get_posts_service,
        get_post_by_id as get_post_by_id_service,
        delete_post as delete_post_service
    )
    from app.services.user_service import get_user_uuid
    from app.api.deps import get_current_author_sub, get_optional_author_sub

router = APIRouter(tags=["posts"])


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_in: PostCreate,
    author_sub: str = Depends(get_current_author_sub),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new community post with text content and optional media attachments.
    Requires authenticated user (extracts author_sub from RS256 JWT sub claim).
    """
    post = await create_post_service(db=db, author_sub=author_sub, post_in=post_in)
    return post


@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    limit: int = Query(20, ge=1, le=100, description="Page size limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort: str = Query("latest", description="Sorting order: latest or oldest"),
    db: AsyncSession = Depends(get_db),
    _author_sub: Optional[str] = Depends(get_optional_author_sub)
):
    """
    Retrieve community posts feed with pagination and sorting by latest created_at descending.
    """
    items, total = await get_posts_service(db=db, limit=limit, offset=offset, sort=sort)
    return PostListResponse(
        items=items,
        total_count=total,
        limit=limit,
        offset=offset
    )


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_single_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _author_sub: Optional[str] = Depends(get_optional_author_sub)
):
    """Retrieve a single post by ID."""
    post = await get_post_by_id_service(db=db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )
    return post


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    author_sub: str = Depends(get_current_author_sub),
    db: AsyncSession = Depends(get_db)
):
    """Delete a post and its associated comments."""
    post = await get_post_by_id_service(db=db, post_id=post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )
    user_uuid = get_user_uuid(author_sub)
    if post.user_id not in (user_uuid, author_sub):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this post"
        )

    await delete_post_service(db=db, post_id=post_id, author_sub=author_sub)
    return None
