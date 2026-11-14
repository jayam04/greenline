import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_post_unauthenticated(community_client: AsyncClient):
    """POST /posts without Authorization header returns 401 Unauthorized."""
    payload = {
        "content": "Hello community!",
        "author_pseudonym": "Test Author"
    }
    response = await community_client.post("/api/v1/community/posts", json=payload)
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_post_invalid_token(community_client: AsyncClient):
    """POST /posts with invalid token returns 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid.jwt.token"}
    payload = {"content": "Hello community!"}
    response = await community_client.post("/api/v1/community/posts", json=payload, headers=headers)
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_post_empty_content_rejected(auth_community_client: AsyncClient):
    """POST /posts with empty or whitespace-only content returns 422 Unprocessable Entity."""
    # Empty string
    response = await auth_community_client.post("/api/v1/community/posts", json={"content": ""})
    assert response.status_code == 422

    # Whitespace only
    response = await auth_community_client.post("/api/v1/community/posts", json={"content": "    \n\t  "})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_post_content_exceeds_max_chars(auth_community_client: AsyncClient):
    """POST /posts with content exceeding 10,000 characters returns 422 Unprocessable Entity."""
    response = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "a" * 10001}
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_post_success(auth_community_client: AsyncClient):
    """POST /posts with valid payload returns 201 Created with full PostResponse schema."""
    payload = {
        "content": "Discussing portfolio rebalancing strategies for Q4 2026.",
        "author_pseudonym": "Giant Elephant",
        "media_attachments": [
            {
                "url": "https://example.com/charts/allocation.png",
                "type": "image",
                "name": "allocation.png",
                "size": 102400
            }
        ]
    }
    response = await auth_community_client.post("/api/v1/community/posts", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert "post_id" in data
    assert data["id"] == data["post_id"]
    assert data["author_sub"] == "auth0|community_user_a"
    assert data["author_pseudonym"] == "Giant Elephant"
    assert data["content"] == payload["content"]
    assert data["comments_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data

    assert data["media_attachments"] is not None
    assert len(data["media_attachments"]) == 1
    assert data["media_attachments"][0]["url"] == "https://example.com/charts/allocation.png"
    assert data["media_attachments"][0]["type"] == "image"
    assert data["media_attachments"][0]["name"] == "allocation.png"
    assert data["media_attachments"][0]["size"] == 102400


@pytest.mark.anyio
async def test_get_posts_empty_feed(community_client: AsyncClient):
    """GET /posts on empty database returns 200 OK with empty items list."""
    response = await community_client.get("/api/v1/community/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total_count"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.anyio
async def test_get_posts_pagination_and_sorting(auth_community_client: AsyncClient, community_client: AsyncClient):
    """Verify GET /posts supports pagination and sorts by latest created_at descending."""
    # Create 3 posts
    for i in range(3):
        res = await auth_community_client.post(
            "/api/v1/community/posts",
            json={"content": f"Post #{i + 1} content", "author_pseudonym": f"Author {i + 1}"}
        )
        assert res.status_code == 201

    # Fetch with limit=2, offset=0
    resp_page1 = await community_client.get("/api/v1/community/posts?limit=2&offset=0")
    assert resp_page1.status_code == 200
    data1 = resp_page1.json()
    assert data1["total_count"] == 3
    assert len(data1["items"]) == 2
    assert data1["items"][0]["content"] == "Post #3 content"
    assert data1["items"][1]["content"] == "Post #2 content"

    # Fetch with limit=2, offset=2
    resp_page2 = await community_client.get("/api/v1/community/posts?limit=2&offset=2")
    assert resp_page2.status_code == 200
    data2 = resp_page2.json()
    assert data2["total_count"] == 3
    assert len(data2["items"]) == 1
    assert data2["items"][0]["content"] == "Post #1 content"


@pytest.mark.anyio
async def test_get_single_post(auth_community_client: AsyncClient, community_client: AsyncClient):
    """GET /posts/{post_id} returns 200 OK for existing post, 404 for non-existent."""
    # Create a post
    res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Single post lookup", "author_pseudonym": "Crazy Dog"}
    )
    assert res.status_code == 201
    post_id = res.json()["post_id"]

    # Retrieve by ID
    get_res = await community_client.get(f"/api/v1/community/posts/{post_id}")
    assert get_res.status_code == 200
    assert get_res.json()["post_id"] == post_id
    assert get_res.json()["author_pseudonym"] == "Crazy Dog"

    # Non-existent
    not_found_res = await community_client.get("/api/v1/community/posts/999999")
    assert not_found_res.status_code == 404
