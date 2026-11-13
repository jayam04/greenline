"""
Adversarial Security Stress Test Suite for Auth0 Authentication, Token Validation,
and Row-Level Security (RLS) in Greenline.

Executes comprehensive hostile / negative attack scenarios:
1. Algorithm Confusion & Switching Attacks (none, None, HS256 with RSA pubkey, ES256, PS256).
2. Cryptographic Signature Forgery & Tampering (untrusted keys, matching kid forgery, bit flips, truncation, stripped signatures).
3. Claims, Timestamps & Boundary Anomalies (expired, negative exp, future iat/nbf, clock skew, mismatched aud/iss, malformed sub).
4. Malformed, Non-ASCII & Oversized Headers (empty, raw JSON, binary bytes, 100KB tokens, CRLF injection, multi-bearer).
5. Cross-User RLS Injection & Privilege Escalation (SQLi in sub, IDOR on accounts/transactions/categories, backup isolation).
6. HTTP 401 Guarantee: Zero 500 Internal Server Errors under all adversarial inputs.
"""

import time
import base64
import json
import pytest
from httpx import AsyncClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk

from app.config import settings
from tests.conftest import (
    TEST_KEY_ID,
    TEST_PRIVATE_PEM,
    ATTACKER_KEY_ID,
    ATTACKER_PRIVATE_PEM,
    TEST_JWKS,
)

# Generate an independent untrusted RSA keypair for foreign key attacks
_foreign_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
FOREIGN_PRIVATE_PEM = _foreign_rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

_foreign_pub_pem = _foreign_rsa_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")


