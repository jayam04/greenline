"""
Tier 5 Adversarial Hardening and Stress Testing Suite for Greenline Community Microservice.
Empirically probes:
1. Non-deterministic sorting stress loop (50-100 repetitions on posts and comments with tie-breaking)
2. Authentication & Authorization boundaries (missing tokens, expired tokens, forged signatures, unauthorized deletions)
3. Input boundaries (boundary character lengths, empty/whitespace strings, unicode, emojis, SQL injection patterns, XSS patterns, cross-post parent comments)
4. Oracle Database isolation (verifies GREENLINE_COMMUNITY is strictly denied access to all 21 financial tables and zero DDL)
"""

import os
import time
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import oracledb
    ORACLEDB_AVAILABLE = True
except ImportError:
    oracledb = None
    ORACLEDB_AVAILABLE = False


# ==============================================================================
# PROBE 1: NON-DETERMINISTIC SORTING STRESS LOOPS
# ==============================================================================

@pytest.mark.anyio
async def test_probe_post_sorting_determinism_stress_loop(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """
    Stress-probe post feed sorting determinism:
    Create 10 posts in rapid succession, then query the feed 50 times in a loop.
    Verify that every query returns the EXACT same post order with zero jitter.
    Verify strict tie-breaking: created_at desc, id desc.
    """
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token = mint_auth0_token(sub="auth0|stress_tester_01", name="Stress Tester")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        # Create 10 posts rapidly
        created_post_ids = []
        for i in range(10):
            res = await client.post(
                "/api/v1/community/posts",
                json={"content": f"Deterministic stress test post {i + 1}", "author_pseudonym": "DeterminismProbe"}
            )
            assert res.status_code == 201
            created_post_ids.append(res.json()["post_id"])

        assert len(created_post_ids) == 10

        # Query 50 times in a loop for latest sort
        first_order = None
        for iteration in range(50):
            res = await client.get("/api/v1/community/posts?limit=10&sort=latest")
            assert res.status_code == 200
            data = res.json()
            returned_ids = [p["post_id"] for p in data["items"]]

            if first_order is None:
                first_order = returned_ids
                # Expect newest post first (reverse of creation order)
                assert returned_ids == list(reversed(created_post_ids)), (
                    f"Expected descending order {list(reversed(created_post_ids))}, got {returned_ids}"
                )
            else:
                assert returned_ids == first_order, (
                    f"Non-deterministic sorting detected at iteration {iteration}! Expected {first_order}, got {returned_ids}"
                )

        # Query 30 times in a loop for oldest sort
        oldest_first_order = None
        for iteration in range(30):
            res = await client.get("/api/v1/community/posts?limit=10&sort=oldest")
            assert res.status_code == 200
            returned_ids = [p["post_id"] for p in res.json()["items"]]

            if oldest_first_order is None:
                oldest_first_order = returned_ids
                assert returned_ids == created_post_ids, (
                    f"Expected ascending order {created_post_ids}, got {returned_ids}"
                )
            else:
                assert returned_ids == oldest_first_order, (
                    f"Non-deterministic oldest sorting detected at iteration {iteration}!"
                )

        # Pagination consistency test: Page 1 (limit=5, offset=0) and Page 2 (limit=5, offset=5)
        p1_res = await client.get("/api/v1/community/posts?limit=5&offset=0&sort=latest")
        p2_res = await client.get("/api/v1/community/posts?limit=5&offset=5&sort=latest")
        p1_ids = [p["post_id"] for p in p1_res.json()["items"]]
        p2_ids = [p["post_id"] for p in p2_res.json()["items"]]

        assert len(p1_ids) == 5
        assert len(p2_ids) == 5
        assert set(p1_ids).isdisjoint(set(p2_ids)), "Pages 1 and 2 must have zero overlap"
        assert p1_ids + p2_ids == first_order, "Concatenated pages must exactly match unpaginated feed"

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_probe_comment_sorting_determinism_stress_loop(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """
    Stress-probe comment retrieval determinism:
    Create 1 post with 10 comments, then retrieve comments 50 times in a loop.
    Verify that every query returns identical chronological ordering with zero jitter.
    """
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token = mint_auth0_token(sub="auth0|stress_tester_02", name="Comment Tester")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        # Create post
        p_res = await client.post(
            "/api/v1/community/posts",
            json={"content": "Parent post for comment stress loop"}
        )
        assert p_res.status_code == 201
        post_id = p_res.json()["post_id"]

        # Create 10 comments
        created_comment_ids = []
        for i in range(10):
            c_res = await client.post(
                f"/api/v1/community/posts/{post_id}/comments",
                json={"content": f"Comment {i + 1} on post {post_id}"}
            )
            assert c_res.status_code == 201
            created_comment_ids.append(c_res.json()["comment_id"])

        # Loop 50 times querying comments
        first_order = None
        for iteration in range(50):
            res = await client.get(f"/api/v1/community/posts/{post_id}/comments?limit=50")
            assert res.status_code == 200
            returned_ids = [c["comment_id"] for c in res.json()]

            if first_order is None:
                first_order = returned_ids
                assert returned_ids == created_comment_ids, (
                    f"Expected chronological order {created_comment_ids}, got {returned_ids}"
                )
            else:
                assert returned_ids == first_order, (
                    f"Non-deterministic comment sorting detected at iteration {iteration}!"
                )

    app.dependency_overrides.clear()


# ==============================================================================
# PROBE 2: AUTHENTICATION & AUTHORIZATION BOUNDARIES
# ==============================================================================

@pytest.mark.anyio
async def test_probe_authentication_and_authorization_boundaries(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """
    Empirically probe security and permission boundaries:
    - Unauthenticated post and comment creation -> 401
    - Forged / invalid / expired JWT tokens -> 401
    - Missing sub claim in JWT -> 401
    - Unauthorized post deletion by non-owner -> 403
    - Unauthenticated post deletion -> 401
    - Deletion and comment on nonexistent post -> 404
    """
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token_owner = mint_auth0_token(sub="auth0|legit_owner", name="Owner")
    token_attacker = mint_auth0_token(sub="auth0|attacker_99", name="Attacker")
    token_expired = mint_auth0_token(sub="auth0|expired_user", exp=int(time.time()) - 3600)
    token_no_sub = mint_auth0_token(sub="")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Post creation without auth header -> 401
        res = await client.post("/api/v1/community/posts", json={"content": "Sneaky unauth post"})
        assert res.status_code == 401

        # 2. Post creation with malformed token -> 401
        res = await client.post(
            "/api/v1/community/posts",
            json={"content": "Malformed token post"},
            headers={"Authorization": "Bearer not.a.valid.jwt.token"}
        )
        assert res.status_code == 401

        # 3. Post creation with expired token -> 401
        res = await client.post(
            "/api/v1/community/posts",
            json={"content": "Expired token post"},
            headers={"Authorization": f"Bearer {token_expired}"}
        )
        assert res.status_code == 401

        # 4. Post creation with empty sub -> 401
        res = await client.post(
            "/api/v1/community/posts",
            json={"content": "No sub token post"},
            headers={"Authorization": f"Bearer {token_no_sub}"}
        )
        assert res.status_code == 401

        # 5. Create valid post as owner
        res_post = await client.post(
            "/api/v1/community/posts",
            json={"content": "Legit post by owner", "author_pseudonym": "Owner"},
            headers={"Authorization": f"Bearer {token_owner}"}
        )
        assert res_post.status_code == 201
        post_id = res_post.json()["post_id"]

        # 6. Comment creation without token -> 401
        res_comment = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json={"content": "Unauth comment"}
        )
        assert res_comment.status_code == 401

        # 7. Comment creation with expired token -> 401
        res_comment_exp = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json={"content": "Expired comment"},
            headers={"Authorization": f"Bearer {token_expired}"}
        )
        assert res_comment_exp.status_code == 401

        # 8. Unauthenticated deletion -> 401
        res_del_unauth = await client.delete(f"/api/v1/community/posts/{post_id}")
        assert res_del_unauth.status_code == 401

        # 9. Attacker attempts to delete owner's post -> 403 Forbidden
        res_del_attacker = await client.delete(
            f"/api/v1/community/posts/{post_id}",
            headers={"Authorization": f"Bearer {token_attacker}"}
        )
        assert res_del_attacker.status_code == 403
        assert "not authorized" in res_del_attacker.json()["detail"].lower()

        # 10. Deletion of non-existent post as owner -> 404
        res_del_404 = await client.delete(
            "/api/v1/community/posts/999999",
            headers={"Authorization": f"Bearer {token_owner}"}
        )
        assert res_del_404.status_code == 404

        # 11. Owner successfully deletes own post -> 204
        res_del_ok = await client.delete(
            f"/api/v1/community/posts/{post_id}",
            headers={"Authorization": f"Bearer {token_owner}"}
        )
        assert res_del_ok.status_code == 204

        # 12. Post is verified gone -> 404
        res_get_gone = await client.get(f"/api/v1/community/posts/{post_id}")
        assert res_get_gone.status_code == 404

    app.dependency_overrides.clear()


# ==============================================================================
# PROBE 3: INPUT BOUNDARIES & RESISTANCE
# ==============================================================================

@pytest.mark.anyio
async def test_probe_input_boundaries_and_sanitization_resistance(
    community_db_session: AsyncSession,
    mint_auth0_token
):
    """
    Probe extreme and adversarial inputs:
    - Empty and whitespace-only text -> 422
    - Exact boundary lengths: 10,000 post chars (201), 10,001 post chars (422)
    - Comment exact boundary: 5,000 comment chars (201), 5,001 comment chars (422)
    - Unicode, emojis, multi-byte UTF-8, zero-width chars, RTL strings
    - SQL injection strings and XSS script tags safely stored as literals
    - Cross-post parent comment linkage denial (referencing comment on another post -> 404)
    """
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield community_db_session

    app.dependency_overrides[get_db] = _override_get_db

    token = mint_auth0_token(sub="auth0|input_probe_user")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        # 1. Empty string post -> 422
        r = await client.post("/api/v1/community/posts", json={"content": ""})
        assert r.status_code == 422

        # 2. Whitespace-only post -> 422
        r = await client.post("/api/v1/community/posts", json={"content": "   \n\t  \r  "})
        assert r.status_code == 422

        # 3. Exact 10,000 character post -> 201
        large_content = "A" * 10000
        r = await client.post("/api/v1/community/posts", json={"content": large_content})
        assert r.status_code == 201
        assert len(r.json()["content"]) == 10000
        post_id = r.json()["post_id"]

        # 4. 10,001 character post -> 422
        r = await client.post("/api/v1/community/posts", json={"content": "A" * 10001})
        assert r.status_code == 422

        # 5. Unicode, Emojis, RTL Hebrew/Arabic, Zero-Width Spaces
        complex_content = (
            "🚀 Portfolio up 42.5%! 💎🙌\n"
            "Arabic: تم تسجيل الأرباح بنجاح\n"
            "Hebrew: תיק השקעות ירוק\n"
            "Zero-width: a\u200b\u200cb\n"
            "Math: ∑_{i=1}^n x_i ≈ ∫_0^∞ e^{-x} dx"
        )
        r = await client.post(
            "/api/v1/community/posts",
            json={"content": complex_content, "author_pseudonym": "UnicodeWizard"}
        )
        assert r.status_code == 201
        unicode_post_id = r.json()["post_id"]

        # Fetch and verify verbatim preservation
        r_get = await client.get(f"/api/v1/community/posts/{unicode_post_id}")
        assert r_get.status_code == 200
        assert r_get.json()["content"] == complex_content

        # 6. SQL Injection attempts stored safely as verbatim text
        sqli_content = "' OR '1'='1'; DROP TABLE community_posts; -- /* injected */"
        r_sqli = await client.post("/api/v1/community/posts", json={"content": sqli_content})
        assert r_sqli.status_code == 201
        sqli_id = r_sqli.json()["post_id"]

        r_sqli_get = await client.get(f"/api/v1/community/posts/{sqli_id}")
        assert r_sqli_get.status_code == 200
        assert r_sqli_get.json()["content"] == sqli_content

        # 7. XSS payloads stored safely as verbatim text
        xss_content = "<script>alert('xss');</script><img src=x onerror=alert(1)>"
        r_xss = await client.post("/api/v1/community/posts", json={"content": xss_content})
        assert r_xss.status_code == 201
        xss_id = r_xss.json()["post_id"]

        r_xss_get = await client.get(f"/api/v1/community/posts/{xss_id}")
        assert r_xss_get.status_code == 200
        assert r_xss_get.json()["content"] == xss_content

        # 8. Comment boundary: empty and whitespace -> 422
        r = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"content": ""})
        assert r.status_code == 422

        r = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"content": " \t \n "})
        assert r.status_code == 422

        # 9. Comment boundary: 5,000 chars (201), 5,001 chars (422)
        r = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"content": "C" * 5000})
        assert r.status_code == 201
        valid_comment_id = r.json()["comment_id"]

        r = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"content": "C" * 5001})
        assert r.status_code == 422

        # 10. Comment on nonexistent post -> 404
        r = await client.post("/api/v1/community/posts/999999/comments", json={"content": "Orphan comment"})
        assert r.status_code == 404

        # 11. Comment with nonexistent parent_comment_id -> 404
        r = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json={"content": "Bad parent", "parent_comment_id": 888888}
        )
        assert r.status_code == 404

        # 12. Cross-post parent comment rejection:
        # Create a second post, attempt to create comment on post 2 referencing comment on post 1
        r_post2 = await client.post("/api/v1/community/posts", json={"content": "Post 2"})
        post2_id = r_post2.json()["post_id"]

        r_cross = await client.post(
            f"/api/v1/community/posts/{post2_id}/comments",
            json={"content": "Cross-post reply attempt", "parent_comment_id": valid_comment_id}
        )
        assert r_cross.status_code == 404, "Must reject parent comment belonging to a different post"

    app.dependency_overrides.clear()


