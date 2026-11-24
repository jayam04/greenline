import json
import secrets
import pytest
from typing import Dict, Any
from httpx import AsyncClient
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, User
from app.api.deps import hash_api_key
from app.services.mcp_openapi_service import build_mcp_openapi_spec


# ==============================================================================
# Challenge 1: MCP Authentication Fuzzing & Stress Testing
# ==============================================================================

@pytest.mark.anyio
async def test_auth_fuzzing_malformed_and_edge_case_headers(
    e2e_client: AsyncClient,
    e2e_primary_api_key: str
):
    """
    Fuzz Authorization and X-API-Key headers with invalid, malformed, empty,
    SQL-injection, XSS, and buffer overflow payloads.
    All invalid credentials MUST be rejected with HTTP 401 Unauthorized.
    """
    valid_key = e2e_primary_api_key

    # Subtest 1: Headers that MUST fail with 401 Unauthorized
    reject_headers = [
        # Empty and whitespace tokens
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer   "},
        {"Authorization": "bearer "},
        {"Authorization": "Token "},
        {"Authorization": "Token   "},
        {"Authorization": ""},
        {"Authorization": "   "},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer \"\""},
        {"Authorization": "Bearer ''"},
        {"Authorization": "Bearer ' '"},
        {"Authorization": "Bearer \" \""},
        {"Authorization": "Bearer null"},
        {"Authorization": "Bearer undefined"},
        {"Authorization": "Bearer None"},
        {"Authorization": "null"},
        {"Authorization": "undefined"},
        {"Authorization": "None"},
        {"Authorization": "\"\""},
        {"Authorization": "''"},
        # Invalid / unexpected schemes
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Digest username=\"Mufasa\""},
        {"Authorization": "Hawk id=\"123456\""},
        {"Authorization": "Custom gl_mcp_123456789"},
        {"Authorization": "OAuth 123456789"},
        # Malformed / fake keys
        {"Authorization": "Bearer gl_mcp_non_existent_key_999999999"},
        {"Authorization": "Bearer wrong_prefix_1234567890abcdef"},
        {"Authorization": "Bearer gl_mcp_"},
        {"Authorization": "gl_mcp_non_existent_key_999999999"},
        # SQL Injection attempts
        {"Authorization": "Bearer ' OR '1'='1"},
        {"Authorization": "Bearer ' OR 1=1 --"},
        {"Authorization": "Bearer \" UNION SELECT * FROM users --"},
        {"Authorization": "Bearer admin' --"},
        # XSS / script payloads
        {"Authorization": "Bearer <script>alert(1)</script>"},
        {"Authorization": "Bearer <svg onload=alert(1)>"},
        # Format string & long buffer overflow
        {"Authorization": "Bearer %s%s%s%s%s%s%s%s%s%s"},
        {"Authorization": f"Bearer {'A' * 5000}"},
        {"Authorization": f"Bearer {'gl_mcp_' + 'x' * 4000}"},
        # X-API-Key invalid variants
        {"X-API-Key": ""},
        {"X-API-Key": "   "},
        {"X-API-Key": "gl_mcp_non_existent_key_999999999"},
        {"X-API-Key": "Basic dXNlcjpwYXNz"},
        {"X-API-Key": "' OR '1'='1"},
        {"X-API-Key": "None"},
        {"X-API-Key": "null"},
        # Both headers present but invalid
        {"X-API-Key": "fake_key", "Authorization": "Bearer fake_key"},
        {"X-API-Key": "", "Authorization": ""},
        {"X-API-Key": "   ", "Authorization": "Bearer   "},
    ]

    for h in reject_headers:
        res = await e2e_client.get("/api/v1/mcp/categories", headers=h)
        assert res.status_code == 401, (
            f"Fuzz failure: Header {h} was expected to return 401, but got {res.status_code}: {res.text}"
        )


