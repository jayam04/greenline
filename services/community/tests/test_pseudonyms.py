import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_random_pseudonym_endpoint(community_client: AsyncClient):
    """GET /api/v1/community/pseudonyms/random returns 200 OK with expected JSON structure."""
    response = await community_client.get("/api/v1/community/pseudonyms/random")
    assert response.status_code == 200
    data = response.json()
    assert "pseudonym" in data
    pseudonym = data["pseudonym"]
    assert isinstance(pseudonym, str)
    parts = pseudonym.split(" ")
    assert len(parts) >= 2, f"Expected '<Adjective> <Noun>', got '{pseudonym}'"
    for part in parts:
        assert part[0].isupper(), f"Expected title-cased words, got '{part}'"


@pytest.mark.anyio
async def test_random_pseudonym_generator_service():
    """Verify the pseudonym generator produces diverse valid pseudonyms."""
    from app.services.pseudonym_service import generate_random_pseudonym

    generated = {generate_random_pseudonym() for _ in range(50)}
    assert len(generated) > 5, "Pseudonym generator must produce varied names"
    for name in generated:
        parts = name.split(" ")
        assert len(parts) >= 2
