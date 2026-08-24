"""Task 3 — explicit A1-A3 (ROPC) and B1-B5 (Authorization Code + PKCE)
acceptance tests, named to match the assignment's own scenario IDs for
direct traceability in the requirement matrix (see EVIDENCIAS.md).

These are additive: every Task 1 test in test_scenarios.py/test_security.py
is kept and must still pass (regression, work-plan §36). Some scenarios here
necessarily duplicate coverage that already existed under different test
names in Task 1 (e.g. B2-B4 mirror existing PKCE hardening tests) — they are
repeated here, under the assignment's own naming, specifically so the
evidence-to-requirement matrix can point at one unambiguous test per ID.
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import get_settings

from .conftest import (
    REDIRECT_URI,
    ROPC_SCOPES,
    USER_PASSWORD,
    authorize_and_get_code,
    bearer,
    make_pkce_pair,
    pkce_token,
    ropc_token,
)


# ===========================================================================
# Flow A — ROPC (grant_type=password), legacy-client / alumno.demo
# ===========================================================================
class TestTask3RopcA1ValidRequest:
    def test_a1_valid_ropc_returns_200_with_usable_token_and_correct_scopes(self, client):
        resp = ropc_token(client)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["token_type"] == "Bearer"
        assert 0 < data["expires_in"] <= 15 * 60
        assert set(data["scope"].split()) == set(ROPC_SCOPES.split())

        settings = get_settings()
        claims = pyjwt.decode(
            data["access_token"], settings.jwt_secret,
            algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience,
        )
        for required in ("iss", "sub", "aud", "iat", "exp", "jti", "client_id", "scope"):
            assert required in claims
        assert claims["iss"] == settings.jwt_issuer
        assert claims["client_id"] == "legacy-client"
        # sub is the USER's id (ROPC represents a person), not the client_id —
        # same convention as Authorization Code, distinct from Client Credentials.
        assert claims["sub"] != claims["client_id"]

        # The token must actually work against the protected API.
        me = client.get("/api/me", headers=bearer(data["access_token"]))
        assert me.status_code == 200
        assert me.json()["username"] == "alumno.demo"
        playlists = client.get("/api/playlists", headers=bearer(data["access_token"]))
        assert playlists.status_code == 200


class TestTask3RopcA2InvalidCredentialsOrClient:
    def test_a2_wrong_password_is_invalid_grant(self, client):
        resp = ropc_token(client, password="not-the-right-password")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_grant"

    def test_a2_unknown_username_is_the_same_invalid_grant(self, client):
        # Must be indistinguishable from a wrong password (no user enumeration).
        resp = ropc_token(client, username="no-such-user")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_grant"
        assert resp.json()["detail"]["error_description"] == \
            ropc_token(client, password="wrong").json()["detail"]["error_description"]

    def test_a2_wrong_client_secret_is_invalid_client(self, client):
        resp = ropc_token(client, client_secret="not-the-right-secret")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "invalid_client"

    def test_a2_ropc_rejected_for_a_client_not_authorized_for_it(self, client):
        from .conftest import SERVICE_SECRET
        resp = ropc_token(client, client_id="music-service-client", client_secret=SERVICE_SECRET)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "unauthorized_client"

    def test_a2_missing_fields_is_invalid_request(self, client):
        resp = client.post("/oauth/token", data={"grant_type": "password", "client_id": "legacy-client"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_request"


class TestTask3RopcA3ProtectedResourceFailures:
    def test_a3_missing_token_is_401(self, client):
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/playlists").status_code == 401

    def test_a3_expired_ropc_token_is_401(self, client):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        claims = {
            "iss": settings.jwt_issuer, "sub": "alumno-demo-id",
            "aud": settings.jwt_audience, "exp": now - timedelta(minutes=1),
            "iat": now - timedelta(minutes=16), "jti": "expired-ropc",
            "client_id": "legacy-client", "scope": "profile.read",
        }
        expired = pyjwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        resp = client.get("/api/me", headers=bearer(expired))
        assert resp.status_code == 401

    def test_a3_altered_token_signature_is_401(self, client):
        data = ropc_token(client).json()
        header, payload, signature = data["access_token"].split(".")
        tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
        resp = client.get("/api/me", headers=bearer(tampered))
        assert resp.status_code == 401

    def test_a3_insufficient_scope_is_403(self, client):
        # Token only carries playlists.read — must not reach a profile:read endpoint.
        data = ropc_token(client, scope="playlists.read").json()
        resp = client.get("/api/me", headers=bearer(data["access_token"]))
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "insufficient_scope"
        # But it DOES work for the scope it was actually granted.
        ok = client.get("/api/playlists", headers=bearer(data["access_token"]))
        assert ok.status_code == 200


# ===========================================================================
# Flow B — Authorization Code + PKCE (audited, no functional changes needed)
# ===========================================================================
class TestTask3PkceB1ValidFlow:
    def test_b1_login_consent_client_scopes_state_redirect_all_validated(self, client):
        data = pkce_token(client)
        assert data["token_type"] == "Bearer"
        me = client.get("/api/me", headers=bearer(data["access_token"]))
        assert me.status_code == 200
        playlists = client.get("/api/playlists", headers=bearer(data["access_token"]))
        assert playlists.status_code == 200


class TestTask3PkceB2InvalidRedirect:
    def test_b2_unregistered_redirect_uri_rejected_no_redirection(self, client):
        _, challenge = make_pkce_pair()
        params = {
            "client_id": "web-user-client", "redirect_uri": "https://attacker.example.com/steal",
            "response_type": "code", "scope": "catalog:read", "state": "s",
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        resp = client.get("/oauth/authorize", params=params, follow_redirects=False)
        assert resp.status_code == 400
        assert "location" not in resp.headers  # never redirects to the unregistered URI


class TestTask3PkceB3InvalidVerifier:
    def test_b3_incorrect_code_verifier_is_400_invalid_grant(self, client):
        code, _correct_verifier = authorize_and_get_code(client)
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": "web-user-client",
            "code_verifier": "x" * 64,
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_grant"


class TestTask3PkceB4CodeReuse:
    def test_b4_second_exchange_of_the_same_code_fails(self, client):
        code, verifier = authorize_and_get_code(client)
        payload = {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": "web-user-client",
            "code_verifier": verifier,
        }
        first = client.post("/oauth/token", data=payload)
        assert first.status_code == 200
        second = client.post("/oauth/token", data=payload)
        assert second.status_code == 400
        assert second.json()["detail"]["error"] == "invalid_grant"


class TestTask3PkceB5StateMismatch:
    """The state comparison that protects the Authorization Code flow from
    CSRF is, correctly, a CLIENT-side check (RFC 6749 §10.12): the client
    generates `state`, remembers it, and must abort if the value it gets
    back differs. The server's only role is to echo `state` back unaltered
    so tampering is detectable — verified here. The client-side guard itself
    is verified as a source-contract test (its exact presence and ordering
    in frontend/callback.html), and exercised live with a real browser in
    scripts/capture_task3_evidence.py for EVIDENCIAS.md (B5)."""

    def test_b5_server_echoes_state_unaltered(self, client):
        _, challenge = make_pkce_pair()
        tricky_state = "abc-123_XYZ~state"
        params = {
            "client_id": "web-user-client", "redirect_uri": REDIRECT_URI,
            "response_type": "code", "scope": "catalog:read", "state": tricky_state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        client.get("/oauth/authorize", params=params)
        resp = client.post("/oauth/authorize", data={
            **params, "username": "ana", "password": USER_PASSWORD, "action": "allow",
        }, follow_redirects=False)
        assert resp.status_code == 302
        from urllib.parse import parse_qs, urlparse
        returned_state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
        assert returned_state == tricky_state

    def test_b5_client_side_mismatch_guard_present_and_precedes_token_exchange(self):
        from pathlib import Path
        source = Path(__file__).resolve().parents[1] / "frontend" / "callback.html"
        js = source.read_text()
        guard = "state !== savedState"
        exchange_call = 'fetch(TOKEN_URL'
        assert guard in js, "state-mismatch guard missing from frontend/callback.html"
        assert exchange_call in js, "token exchange call missing from frontend/callback.html"
        # The guard must appear BEFORE the token exchange in source order, so
        # a mismatch provably aborts the flow before any code is exchanged.
        assert js.index(guard) < js.index(exchange_call)