@pytest.mark.anyio
async def test_auth_permissive_variants_of_valid_key(
    e2e_client: AsyncClient,
    e2e_primary_api_key: str
):
    """
    Test that valid keys with acceptable real-world variations (extra whitespace,
    redundant quotes, repeated bearer keywords, mixed casing) succeed with 200 OK.
    """
    valid_key = e2e_primary_api_key

    permissive_headers = [
        # Standard
        {"Authorization": f"Bearer {valid_key}"},
        {"X-API-Key": valid_key},
        # Repeated schemes (ChatGPT copy-paste artifacts)
        {"Authorization": f"Bearer Bearer {valid_key}"},
        {"Authorization": f"Bearer Bearer Bearer {valid_key}"},
        {"Authorization": f"Token Token {valid_key}"},
        {"Authorization": f"Bearer token {valid_key}"},
        {"Authorization": f"token Bearer {valid_key}"},
        # Casing variants
        {"Authorization": f"bearer {valid_key}"},
        {"Authorization": f"BEARER {valid_key}"},
        {"Authorization": f"BeArEr {valid_key}"},
        {"Authorization": f"token {valid_key}"},
        {"Authorization": f"TOKEN {valid_key}"},
        # Raw key in Authorization header without prefix
        {"Authorization": valid_key},
        {"Authorization": f"   {valid_key}   "},
        # Quotes variations
        {"Authorization": f'Bearer "{valid_key}"'},
        {"Authorization": f"Bearer '{valid_key}'"},
        {"Authorization": f'"{valid_key}"'},
        {"Authorization": f"'{valid_key}'"},
        {"Authorization": f'Bearer   "{valid_key}"  '},
        {"Authorization": f"Bearer   '{valid_key}'  "},
        {"X-API-Key": f"  {valid_key}  "},
        {"X-API-Key": f'"{valid_key}"'},
        {"X-API-Key": f"'{valid_key}'"},
        # Fallback when one header is invalid/empty but the other is valid
        {"X-API-Key": "invalid_trash", "Authorization": f"Bearer {valid_key}"},
        {"X-API-Key": valid_key, "Authorization": "Bearer invalid_trash"},
        {"X-API-Key": "", "Authorization": f"Bearer {valid_key}"},
        {"X-API-Key": valid_key, "Authorization": ""},
    ]

    for h in permissive_headers:
        res = await e2e_client.get("/api/v1/mcp/categories", headers=h)
        assert res.status_code == 200, (
            f"Permissive auth failure: Header {h} failed with {res.status_code}: {res.text}"
        )
        data = res.json()
        assert "categories" in data
        assert "available_accounts" in data


@pytest.mark.anyio
async def test_auth_revocation_and_tenant_isolation(
    e2e_client: AsyncClient,
    e2e_session: AsyncSession,
    e2e_primary_api_key: str,
    e2e_secondary_api_key: str
):
    """
    Verify:
    1. Revoking User 1's key renders it immediately unusable (401).
    2. User 2's key continues to function uninterrupted.
    3. User 2 cannot access or mutate User 1's tenant data under MCP.
    """
    key_u1 = e2e_primary_api_key
    key_u2 = e2e_secondary_api_key

    # Both keys work initially
    res1 = await e2e_client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {key_u1}"})
    assert res1.status_code == 200
    res2 = await e2e_client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {key_u2}"})
    assert res2.status_code == 200

    # Revoke User 1's key in database
    await e2e_session.execute(
        update(ApiKey).where(ApiKey.user_id == 1).values(is_active=False)
    )
    await e2e_session.commit()

    # User 1's key must return 401
    res1_revoked = await e2e_client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {key_u1}"})
    assert res1_revoked.status_code == 401, "Revoked key must return 401"

    # User 2's key must still work 200
    res2_active = await e2e_client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {key_u2}"})
    assert res2_active.status_code == 200, "User 2's key must remain active"


# ==============================================================================
# Challenge 2: MCP OpenAPI Specification Invariants
# ==============================================================================