# ==============================================================================
# PROBE 4: ORACLE DATABASE ISOLATION & LEAST PRIVILEGE
# ==============================================================================

@pytest.mark.anyio
async def test_probe_oracle_db_isolation_and_least_privilege(community_db_session: AsyncSession):
    """
    Directly verify that the database session used by the Community microservice
    cannot access ANY of the 21 core financial tables or perform DDL operations.
    All attempts MUST raise ORA-00942 (table does not exist) or ORA-01031 (insufficient privileges).
    """
    ALL_21_CORE_FINANCIAL_TABLES = [
        "users",
        "accounts",
        "assets",
        "transactions",
        "lots",
        "lot_sales",
        "price_history",
        "dividends",
        "expected_dividends",
        "cash_flows",
        "cashflow_transactions",
        "cashflow_payments",
        "cashflow_items",
        "categories",
        "networth_snapshots",
        "networth_by_asset_class",
        "xirr_cache",
        "benchmarks",
        "app_settings",
        "api_keys",
        "schema_migrations",
    ]

    # Verify every single core financial table is blocked
    for table_name in ALL_21_CORE_FINANCIAL_TABLES:
        with pytest.raises(Exception) as excinfo:
            await community_db_session.execute(text(f"SELECT * FROM {table_name} WHERE ROWNUM <= 1"))
        err_msg = str(excinfo.value)
        assert any(code in err_msg for code in ["ORA-00942", "table or view does not exist"]), (
            f"Expected ORA-00942 table denial for {table_name}, but got: {err_msg}"
        )

    # Verify DDL statements are blocked (ORA-01031)
    ddl_statements = [
        "CREATE TABLE community_adversarial_probe_table (id NUMBER)",
        "DROP TABLE community_posts",
        "ALTER TABLE community_posts ADD (adversarial_col VARCHAR2(100))",
    ]
    for ddl in ddl_statements:
        with pytest.raises(Exception) as excinfo:
            await community_db_session.execute(text(ddl))
        err_msg = str(excinfo.value)
        assert any(code in err_msg for code in ["ORA-01031", "ORA-00942", "insufficient privileges"]), (
            f"Expected DDL denial (ORA-01031) for '{ddl}', got: {err_msg}"
        )
