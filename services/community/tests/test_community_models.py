import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.anyio
async def test_community_models_cascade_delete(
    auth_community_client,
    community_client,
    community_db_session: AsyncSession
):
    """Verify that deleting a post cascades to all its comments and nested replies."""
    from app.db.models import CommunityPost, CommunityComment

    # 1. Create a post with comments
    p_res = await auth_community_client.post(
        "/api/v1/community/posts",
        json={"content": "Post to cascade delete"}
    )
    post_id = p_res.json()["post_id"]

    c1_res = await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"content": "Top comment"}
    )
    c1_id = c1_res.json()["comment_id"]

    await auth_community_client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"content": "Nested comment", "parent_comment_id": c1_id}
    )

    # Verify rows in DB
    p_stmt = select(CommunityPost).where(CommunityPost.id == post_id)
    post_db = (await community_db_session.execute(p_stmt)).scalars().first()
    assert post_db is not None

    c_stmt = select(CommunityComment).where(CommunityComment.post_id == post_id)
    comments_db = (await community_db_session.execute(c_stmt)).scalars().all()
    assert len(comments_db) == 2

    # Delete the post
    await community_db_session.delete(post_db)
    await community_db_session.commit()

    # Verify post and comments are completely gone
    post_check = (await community_db_session.execute(p_stmt)).scalars().first()
    assert post_check is None

    comments_check = (await community_db_session.execute(c_stmt)).scalars().all()
    assert len(comments_check) == 0


def test_community_models_comments_relationship_order_by_tie_breaker():
    """Verify that CommunityPost.comments relationship specifies both created_at.asc() and id.asc() tie-breaker."""
    from app.db.models import CommunityPost

    order_by_clauses = CommunityPost.comments.property.order_by
    assert len(order_by_clauses) == 2, f"Expected 2 order_by clauses, got {len(order_by_clauses)}"
    # Verify column names in order_by expressions
    col_names = [expr.element.name for expr in order_by_clauses]
    assert col_names == ["created_at", "id"]