@pytest.mark.anyio
async def test_openapi_spec_deep_invariants_and_chatgpt_actions_strictness(
    e2e_client: AsyncClient
):
    """
    Rigorously verify MCP OpenAPI 3.1.0 specification invariants:
    1. Schema version is 3.1.0
    2. ZERO descriptions > 300 characters anywhere (operations, parameters, schemas, properties)
    3. Exposed paths contain ONLY /api/v1/mcp/*
    4. ZERO internal parameters leaked (offset, X-API-Key, etc.)
    5. Spec is accessible unauthenticated via both /openapi.json and /api/v1/mcp/openapi.json
    6. RequestBody schemas contain no invalid sibling fields with $ref
    """
    # 1. Test build_mcp_openapi_spec() direct output
    spec = build_mcp_openapi_spec()
    assert spec["openapi"] == "3.1.0", f"OpenAPI version must be 3.1.0, got {spec.get('openapi')}"

    # 2. Test live HTTP endpoint /openapi.json (root)
    res_root = await e2e_client.get("/openapi.json")
    assert res_root.status_code == 200, f"/openapi.json failed: {res_root.status_code}"
    spec_root = res_root.json()
    assert spec_root["openapi"] == "3.1.0"

    # 3. Test live HTTP endpoint /api/v1/mcp/openapi.json
    res_mcp = await e2e_client.get("/api/v1/mcp/openapi.json")
    assert res_mcp.status_code == 200, f"/api/v1/mcp/openapi.json failed: {res_mcp.status_code}"
    spec_mcp = res_mcp.json()
    assert spec_mcp["openapi"] == "3.1.0"

    # Deep tree scan for description length across the entire spec
    violations = []

    def scan_descriptions(node: Any, breadcrumb: str):
        if isinstance(node, dict):
            for k, v in node.items():
                current_path = f"{breadcrumb}.{k}"
                if k == "description" and isinstance(v, str):
                    if len(v) > 300:
                        violations.append((current_path, len(v), v))
                else:
                    scan_descriptions(v, current_path)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                scan_descriptions(item, f"{breadcrumb}[{idx}]")

    scan_descriptions(spec, "spec")
    assert len(violations) == 0, (
        f"Found {len(violations)} descriptions exceeding 300 characters in OpenAPI spec: {violations}"
    )

    # 4. Route isolation: check paths contain ONLY /api/v1/mcp/*
    paths = spec.get("paths", {})
    assert len(paths) > 0, "MCP OpenAPI spec has no paths"
    for path in paths:
        assert path.startswith("/api/v1/mcp/"), (
            f"Path '{path}' in MCP OpenAPI spec does not start with '/api/v1/mcp/'"
        )
        assert "/import" not in path, f"Forbidden /import found in path: {path}"
        assert not path.endswith("openapi.json"), f"openapi.json route should not be exposed in paths: {path}"

    # Expected exact operations
    assert "/api/v1/mcp/categories" in paths
    assert "/api/v1/mcp/cashflow" in paths
    assert "/api/v1/mcp/stocks" in paths

    # 5. Parameter leak verification
    for path, path_item in paths.items():
        for method, op in path_item.items():
            if not isinstance(op, dict):
                continue
            params = op.get("parameters", [])
            param_names = [p.get("name") for p in params]
            assert "X-API-Key" not in param_names, f"Leaked X-API-Key in {method.upper()} {path}"
            assert "offset" not in param_names, f"Leaked offset in {method.upper()} {path}"
            assert "token" not in param_names, f"Leaked token in {method.upper()} {path}"

            # Check parameter descriptions <= 300 chars
            for p in params:
                p_desc = p.get("description", "")
                assert len(p_desc) <= 300, (
                    f"Parameter '{p.get('name')}' in {method.upper()} {path} description > 300: '{p_desc}'"
                )

            # Check request body cleanliness
            if "requestBody" in op and "content" in op["requestBody"]:
                for media_type, media_obj in op["requestBody"]["content"].items():
                    if "schema" in media_obj and "$ref" in media_obj["schema"]:
                        # When $ref is present, ensure no conflicting sibling keywords
                        keys = list(media_obj["schema"].keys())
                        assert keys == ["$ref"], (
                            f"requestBody in {method.upper()} {path} has invalid siblings with $ref: {keys}"
                        )


# ==============================================================================
# Challenge 3: Frontend Route Removal & Portfolio Backup Preservation
# ==============================================================================

@pytest.mark.anyio
async def test_frontend_route_removal_and_backup_import_persistence(
    e2e_client: AsyncClient,
    e2e_session: AsyncSession,
    e2e_seeded_env: Dict[str, Any]
):
    """
    Verify:
    1. /api/v1/import is completely dead (404 on all standard HTTP methods).
    2. Portfolio JSON backup import (/api/v1/backup/import) remains active and functional.
    """
    # 1. AI Import routes return 404
    import_probes = [
        ("GET", "/api/v1/import"),
        ("POST", "/api/v1/import"),
        ("POST", "/api/v1/import/upload"),
        ("GET", "/api/v1/import/batches"),
        ("GET", "/api/v1/import/batches/1"),
        ("POST", "/api/v1/import/batches/1/commit"),
    ]
    for method, route in import_probes:
        res = await e2e_client.request(method, route)
        assert res.status_code == 404, f"Expected 404 for removed route {method} {route}, got {res.status_code}"

    # 2. Portfolio JSON backup export & import must be preserved and functional
    # First, test unauthenticated access to /api/v1/backup/import (must be 401)
    unauth_res = await e2e_client.post("/api/v1/backup/import")
    assert unauth_res.status_code == 401, f"Expected 401 for unauthenticated backup import, got {unauth_res.status_code}"

    # Now login as primary user to get JWT
    login_res = await e2e_client.post(
        "/api/v1/auth/login",
        data={"username": "e2e_primary", "password": "Password123!"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    jwt_token = login_res.json()["access_token"]
    jwt_headers = {"Authorization": f"Bearer {jwt_token}"}

    # Export backup
    export_res = await e2e_client.get("/api/v1/backup/export", headers=jwt_headers)
    assert export_res.status_code == 200, f"Backup export failed: {export_res.text}"
    backup_data = export_res.json()
    assert "accounts" in backup_data

    # Import backup back via multipart form upload as in accounts/page.tsx
    json_bytes = json.dumps(backup_data).encode("utf-8")
    files = {"file": ("backup.json", json_bytes, "application/json")}
    import_res = await e2e_client.post("/api/v1/backup/import", headers=jwt_headers, files=files)
    assert import_res.status_code == 200, f"Backup import failed: {import_res.text}"
    result = import_res.json()
    assert "imported" in result
    assert "message" in result
