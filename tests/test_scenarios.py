"""The six mandatory scenarios of the Week 7 assignment."""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import get_settings

from .conftest import bearer, pkce_token, service_token


# ---------------------------------------------------------------------------
# Scenario 1 — Authorization Code + PKCE happy path
# ---------------------------------------------------------------------------
class TestScenario1AuthorizationCodePKCE:
    def test_full_flow_grants_access_to_protected_api(self, client):
        data = pkce_token(client)
        assert data["token_type"] == "Bearer"
        assert 0 < data["expires_in"] <= 15 * 60
        me = client.get("/api/me", headers=bearer(data["access_token"]))
        assert me.status_code == 200
        assert me.json()["username"] == "ana"
        catalog = client.get("/api/catalog/tracks", headers=bearer(data["access_token"]))
        assert catalog.status_code == 200
        assert len(catalog.json()) >= 5

    def test_token_contains_required_claims(self, client):
        settings = get_settings()
        data = pkce_token(client)
        claims = pyjwt.decode(
            data["access_token"], settings.jwt_secret,
            algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience,
        )
        for claim in ("iss", "sub", "aud", "exp", "iat", "jti", "client_id", "scope"):
            assert claim in claims
        assert claims["iss"] == settings.jwt_issuer
        assert claims["client_id"] == "web-user-client"


# ---------------------------------------------------------------------------
# Scenario 2 — Client Credentials
# ---------------------------------------------------------------------------
class TestScenario2ClientCredentials:
    def test_service_client_gets_token_and_reads_catalog(self, client):
        resp = service_token(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "catalog:read"
        catalog = client.get("/api/catalog/tracks", headers=bearer(data["access_token"]))
        assert catalog.status_code == 200

    def test_service_token_represents_the_client_not_a_user(self, client):
        settings = get_settings()
        data = service_token(client).json()
        claims = pyjwt.decode(
            data["access_token"], settings.jwt_secret,
            algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience,
        )
        assert claims["sub"] == claims["client_id"] == "music-service-client"


# ---------------------------------------------------------------------------
# Scenario 3 — Protected request without token -> 401
# ---------------------------------------------------------------------------
class TestScenario3NoToken:
    def test_all_protected_endpoints_return_401(self, client):
        assert client.get("/api/catalog/tracks").status_code == 401
        assert client.get("/api/me").status_code == 401
        assert client.post("/api/playlists", json={"name": "x"}).status_code == 401
        assert client.get("/api/playlists/" + "a" * 32).status_code == 401
        assert client.delete("/api/playlists/" + "a" * 32).status_code == 401

    def test_401_carries_www_authenticate(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401
        assert "Bearer" in resp.headers.get("WWW-Authenticate", "")


# ---------------------------------------------------------------------------
# Scenario 4 — Invalid / expired / wrong-issuer / wrong-audience token -> 401
# ---------------------------------------------------------------------------
def _forge(claim_overrides: dict = None, *, key=None, algorithm="HS256") -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "iss": settings.jwt_issuer,
        "sub": "someone",
        "aud": settings.jwt_audience,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "jti": "forged",
        "client_id": "web-user-client",
        "scope": "catalog:read",
    }
    claims.update(claim_overrides or {})
    return pyjwt.encode(claims, key or settings.jwt_secret, algorithm=algorithm)


class TestScenario4InvalidTokens:
    def test_malformed_token(self, client):
        assert client.get("/api/me", headers=bearer("not.a.jwt")).status_code == 401

    def test_wrong_signature(self, client):
        token = _forge(key="another-key-entirely-different-0123456789")
        assert client.get("/api/me", headers=bearer(token)).status_code == 401

    def test_expired_token(self, client):
        token = _forge({"exp": datetime.now(timezone.utc) - timedelta(minutes=1)})
        assert client.get("/api/me", headers=bearer(token)).status_code == 401

    def test_wrong_issuer(self, client):
        token = _forge({"iss": "https://evil.example.com"})
        assert client.get("/api/me", headers=bearer(token)).status_code == 401

    def test_wrong_audience(self, client):
        token = _forge({"aud": "https://other-api.example.com"})
        assert client.get("/api/me", headers=bearer(token)).status_code == 401


# ---------------------------------------------------------------------------
# Scenario 5 — Valid token WITHOUT the required scope -> 403
# ---------------------------------------------------------------------------
class TestScenario5InsufficientScope:
    def test_catalog_only_token_cannot_read_profile(self, client):
        data = pkce_token(client, scope="catalog:read")
        resp = client.get("/api/me", headers=bearer(data["access_token"]))
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "insufficient_scope"

    def test_catalog_only_token_cannot_write_playlists(self, client):
        data = pkce_token(client, scope="catalog:read")
        resp = client.post(
            "/api/playlists", json={"name": "no"},
            headers=bearer(data["access_token"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scenario 6 — Cross-user playlist access is rejected without leaking data
# ---------------------------------------------------------------------------
class TestScenario6ResourceOwnership:
    def test_user_b_cannot_read_or_delete_user_a_playlist(self, client):
        ana = pkce_token(client, username="ana")["access_token"]
        bruno = pkce_token(client, username="bruno")["access_token"]

        created = client.post(
            "/api/playlists",
            json={"name": "Privada de Ana", "description": "secreta"},
            headers=bearer(ana),
        )
        assert created.status_code == 201
        playlist_id = created.json()["id"]

        read = client.get(f"/api/playlists/{playlist_id}", headers=bearer(bruno))
        assert read.status_code in (403, 404)
        body = read.text.lower()
        assert "privada de ana" not in body and "secreta" not in body  # no leak

        delete = client.delete(f"/api/playlists/{playlist_id}", headers=bearer(bruno))
        assert delete.status_code in (403, 404)

        # Still intact and readable by its owner.
        mine = client.get(f"/api/playlists/{playlist_id}", headers=bearer(ana))
        assert mine.status_code == 200
        assert mine.json()["owner_username"] == "ana"
