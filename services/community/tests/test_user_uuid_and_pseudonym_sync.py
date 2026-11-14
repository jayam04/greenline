import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_post_creation_identifies_user_by_uuid(
    community_client: AsyncClient,
    mint_auth0_token
):
    """Verify that community posts identify authors by a valid RFC 4122 UUID in the backend."""
    token = mint_auth0_token(sub="auth0|unique_user_42")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await community_client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "content": "Testing user UUID identification in backend",
            "author_pseudonym": "Initial Name"
        }
    )
    assert create_res.status_code == 201
    data = create_res.json()

    # author_sub / author_uuid must be a valid UUID
    author_id = data.get("author_uuid") or data.get("author_sub")
    assert author_id is not None
    # Must parse cleanly as an RFC 4122 UUID
    parsed_uuid = uuid.UUID(author_id)
    assert str(parsed_uuid) == author_id


@pytest.mark.anyio
async def test_update_pseudonym_updates_older_posts_and_comments(
    community_client: AsyncClient,
    mint_auth0_token
):
    """
    Verify that updating a user's pseudonym updates the pseudonym on all of their
    previously created posts and comments.
    """
    token_a = mint_auth0_token(sub="auth0|author_alpha")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = mint_auth0_token(sub="auth0|author_beta")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Author A creates two posts with pseudonym "Giant Elephant"
    post1_res = await community_client.post(
        "/api/v1/community/posts",
        headers=headers_a,
        json={"content": "First post by Author A", "author_pseudonym": "Giant Elephant"}
    )
    assert post1_res.status_code == 201
    post1_id = post1_res.json()["id"]

    post2_res = await community_client.post(
        "/api/v1/community/posts",
        headers=headers_a,
        json={"content": "Second post by Author A", "author_pseudonym": "Giant Elephant"}
    )
    assert post2_res.status_code == 201
    post2_id = post2_res.json()["id"]

    # 2. Author B creates a post with pseudonym "Wise Owl"
    post_b_res = await community_client.post(
        "/api/v1/community/posts",
        headers=headers_b,
        json={"content": "Post by Author B", "author_pseudonym": "Wise Owl"}
    )
    assert post_b_res.status_code == 201
    post_b_id = post_b_res.json()["id"]

    # 3. Author A comments on Author B's post with "Giant Elephant"
    comment_res = await community_client.post(
        f"/api/v1/community/posts/{post_b_id}/comments",
        headers=headers_a,
        json={"content": "Comment by Author A", "author_pseudonym": "Giant Elephant"}
    )
    assert comment_res.status_code == 201
    comment_id = comment_res.json()["id"]

    # 4. Author A updates their pseudonym to "Crazy Dog" via PUT /api/v1/community/pseudonyms/me
    update_res = await community_client.put(
        "/api/v1/community/pseudonyms/me",
        headers=headers_a,
        json={"pseudonym": "Crazy Dog"}
    )
    assert update_res.status_code == 200
    update_data = update_res.json()
    assert update_data["pseudonym"] == "Crazy Dog"
    assert "user_uuid" in update_data
    # Valid UUID
    uuid.UUID(update_data["user_uuid"])

    # 5. Fetch posts feed: Author A's older posts must now display "Crazy Dog", Author B remains "Wise Owl"
    feed_res = await community_client.get("/api/v1/community/posts")
    assert feed_res.status_code == 200
    posts_by_id = {p["id"]: p for p in feed_res.json()["items"]}

    assert posts_by_id[post1_id]["author_pseudonym"] == "Crazy Dog"
    assert posts_by_id[post2_id]["author_pseudonym"] == "Crazy Dog"
    assert posts_by_id[post_b_id]["author_pseudonym"] == "Wise Owl"

    # 6. Fetch comments: Author A's comment must now display "Crazy Dog"
    comments_res = await community_client.get(f"/api/v1/community/posts/{post_b_id}/comments")
    assert comments_res.status_code == 200
    comments_list = comments_res.json()
    assert len(comments_list) == 1
    assert comments_list[0]["id"] == comment_id
    assert comments_list[0]["author_pseudonym"] == "Crazy Dog"

    # 7. GET /api/v1/community/pseudonyms/me returns current profile
    me_res = await community_client.get("/api/v1/community/pseudonyms/me", headers=headers_a)
    assert me_res.status_code == 200
    assert me_res.json()["pseudonym"] == "Crazy Dog"