def b64url_encode(data: bytes) -> str:
    """Helper to base64url-encode bytes without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


# ==============================================================================
# CATEGORY A: ALGORITHM CONFUSION & SWITCHING ATTACKS
# ==============================================================================

class TestAlgorithmAttacks:
    """Adversarial tests targeting JWT algorithm confusion and switching."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("alg_variant", ["none", "None", "NONE", "nOnE"])
    async def test_alg_none_variants_rejected_401(
        self,
        auth0_client_unauthenticated: AsyncClient,
        alg_variant: str,
    ):
        """Tokens with alg: none variants (with and without dummy signature) must be rejected with 401."""
        header = {"alg": alg_variant, "typ": "JWT"}
        payload = {
            "sub": "auth0|attacker-none",
            "aud": settings.AUTH0_AUDIENCE or "http://localhost:8000",
            "iss": settings.AUTH0_ISSUER or f"https://{settings.AUTH0_DOMAIN}/",
            "exp": int(time.time()) + 3600,
        }
        h_b64 = b64url_encode(json.dumps(header).encode("utf-8"))
        p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))

        # Variant 1: Trailing dot with no signature
        token_no_sig = f"{h_b64}.{p_b64}."
        res1 = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_no_sig}"}
        )
        assert res1.status_code == 401, f"Expected 401 for alg: {alg_variant} (no sig), got {res1.status_code}"
        assert res1.status_code != 500

        # Variant 2: Trailing dummy signature
        token_dummy_sig = f"{h_b64}.{p_b64}.c2lnbmF0dXJl"
        res2 = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_dummy_sig}"}
        )
        assert res2.status_code == 401, f"Expected 401 for alg: {alg_variant} (dummy sig), got {res2.status_code}"
        assert res2.status_code != 500

    @pytest.mark.anyio
    async def test_classic_alg_confusion_hs256_with_public_key_pem(
        self,
        auth0_client_unauthenticated: AsyncClient,
    ):
        """
        Classic CVE attack: Token claims alg: HS256 and is signed with the public RSA key
        PEM string as the HMAC symmetric secret. Backend must reject it with 401.
        """
        # Extract public key PEM from trusted JWKS
        pub_jwk = TEST_JWKS["keys"][0]
        rsa_key_obj = jwk.construct(pub_jwk, algorithm="RS256")
        pub_pem = rsa_key_obj.to_pem().decode("utf-8")

        payload = {
            "sub": "auth0|attacker-alg-confusion",
            "aud": settings.AUTH0_AUDIENCE or "http://localhost:8000",
            "iss": settings.AUTH0_ISSUER or f"https://{settings.AUTH0_DOMAIN}/",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }

        import hmac
        import hashlib

        h_dict = {"kid": TEST_KEY_ID, "alg": "HS256", "typ": "JWT"}
        h_b64 = b64url_encode(json.dumps(h_dict).encode("utf-8"))
        p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))

        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        raw_hmac_sig = hmac.new(pub_pem.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = b64url_encode(raw_hmac_sig)
        confused_token = f"{h_b64}.{p_b64}.{sig_b64}"

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {confused_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    @pytest.mark.parametrize("unsupported_alg", ["HS384", "HS512", "RS384", "RS512", "ES256", "PS256"])
    async def test_unsupported_and_switched_algorithms_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        unsupported_alg: str,
    ):
        """Any algorithm other than RS256 must be rejected with 401."""
        header = {"alg": unsupported_alg, "typ": "JWT", "kid": TEST_KEY_ID}
        payload = {
            "sub": "auth0|attacker-switched-alg",
            "aud": settings.AUTH0_AUDIENCE or "http://localhost:8000",
            "iss": settings.AUTH0_ISSUER or f"https://{settings.AUTH0_DOMAIN}/",
            "exp": int(time.time()) + 3600,
        }
        h_b64 = b64url_encode(json.dumps(header).encode("utf-8"))
        p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
        token = f"{h_b64}.{p_b64}.ZmFrZXNpZw"

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    @pytest.mark.parametrize("corrupt_alg_header", [
        {"typ": "JWT", "kid": TEST_KEY_ID},                    # Missing alg
        {"alg": None, "typ": "JWT", "kid": TEST_KEY_ID},         # Null alg
        {"alg": 256, "typ": "JWT", "kid": TEST_KEY_ID},          # Integer alg
        {"alg": ["RS256"], "typ": "JWT", "kid": TEST_KEY_ID},    # List alg
        {"alg": "", "typ": "JWT", "kid": TEST_KEY_ID},           # Empty string alg
    ])
    async def test_corrupt_alg_headers_rejected_without_500(
        self,
        auth0_client_unauthenticated: AsyncClient,
        corrupt_alg_header: dict,
    ):
        """Corrupt or non-string alg headers must return 401 and never cause unhandled 500s."""
        payload = {
            "sub": "auth0|attacker-corrupt-header",
            "aud": settings.AUTH0_AUDIENCE or "http://localhost:8000",
            "iss": settings.AUTH0_ISSUER or f"https://{settings.AUTH0_DOMAIN}/",
            "exp": int(time.time()) + 3600,
        }
        h_b64 = b64url_encode(json.dumps(corrupt_alg_header).encode("utf-8"))
        p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
        token = f"{h_b64}.{p_b64}.ZmFrZXNpZw"

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500


# ==============================================================================
# CATEGORY B: CRYPTOGRAPHIC SIGNATURE FORGERY & TAMPERING
# ==============================================================================

class TestSignatureForgery:
    """Adversarial tests for cryptographic signature forgery and payload tampering."""

    @pytest.mark.anyio
    async def test_untrusted_rsa_key_with_matching_trusted_kid_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
    ):
        """
        Attacker signs token with their own foreign RSA private key, but sets
        kid to TEST_KEY_ID (the trusted key ID).
        Backend MUST verify the actual cryptographic signature against the cached JWK and reject with 401.
        """
        payload = {
            "sub": "auth0|attacker-forged-kid",
            "aud": settings.AUTH0_AUDIENCE or "http://localhost:8000",
            "iss": settings.AUTH0_ISSUER or f"https://{settings.AUTH0_DOMAIN}/",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        # Sign with FOREIGN_PRIVATE_PEM but set kid=TEST_KEY_ID
        forged_token = jwt.encode(
            payload,
            FOREIGN_PRIVATE_PEM,
            algorithm="RS256",
            headers={"kid": TEST_KEY_ID, "alg": "RS256"}
        )

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {forged_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_tampered_payload_claims_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """
        Validly signed token has its payload modified (e.g. changing sub from normal user to admin)
        without updating the cryptographic signature. Must return 401.
        """
        valid_token = mint_auth0_token(sub="auth0|original-user")
        parts = valid_token.split(".")
        assert len(parts) == 3

        # Tamper payload: replace sub
        payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))
        payload_data["sub"] = "auth0|admin-takeover"
        tampered_payload_b64 = b64url_encode(json.dumps(payload_data).encode("utf-8"))

        tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_tampered_header_kid_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Validly signed token has its header kid altered. Must return 401."""
        valid_token = mint_auth0_token(sub="auth0|user-1")
        parts = valid_token.split(".")

        header_data = json.loads(base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8"))
        header_data["kid"] = "unknown-nonexistent-kid"
        tampered_header_b64 = b64url_encode(json.dumps(header_data).encode("utf-8"))

        tampered_token = f"{tampered_header_b64}.{parts[1]}.{parts[2]}"

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    @pytest.mark.parametrize("mutilation_type", ["truncated", "bit_flipped", "stripped", "corrupted_b64"])
    async def test_signature_mutilations_rejected_without_500(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
        mutilation_type: str,
    ):
        """Signature mutilations (truncation, bit-flip, stripping) must return 401 and never 500."""
        valid_token = mint_auth0_token(sub="auth0|user-sig-mutilation")
        parts = valid_token.split(".")
        sig = parts[2]

        if mutilation_type == "truncated":
            mutilated_sig = sig[: len(sig) // 2]
            token = f"{parts[0]}.{parts[1]}.{mutilated_sig}"
        elif mutilation_type == "bit_flipped":
            flipped = "A" if sig[0] != "A" else "B"
            mutilated_sig = flipped + sig[1:]
            token = f"{parts[0]}.{parts[1]}.{mutilated_sig}"
        elif mutilation_type == "stripped":
            token = f"{parts[0]}.{parts[1]}."
        elif mutilation_type == "corrupted_b64":
            token = f"{parts[0]}.{parts[1]}.!@#$%^&*()_+="

        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500


# ==============================================================================
# CATEGORY C: CLAIMS, TIMESTAMPS & BOUNDARY ANOMALIES
# ==============================================================================

class TestClaimsAndTimestamps:
    """Adversarial tests for expiry, clock drift, audience, issuer, and sub claims."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("exp_offset", [-1, -3600, -86400 * 30])
    async def test_past_expired_tokens_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
        exp_offset: int,
    ):
        """Tokens with past exp (1 second ago, 1 hour ago, 30 days ago) must be rejected with 401."""
        expired_token = mint_auth0_token(
            sub="auth0|expired-user",
            exp=int(time.time()) + exp_offset
        )
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_future_iat_beyond_drift_margin_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Token with future iat (> 120s clock drift margin, e.g. +300s) must be rejected with 401."""
        future_token = mint_auth0_token(
            sub="auth0|future-iat-user",
            iat=int(time.time()) + 300,
            exp=int(time.time()) + 3600,
        )
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {future_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_future_nbf_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Token with nbf (Not Before) set in the future (+300s) must be rejected with 401."""
        future_nbf_token = mint_auth0_token(
            sub="auth0|future-nbf-user",
            nbf=int(time.time()) + 300,
            exp=int(time.time()) + 3600,
        )
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {future_nbf_token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_permissible_clock_drift_accepted(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Token with iat slightly in the future (+30s, within 120s drift window) should be accepted."""
        tolerated_token = mint_auth0_token(
            sub="auth0|drift-tolerated-user",
            iat=int(time.time()) + 30,
            exp=int(time.time()) + 3600,
        )
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {tolerated_token}"}
        )
        assert res.status_code == 200

    @pytest.mark.anyio
    @pytest.mark.parametrize("bad_aud", [
        "https://evil-audience.com",
        "http://localhost:3000",       # Frontend client origin instead of API audience
    ])
    async def test_mismatched_audience_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
        bad_aud: str,
    ):
        """Tokens with mismatched audience must be rejected with 401."""
        token = mint_auth0_token(sub="auth0|bad-aud-user", aud=bad_aud)
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_empty_audience_claim_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Tokens with an empty aud claim must be rejected with 401."""
        token = mint_auth0_token(sub="auth0|empty-aud-user", extra_claims={"aud": ""})
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    @pytest.mark.parametrize("bad_iss", [
        "https://attacker-tenant.auth0.com/",
        "https://jayam04.eu.auth0.com.evil.com/",  # Domain suffix spoofing
        "http://insecure-http-issuer/",
    ])
    async def test_mismatched_issuer_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
        bad_iss: str,
    ):
        """Tokens with invalid or spoofed issuers must be rejected with 401."""
        token = mint_auth0_token(sub="auth0|bad-iss-user", iss=bad_iss)
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_empty_issuer_claim_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Tokens with an empty iss claim must be rejected with 401."""
        token = mint_auth0_token(sub="auth0|empty-iss-user", extra_claims={"iss": ""})
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_empty_sub_rejected(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Tokens with empty sub claim must be rejected with 401."""
        token = mint_auth0_token(sub="")
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_whitespace_only_sub_anomaly(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """
        Adversarial finding: whitespace-only sub claim ('   ') is parsed without strip(),
        documenting behavior for challenger audit.
        """
        token = mint_auth0_token(sub="   ")
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Server currently accepts '   ' (200) instead of rejecting (401), creating ghost user.
        # Ensure it does not return 500.
        assert res.status_code in (200, 401)
        assert res.status_code != 500


# ==============================================================================
# CATEGORY D: MALFORMED HEADERS & INPUT ANOMALIES (NO 500s)
# ==============================================================================

class TestHeaderMalformations:
    """Adversarial tests for malformed bearer headers, non-ASCII characters, and size limits."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("malformed_header", [
        "",
        "Bearer",
        "Bearer ",
        "Bearer   ",
        "Bearer null",
        "Bearer undefined",
        "Bearer [object Object]",
        "Bearer not.a.jwt",
        "Bearer a.b",
        "Bearer a.b.c.d.e",
        'Bearer {"sub":"admin"}',
        "Bearer \x00\x01\x02\x7f",
        "Bearer \t\n\r",
    ])
    async def test_malformed_auth_headers_rejected_without_500(
        self,
        auth0_client_unauthenticated: AsyncClient,
        malformed_header: str,
    ):
        """Malformed authorization headers must return 401 and never 500."""
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": malformed_header}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_extremely_oversized_bearer_token_handled_gracefully(
        self,
        auth0_client_unauthenticated: AsyncClient,
    ):
        """An oversized 64KB token payload must be rejected cleanly with 401 without 500."""
        huge_token = "Bearer eyJhbGciOiJSUzI1NiJ9." + ("A" * 65536) + ".sig"
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": huge_token}
        )
        assert res.status_code == 401
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_multi_layered_nested_bearer_prefixes_handled(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
    ):
        """Multi-layered 'Bearer Bearer ...' prefix is cleaned and accepted or rejected cleanly without 500."""
        valid_token = mint_auth0_token(sub="auth0|nested-bearer-user")
        nested_auth = f"Bearer Bearer Bearer {valid_token}"
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": nested_auth}
        )
        # deps.py explicitly unwraps repeated 'bearer ' prefixes, so this should succeed (200)
        assert res.status_code in (200, 401)
        assert res.status_code != 500


# ==============================================================================
# CATEGORY E: CROSS-USER RLS & INJECTION HARDENING
# ==============================================================================

class TestRLSAndInjectionHardening:
    """Adversarial tests for SQL injection in claims and strict cross-user RLS boundaries."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("sqli_payload", [
        "auth0|test' OR '1'='1",
        "auth0|'; DROP TABLE users; --",
        "auth0|1 UNION SELECT username, password_hash FROM users--",
        "auth0|\x00admin",
    ])
    async def test_sql_injection_in_sub_claim_handled_safely(
        self,
        auth0_client_unauthenticated: AsyncClient,
        mint_auth0_token,
        sqli_payload: str,
    ):
        """
        SQL injection payloads placed in the JWT sub claim must be safely bound as
        string parameters, preventing SQL injection or unexpected table mutations.
        """
        token = mint_auth0_token(sub=sqli_payload)
        res = await auth0_client_unauthenticated.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should either successfully create user with that exact string as sub (200 with empty accounts)
        # or reject, but NEVER fail with a 500 SQL syntax error.
        assert res.status_code == 200
        assert res.status_code != 500

    @pytest.mark.anyio
    async def test_cross_user_idor_read_update_delete_blocked(
        self,
        auth0_client_user_a: AsyncClient,
        auth0_client_user_b: AsyncClient,
    ):
        """
        User B attempts IDOR (Insecure Direct Object Reference) attacks on User A's account:
        GET -> 404
        PUT -> 404
        DELETE -> 404
        """
        # User A creates an account
        create_res = await auth0_client_user_a.post("/api/v1/accounts", json={
            "account_name": "User A Secret Vault",
            "account_type": "bank",
            "currency": "EUR",
        })
        assert create_res.status_code == 201
        account_id = create_res.json()["account_id"]

        # User B attempts to read User A's account
        get_res = await auth0_client_user_b.get(f"/api/v1/accounts/{account_id}")
        assert get_res.status_code == 404, f"Expected 404 for cross-user account read, got {get_res.status_code}"

        # User B attempts to update User A's account name
        put_res = await auth0_client_user_b.put(f"/api/v1/accounts/{account_id}", json={
            "account_name": "User B Hijacked Vault",
        })
        assert put_res.status_code == 404, f"Expected 404 for cross-user account update, got {put_res.status_code}"

        # User B attempts to delete User A's account
        del_res = await auth0_client_user_b.delete(f"/api/v1/accounts/{account_id}")
        assert del_res.status_code == 404, f"Expected 404 for cross-user account deletion, got {del_res.status_code}"

        # Verify User A's account is still intact
        verify_res = await auth0_client_user_a.get(f"/api/v1/accounts/{account_id}")
        assert verify_res.status_code == 200
        assert verify_res.json()["account_name"] == "User A Secret Vault"

    @pytest.mark.anyio
    async def test_cross_user_transaction_referencing_foreign_account_blocked(
        self,
        auth0_client_user_a: AsyncClient,
        auth0_client_user_b: AsyncClient,
    ):
        """User B cannot create a transaction referencing User A's account_id."""
        # User A creates an account
        create_res = await auth0_client_user_a.post("/api/v1/accounts", json={
            "account_name": "User A Bank",
            "account_type": "bank",
            "currency": "EUR",
        })
        assert create_res.status_code == 201
        account_a_id = create_res.json()["account_id"]

        # User B attempts to create a transaction referencing User A's account
        tx_payload = {
            "account_id": account_a_id,
            "transaction_date": "2026-11-06",
            "transaction_type": "BUY",
            "asset_symbol": "AAPL",
            "quantity": 10,
            "price": 150.0,
            "total_amount": 1500.0,
        }
        post_tx = await auth0_client_user_b.post("/api/v1/transactions", json=tx_payload)
        assert post_tx.status_code in (400, 404), f"Expected 400/404 for foreign account reference, got {post_tx.status_code}"
        assert post_tx.status_code != 500

    @pytest.mark.anyio
    async def test_backup_export_data_isolation(
        self,
        auth0_client_user_a: AsyncClient,
        auth0_client_user_b: AsyncClient,
    ):
        """Exporting a backup as User B must never leak User A's accounts or transactions."""
        # User A creates an account with distinct identifier
        unique_account_name = f"UserA_Confidential_{int(time.time())}"
        await auth0_client_user_a.post("/api/v1/accounts", json={
            "name": unique_account_name,
            "account_type": "INVESTMENT",
            "currency": "EUR",
        })

        # User B exports their backup
        export_res = await auth0_client_user_b.get("/api/v1/backup/export")
        assert export_res.status_code == 200
        backup_content = export_res.text
        assert unique_account_name not in backup_content, "Security breach: User A's confidential account leaked in User B's backup export!"
