from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from ...db.database import get_db
    from ...schemas.pseudonym import (
        RandomPseudonymResponse,
        UpdatePseudonymRequest,
        UserProfileResponse
    )
    from ...services.pseudonym_service import generate_random_pseudonym
    from ...services.user_service import get_user_profile, update_user_pseudonym
    from ..deps import get_current_author_sub
except (ImportError, ValueError):
    from app.db.database import get_db
    from app.schemas.pseudonym import (
        RandomPseudonymResponse,
        UpdatePseudonymRequest,
        UserProfileResponse
    )
    from app.services.pseudonym_service import generate_random_pseudonym
    from app.services.user_service import get_user_profile, update_user_pseudonym
    from app.api.deps import get_current_author_sub

router = APIRouter(tags=["pseudonyms"])


@router.get(
    "/pseudonyms/random",
    response_model=RandomPseudonymResponse,
    status_code=status.HTTP_200_OK
)
async def get_random_pseudonym():
    """Generate a random whimsical pseudonym (e.g. 'Giant Elephant', 'Crazy Dog')."""
    pseudonym = generate_random_pseudonym()
    return RandomPseudonymResponse(pseudonym=pseudonym)


@router.get(
    "/pseudonyms/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK
)
async def get_my_pseudonym_profile(
    db: AsyncSession = Depends(get_db),
    author_sub: str = Depends(get_current_author_sub)
):
    """Retrieve current user's UUID and community pseudonym."""
    profile = await get_user_profile(db, author_sub)
    return UserProfileResponse(
        user_uuid=profile["user_uuid"],
        pseudonym=profile["pseudonym"]
    )


@router.put(
    "/pseudonyms/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK
)
async def update_my_pseudonym(
    payload: UpdatePseudonymRequest,
    db: AsyncSession = Depends(get_db),
    author_sub: str = Depends(get_current_author_sub)
):
    """
    Update the authenticated user's community pseudonym, dynamically updating
    their pseudonym across all older posts and comments in the community database.
    """
    res = await update_user_pseudonym(db, author_sub, payload.pseudonym)
    return UserProfileResponse(
        user_uuid=res["user_uuid"],
        pseudonym=res["pseudonym"],
        updated_posts=res["updated_posts"],
        updated_comments=res["updated_comments"]
    )
