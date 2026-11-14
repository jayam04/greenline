import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_comment_unauthenticated(community_client: AsyncClient):
    """POST /posts/{post_id}/comments without auth returns 401 Unauthorized."""
    response = await community_client.post(
        "/api/v1/community/posts/1/comments",
        json={"content": "Unauthenticated comment"}
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_comment_empty_content(auth_community_client: AsyncClient):
    """POST /posts/{post_id}/comments with empty content returns 422 Unprocessable Entity."""
    response = await auth_community_client.post(
        "/api/v1/community/posts/1/comments",
        json={"content": "   "}
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_comment_nonexistent_post(auth_community_client: AsyncClient):
    """POST /posts/{post_id}/comments on non-existent post returns 404 Not Found."""
    response = await auth_community_client.post(
        "/api/v1/community/posts/999999/comments",
        json={"content": "Comment on ghost post"}
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_comment_success_and_increments_count(
    auth_community_client: AsyncClient,
    community_client: AsyncClient
):
    """POST comment creates comment, returns 201 Created with CommentResponse, and increments post comments_count."""
    # 1. Create a post
    post_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Post to comment upon", "author_pseudonym": "Giant Elephant"}
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["post_id"]
    assert post_res.json()["comments_count"] == 0

    # 2. Add first comment
    comment_payload = {
        "content": "First thoughtful reply!",
        "author_pseudonym": "Crazy Dog"
    }
    c_res = await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json=comment_payload
    )
    assert c_res.status_code == 201
    c_data = c_res.json()
    assert "id" in c_data
    assert "comment_id" in c_data
    assert c_data["id"] == c_data["comment_id"]
    assert c_data["post_id"] == post_id
    assert c_data["parent_comment_id"] is None
    assert c_data["author_sub"] == "auth0|community_user_a"
    assert c_data["author_pseudonym"] == "Crazy Dog"
    assert c_data["content"] == comment_payload["content"]
    assert "created_at" in c_data
    assert "updated_at" in c_data

    # 3. Check post.comments_count is now 1
    post_get = await community_client.get(f"/api/v1/community/posts/{post_id}")
    assert post_get.status_code == 200
    assert post_get.json()["comments_count"] == 1


@pytest.mark.anyio
async def test_create_threaded_comment_with_parent(
    auth_community_client: AsyncClient,
    community_client: AsyncClient
):
    """Verify nesting/threaded comments using parent_comment_id."""
    post_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Thread parent test"}
    )
    post_id = post_res.json()["post_id"]

    # Top-level comment
    c1_res = await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"content": "Top-level comment"}
    )
    assert c1_res.status_code == 201
    parent_comment_id = c1_res.json()["comment_id"]

    # Reply to c1
    c2_res = await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={
            "content": "Nested reply to c1",
            "parent_comment_id": parent_comment_id
        }
    )
    assert c2_res.status_code == 201
    c2_data = c2_res.json()
    assert c2_data["parent_comment_id"] == parent_comment_id

    # Post comments_count is now 2
    post_get = await community_client.get(f"/api/v1/community/posts/{post_id}")
    assert post_get.json()["comments_count"] == 2


@pytest.mark.anyio
async def test_create_comment_invalid_parent(auth_community_client: AsyncClient):
    """POST comment with nonexistent parent_comment_id returns 404 or 400."""
    post_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Post with invalid reply test"}
    )
    post_id = post_res.json()["post_id"]

    res = await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={
            "content": "Reply to phantom parent",
            "parent_comment_id": 999999
        }
    )
    assert res.status_code in (400, 404)


@pytest.mark.anyio
async def test_get_comments_for_post(
    auth_community_client: AsyncClient,
    community_client: AsyncClient
):
    """GET /posts/{post_id}/comments returns comments list in chronological order."""
    post_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Post with multiple comments"}
    )
    post_id = post_res.json()["post_id"]

    # Add 2 comments
    await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"content": "Comment Alpha"}
    )
    await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"content": "Comment Beta"}
    )

    get_res = await community_client.get(f"/api/v1/community/posts/{post_id}/comments")
    assert get_res.status_code == 200
    comments = get_res.json()
    assert len(comments) == 2
    assert comments[0]["content"] == "Comment Alpha"
    assert comments[1]["content"] == "Comment Beta"


@pytest.mark.anyio
async def test_get_comments_nonexistent_post(community_client: AsyncClient):
    """GET /posts/{post_id}/comments returns 404 if post does not exist."""
    res = await community_client.get("/api/v1/community/posts/999999/comments")
    assert res.status_code == 404


@pytest.mark.anyio
async def test_get_comments_deterministic_tie_breaker_same_timestamp(
    auth_community_client: AsyncClient,
    community_client: AsyncClient,
    community_db_session
):
    """GET /posts/{post_id}/comments orders deterministically by created_at.asc(), id.asc() when timestamps match."""
    from datetime import datetime, timezone
    from app.db.models import CommunityComment

    # 1. Create post
    post_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Post for tie-breaker verification"}
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["post_id"]

    # 2. Insert two comments directly with identical created_at
    fixed_time = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    c1 = CommunityComment(
        post_id=post_id,
        user_id="auth0|user1",
        author_pseudonym="User One",
        content="First Comment Same Timestamp",
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    c2 = CommunityComment(
        post_id=post_id,
        user_id="auth0|user2",
        author_pseudonym="User Two",
        content="Second Comment Same Timestamp",
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    community_db_session.add(c1)
    await community_db_session.commit()
    await community_db_session.refresh(c1)

    community_db_session.add(c2)
    await community_db_session.commit()
    await community_db_session.refresh(c2)

    assert c1.id < c2.id

    # 3. Retrieve comments via endpoint
    get_res = await community_client.get(f"/api/v1/community/posts/{post_id}/comments")
    assert get_res.status_code == 200
    comments = get_res.json()
    assert len(comments) == 2
    assert comments[0]["id"] == c1.id
    assert comments[0]["content"] == "First Comment Same Timestamp"
    assert comments[1]["id"] == c2.id
    assert comments[1]["content"] == "Second Comment Same Timestamp"

