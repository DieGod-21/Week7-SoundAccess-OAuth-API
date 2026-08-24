"""Additional security tests (section 24 of the work plan)."""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.config import get_settings

from .conftest import (
    ALL_SCOPES,
    REDIRECT_URI,
    REGISTRATION_KEY,
    SERVICE_SECRET,
    USER_PASSWORD,
    authorize_and_get_code,
    bearer,
    make_pkce_pair,
    pkce_token,
    service_token,
)


def _authorize_params(**overrides):
    _, challenge = make_pkce_pair()
    params = {
        "client_id": "web-user-client",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": ALL_SCOPES,
        "state": "s1",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    params.update(overrides)
    return params


# --------------------------- authorization endpoint -----------------------
class TestAuthorizeHardening:
    def test_unregistered_redirect_uri_never_redirects(self, client):
        resp = client.get(
            "/oauth/authorize",
            params=_authorize_params(redirect_uri="https://evil.example.com/steal"),
            follow_redirects=False,
        )
        assert resp.status_code == 400          # local error page
        assert "location" not in resp.headers   # open redirect prevented

    def test_unknown_client_never_redirects(self, client):
        resp = client.get(
            "/oauth/authorize",
            params=_authorize_params(client_id="ghost-client"),
            follow_redirects=False,
        )
        assert resp.status_code == 400
        assert "location" not in resp.headers

    def test_invalid_scope_redirects_with_error(self, client):
        resp = client.get(
            "/oauth/authorize",
            params=_authorize_params(scope="admin:everything"),
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=invalid_scope" in resp.headers["location"]
        assert "state=s1" in resp.headers["location"]

    def test_pkce_plain_method_is_rejected(self, client):
        resp = client.get(
            "/oauth/authorize",
            params=_authorize_params(code_challenge_method="plain"),
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=invalid_request" in resp.headers["location"]

    def test_missing_code_challenge_is_rejected(self, client):
        resp = client.get(
            "/oauth/authorize",
            params=_authorize_params(code_challenge=""),
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=invalid_request" in resp.headers["location"]

    def test_wrong_password_does_not_issue_code(self, client):
        params = _authorize_params()
        resp = client.post(
            "/oauth/authorize",
            data={**params, "username": "ana", "password": "wrong-password", "action": "allow"},
            follow_redirects=False,
        )
        assert resp.status_code == 401
        assert "code=" not in resp.text

    def test_deny_redirects_with_access_denied(self, client):
        params = _authorize_params()
        resp = client.post(
            "/oauth/authorize",
            data={**params, "username": "ana", "password": USER_PASSWORD, "action": "deny"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=access_denied" in resp.headers["location"]


# --------------------------- token endpoint --------------------------------
class TestTokenHardening:
    def test_invalid_pkce_verifier_rejected(self, client):
        code, _ = authorize_and_get_code(client)
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": "web-user-client",
            "code_verifier": "A" * 64,
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_grant"

    def test_authorization_code_is_single_use(self, client):
        code, verifier = authorize_and_get_code(client)
        payload = {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": "web-user-client",
            "code_verifier": verifier,
        }
        assert client.post("/oauth/token", data=payload).status_code == 200
        replay = client.post("/oauth/token", data=payload)
        assert replay.status_code == 400
        assert replay.json()["detail"]["error"] == "invalid_grant"

    def test_expired_authorization_code_rejected(self, client, monkeypatch):
        from app.oauth import router as oauth_router_module
        code, verifier = authorize_and_get_code(client)
        from app.database import SessionLocal
        from app.models import AuthorizationCode, utcnow
        from app.security import sha256_hex
        db = SessionLocal()
        record = db.query(AuthorizationCode).filter_by(code_hash=sha256_hex(code)).one()
        record.expires_at = utcnow() - timedelta(seconds=5)
        db.commit(); db.close()
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": "web-user-client",
            "code_verifier": verifier,
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"]["error_description"]

    def test_redirect_uri_mismatch_at_token_rejected(self, client):
        code, verifier = authorize_and_get_code(client)
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": "http://localhost:8000/client/callback",  # differs
            "client_id": "web-user-client", "code_verifier": verifier,
        })
        assert resp.status_code == 400

    def test_wrong_client_secret_is_401(self, client):
        resp = service_token(client, secret="totally-wrong")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "invalid_client"

    def test_service_client_cannot_escalate_scope(self, client):
        resp = service_token(client, scope="playlist:write")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_scope"

    def test_ropc_rejected_for_a_client_not_authorized_for_it(self, client):
        # Superseded by Task 3: ROPC (grant_type=password) is now
        # implemented (see TestTask3Ropc in test_task3_ropc_pkce.py), but
        # ONLY for the seeded legacy-client. This confirms the original
        # intent of this test still holds: ROPC must never work for an
        # "arbitrary client" — here, a confidential client that is properly
        # authenticated but was never authorized for the password grant.
        resp = client.post("/oauth/token", data={
            "grant_type": "password", "username": "ana", "password": USER_PASSWORD,
            "client_id": "music-service-client", "client_secret": SERVICE_SECRET,
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "unauthorized_client"

    def test_ropc_rejected_without_client_authentication(self, client):
        # A public client (no secret) can never use ROPC either way.
        resp = client.post("/oauth/token", data={
            "grant_type": "password", "username": "ana", "password": USER_PASSWORD,
            "client_id": "web-user-client",
        })
        assert resp.status_code in (400, 401)
        assert resp.json()["detail"]["error"] in ("invalid_request", "invalid_client")


# --------------------------- JWT hardening ---------------------------------
class TestJwtHardening:
    def test_alg_none_token_rejected(self, client):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        claims = {
            "iss": settings.jwt_issuer, "sub": "x", "aud": settings.jwt_audience,
            "exp": now + timedelta(minutes=5), "iat": now, "jti": "n",
            "client_id": "web-user-client", "scope": "catalog:read",
        }
        token = pyjwt.encode(claims, key=None, algorithm="none")
        assert client.get("/api/catalog/tracks", headers=bearer(token)).status_code == 401

    def test_missing_required_claims_rejected(self, client):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        # No jti / client_id / scope.
        claims = {
            "iss": settings.jwt_issuer, "sub": "x", "aud": settings.jwt_audience,
            "exp": now + timedelta(minutes=5), "iat": now,
        }
        token = pyjwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        assert client.get("/api/catalog/tracks", headers=bearer(token)).status_code == 401

    def test_token_in_query_string_is_not_accepted(self, client):
        data = pkce_token(client)
        resp = client.get("/api/me", params={"access_token": data["access_token"]})
        assert resp.status_code == 401

    def test_service_token_cannot_access_user_profile(self, client):
        # Valid credential (401 would be wrong) but not authorized -> 403.
        resp = service_token(client)
        token = resp.json()["access_token"]
        forbidden = client.get("/api/me", headers=bearer(token))
        assert forbidden.status_code == 403


# --------------------------- registration & input --------------------------
class TestRegistrationAndInput:
    def test_client_registration_requires_admin_key(self, client):
        body = {
            "client_id": "rogue-client", "client_name": "Rogue", "client_type": "public",
            "redirect_uris": ["http://localhost:9999/cb"],
            "allowed_scopes": ["catalog:read"], "allowed_grant_types": ["authorization_code"],
        }
        assert client.post("/oauth/clients", json=body).status_code == 401
        ok = client.post("/oauth/clients", json=body,
                         headers={"X-Registration-Key": REGISTRATION_KEY})
        assert ok.status_code == 201
        assert "client_secret" not in ok.json() or ok.json()["client_secret"] is None

    def test_confidential_registration_returns_secret_once_hashed_in_db(self, client):
        body = {
            "client_id": "batch-service", "client_name": "Batch", "client_type": "confidential",
            "redirect_uris": [], "allowed_scopes": ["catalog:read"],
            "allowed_grant_types": ["client_credentials"],
        }
        resp = client.post("/oauth/clients", json=body,
                           headers={"X-Registration-Key": REGISTRATION_KEY})
        assert resp.status_code == 201
        secret = resp.json()["client_secret"]
        assert secret and len(secret) > 20
        from app.database import SessionLocal
        from app.models import OAuthClient
        db = SessionLocal()
        stored = db.query(OAuthClient).filter_by(client_id="batch-service").one()
        db.close()
        assert secret not in stored.client_secret_hash
        assert stored.client_secret_hash.startswith("$argon2")

    def test_sql_injection_style_input_is_harmless(self, client):
        data = pkce_token(client)
        resp = client.post(
            "/api/playlists",
            json={"name": "x'); DROP TABLE playlists;--", "description": ""},
            headers=bearer(data["access_token"]),
        )
        assert resp.status_code == 201  # stored as inert text via the ORM
        again = client.get("/api/catalog/tracks", headers=bearer(data["access_token"]))
        assert again.status_code == 200

    def test_invalid_payload_is_422_without_stack_trace(self, client):
        data = pkce_token(client)
        resp = client.post(
            "/api/playlists", json={"description": 12345},
            headers=bearer(data["access_token"]),
        )
        assert resp.status_code == 422
        assert "Traceback" not in resp.text

    def test_invalid_playlist_id_format_rejected(self, client):
        data = pkce_token(client)
        resp = client.get("/api/playlists/../../etc/passwd",
                          headers=bearer(data["access_token"]))
        assert resp.status_code in (404, 422)

    def test_nonexistent_playlist_is_404(self, client):
        data = pkce_token(client)
        resp = client.get("/api/playlists/" + "f" * 32,
                          headers=bearer(data["access_token"]))
        assert resp.status_code == 404


# --------------------------- seed credential hardening ----------------------
class TestSeedRequiresExplicitCredentials:
    """Task 3 finalization hardening: app/seed.py must never fall back to a
    known/guessable credential (it used to default to "changeme-demo" etc.
    when a SOUNDACCESS_SEED_* variable was unset). Seeding an EMPTY database
    with any of the three required variables missing must fail loudly and
    specifically, not silently succeed with a predictable secret. Runs
    against its own throwaway in-memory database so it never touches the
    shared, already-seeded test database from the `client` fixture."""

    def test_seeding_fails_clearly_when_a_required_variable_is_missing(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.config import get_settings
        from app.database import Base
        from app import models  # noqa: F401  (register models on Base)
        from app.seed import seed, SeedConfigurationError

        monkeypatch.setenv("SOUNDACCESS_SEED_USER_PASSWORD", "")
        get_settings.cache_clear()
        try:
            engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=engine)
            db = sessionmaker(bind=engine)()
            try:
                with pytest.raises(SeedConfigurationError) as exc_info:
                    seed(db)
                assert "SOUNDACCESS_SEED_USER_PASSWORD" in str(exc_info.value)
                # No known/guessable fallback value must have been used --
                # nothing should have been written to this empty database.
                from app.models import User
                assert db.query(User).count() == 0
            finally:
                db.close()
        finally:
            get_settings.cache_clear()  # restore the real test settings for later tests
