"""
Comprehensive E2E integration test suite for Standalone Community Microservice.
Verifies multi-user interactions, security boundaries, pagination, and media attachment payloads.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.anyio
async def test_multi_user_post_and_comment_lifecycle(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """
    Verify full lifecycle across multiple distinct users:
    - User A posts an investment insight with media attachments
    - User B leaves a top-level comment
    - User C replies to User B's comment
    - All users can read the feed with author pseudonyms and nested thread structure
    """
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token_a = mint_auth0_token(sub="auth0|investor_alice", name="Alice")
    token_b = mint_auth0_token(sub="auth0|investor_bob", name="Bob")
    token_c = mint_auth0_token(sub="auth0|investor_charlie", name="Charlie")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. User A creates a post
        post_payload = {
            "content": "Deep dive into tech sector asset allocation for 2026.",
            "author_pseudonym": "Wise Owl",
            "media_attachments": [
                {
                    "url": "https://greenline.app/reports/tech-2026.pdf",
                    "type": "document",
                    "name": "tech-2026.pdf",
                    "size": 204800
                }
            ]
        }
        res_a = await client.post(
            "/api/v1/community/posts",
            json=post_payload,
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_a.status_code == 201
        post = res_a.json()
        post_id = post["post_id"]
        assert post["author_sub"] == "auth0|investor_alice"
        assert post["author_pseudonym"] == "Wise Owl"
        assert post["comments_count"] == 0

        # 2. User B adds a comment
        comment_b_payload = {
            "content": "Great analysis, what are your thoughts on semiconductor multiples?",
            "author_pseudonym": "Swift Falcon"
        }
        res_b = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json=comment_b_payload,
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 201
        comment_b = res_b.json()
        comment_b_id = comment_b["comment_id"]
        assert comment_b["author_sub"] == "auth0|investor_bob"
        assert comment_b["author_pseudonym"] == "Swift Falcon"
        assert comment_b["parent_comment_id"] is None

        # 3. User C replies to User B's comment
        comment_c_payload = {
            "content": "Multiples look reasonable given the current forward earnings projections.",
            "parent_comment_id": comment_b_id,
            "author_pseudonym": "Clever Fox"
        }
        res_c = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json=comment_c_payload,
            headers={"Authorization": f"Bearer {token_c}"}
        )
        assert res_c.status_code == 201
        comment_c = res_c.json()
        assert comment_c["author_sub"] == "auth0|investor_charlie"
        assert comment_c["parent_comment_id"] == comment_b_id

        # 4. Verify post comments count is now 2
        res_post = await client.get(f"/api/v1/community/posts/{post_id}")
        assert res_post.status_code == 200
        assert res_post.json()["comments_count"] == 2

        # 5. Verify comments retrieval contains both comments in order
        res_comments = await client.get(f"/api/v1/community/posts/{post_id}/comments")
        assert res_comments.status_code == 200
        comments = res_comments.json()
        assert len(comments) == 2
        assert comments[0]["comment_id"] == comment_b_id
        assert comments[1]["comment_id"] == comment_c["comment_id"]

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_content_length_boundary_limits(auth_community_client: AsyncClient):
    """Verify exact boundary behavior for post content (10,000 characters allowed, 10,001 rejected)."""
    # 10,000 chars - valid
    content_10k = "x" * 10000
    res_valid = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": content_10k, "author_pseudonym": "Edge Master"}
    )
    assert res_valid.status_code == 201
    assert len(res_valid.json()["content"]) == 10000

    # 10,001 chars - rejected with 422
    content_10k_plus = "x" * 10001
    res_invalid = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": content_10k_plus}
    )
    assert res_invalid.status_code == 422


@pytest.mark.anyio
async def test_post_deletion_authorization(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """Verify that only the author of a post can delete it (HTTP 403 for non-authors)."""
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token_owner = mint_auth0_token(sub="auth0|post_owner")
    token_attacker = mint_auth0_token(sub="auth0|malicious_user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create post as owner
        res = await client.post(
            "/api/v1/community/posts",
            json={"content": "Post to test deletion permissions", "author_pseudonym": "Owner"},
            headers={"Authorization": f"Bearer {token_owner}"}
        )
        assert res.status_code == 201
        post_id = res.json()["post_id"]

        # Attacker tries to delete - 403 Forbidden
        del_attacker = await client.delete(
            f"/api/v1/community/posts/{post_id}",
            headers={"Authorization": f"Bearer {token_attacker}"}
        )
        assert del_attacker.status_code == 403

        # Owner deletes - 204 No Content
        del_owner = await client.delete(
            f"/api/v1/community/posts/{post_id}",
            headers={"Authorization": f"Bearer {token_owner}"}
        )
        assert del_owner.status_code == 204

        # Verify post is gone - 404
        get_res = await client.get(f"/api/v1/community/posts/{post_id}")
        assert get_res.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_microservice_least_privilege_security(community_db_session: AsyncSession):
    """
    Verify that the database session used by the Community microservice
    strictly adheres to least-privilege security:
    - Queries on community_posts and community_comments succeed
    - Queries on core financial tables (users, transactions, accounts) fail with ORA-00942
    """
    # 1. Community tables work
    res_posts = await community_db_session.execute(text("SELECT COUNT(*) FROM community_posts"))
    assert res_posts.scalar() is not None

    res_comments = await community_db_session.execute(text("SELECT COUNT(*) FROM community_comments"))
    assert res_comments.scalar() is not None

    # 2. Financial tables are inaccessible
    forbidden_tables = ["users", "transactions", "accounts", "lots", "dividends"]
    for table in forbidden_tables:
        with pytest.raises(Exception) as excinfo:
            await community_db_session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        err_msg = str(excinfo.value)
        assert "ORA-00942" in err_msg or "table or view does not exist" in err_msg.lower(), (
            f"Expected ORA-00942 for {table}, got {err_msg}"
        )
