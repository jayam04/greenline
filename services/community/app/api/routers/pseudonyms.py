from fastapi import APIRouter, status

try:
    from ...schemas.pseudonym import RandomPseudonymResponse
    from ...services.pseudonym_service import generate_random_pseudonym
except (ImportError, ValueError):
    from app.schemas.pseudonym import RandomPseudonymResponse
    from app.services.pseudonym_service import generate_random_pseudonym

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
