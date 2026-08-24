"""Test fixtures: isolated SQLite database, seeded demo data, OAuth helpers.

The test environment is configured BEFORE importing the application so the
cached settings and engine bind to the test database, never to development
data. Test credentials are synthetic and exist only for the test run.
"""
import base64
import hashlib
import os
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

TEST_DB = Path(__file__).resolve().parent / "test_soundaccess.db"

os.environ.update(
    SOUNDACCESS_JWT_SECRET="test-secret-" + secrets.token_urlsafe(32),
    SOUNDACCESS_JWT_ISSUER="https://auth.soundaccess.local",
    SOUNDACCESS_JWT_AUDIENCE="https://api.soundaccess.local",
    SOUNDACCESS_ACCESS_TOKEN_MINUTES="15",
    SOUNDACCESS_AUTH_CODE_SECONDS="60",
    SOUNDACCESS_DATABASE_URL=f"sqlite:///{TEST_DB}",
    SOUNDACCESS_CORS_ORIGINS="http://127.0.0.1:8000",
    SOUNDACCESS_SEED_USER_PASSWORD="test-users-pw-1",
    SOUNDACCESS_SEED_SERVICE_SECRET="test-service-secret-1",
    SOUNDACCESS_SEED_LEGACY_CLIENT_SECRET="test-legacy-secret-1",
    SOUNDACCESS_CLIENT_REGISTRATION_KEY="test-registration-key-1",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: F401,E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

USER_PASSWORD = "test-users-pw-1"
SERVICE_SECRET = "test-service-secret-1"
LEGACY_CLIENT_SECRET = "test-legacy-secret-1"
REGISTRATION_KEY = "test-registration-key-1"
REDIRECT_URI = "http://127.0.0.1:8000/client/callback"
ALL_SCOPES = "catalog:read profile:read playlist:read playlist:write"
ROPC_SCOPES = "profile.read playlists.read"


@pytest.fixture(scope="session", autouse=True)
def _database():
    if TEST_DB.exists():
        TEST_DB.unlink()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture()
def client():
    # raise_server_exceptions=False: assert sanitized 500s, never stack traces.
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------
def make_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)  # 64 chars, within 43..128
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def authorize_and_get_code(client, *, username="ana", password=USER_PASSWORD,
                           scope=ALL_SCOPES, challenge=None, state="xyz-state"):
    """Drive GET+POST /oauth/authorize and return the authorization code."""
    verifier, chal = make_pkce_pair()
    if challenge is not None:
        chal = challenge
    params = {
        "client_id": "web-user-client",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "code_challenge": chal,
        "code_challenge_method": "S256",
    }
    page = client.get("/oauth/authorize", params=params)
    assert page.status_code == 200, page.text
    resp = client.post(
        "/oauth/authorize",
        data={**params, "username": username, "password": password, "action": "allow"},
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query.get("state") == [state]
    return query["code"][0], verifier


def pkce_token(client, *, scope=ALL_SCOPES, username="ana"):
    code, verifier = authorize_and_get_code(client, scope=scope, username=username)
    resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": "web-user-client",
            "code_verifier": verifier,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def service_token(client, *, scope="catalog:read", secret=SERVICE_SECRET):
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "music-service-client",
            "client_secret": secret,
            "scope": scope,
        },
    )


def ropc_token(client, *, username="alumno.demo", password=USER_PASSWORD,
                scope=ROPC_SCOPES, client_id="legacy-client",
                client_secret=LEGACY_CLIENT_SECRET):
    """Task 3 — Resource Owner Password Credentials grant."""
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
    )


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
