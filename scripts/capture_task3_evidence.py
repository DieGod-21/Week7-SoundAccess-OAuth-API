"""Capture real evidence for Task 3 (A1-A3 ROPC, B1-B4 and B5-server-echo
PKCE) against the ACTUAL running application (http://127.0.0.1:8000), not
mocked or hand-written. Companion to scripts/capture_browser_evidence.py
(Task 1) and scripts/capture_task3_browser_evidence.py (B5 live-browser
abort, which needs Playwright and is kept separate).

Every secret, password, and access token written to disk here is redacted:
JWTs keep header+payload (useful to verify claims) but truncate the
signature; passwords/client secrets are replaced with a fixed placeholder
in the saved request bodies.

Run with the app already up and seeded:
    python3 scripts/capture_task3_evidence.py
"""
import base64
import hashlib
import json
import os
import secrets as pysecrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"

os.chdir(ROOT)  # so app.config picks up the same .env uvicorn is using
sys.path.insert(0, str(ROOT))
from app.config import get_settings  # noqa: E402

SETTINGS = get_settings()
USER_PASSWORD = SETTINGS.seed_user_password
LEGACY_SECRET = SETTINGS.seed_legacy_client_secret
SERVICE_SECRET = SETTINGS.seed_service_secret
REDIRECT_URI = f"{BASE}/client/callback"

REDACTED = "<REDACTED>"


def redact_jwt(token: str) -> str:
    # Same short prefix/suffix redaction style as Task 1's evidence
    # (docs/evidence/ev04_token_exchange.txt) -- never a usable token.
    return f"{token[:20]}...{token[-8:]}"


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text.rstrip() + "\n")
    print("wrote", name)


def redact_body(body: dict, *keys) -> dict:
    out = dict(body)
    for k in keys:
        if k in out:
            out[k] = REDACTED
    return out


def make_pkce_pair():
    verifier = pysecrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ===========================================================================
# A1 — valid ROPC request
# ===========================================================================
def a1_valid_ropc():
    body = {
        "grant_type": "password", "username": "alumno.demo",
        "password": USER_PASSWORD, "client_id": "legacy-client",
        "client_secret": LEGACY_SECRET, "scope": "profile.read playlists.read",
    }
    resp = requests.post(f"{BASE}/oauth/token", data=body)
    data = resp.json()
    write(
        "ev_t3_a1_ropc_request_response.txt",
        "Request:\n"
        f"POST /oauth/token\n{json.dumps(redact_body(body, 'password', 'client_secret'), indent=2)}\n\n"
        f"Response: {resp.status_code}\n"
        f"{json.dumps({**data, 'access_token': redact_jwt(data['access_token'])}, indent=2)}",
    )

    claims = pyjwt.decode(
        data["access_token"], SETTINGS.jwt_secret,
        algorithms=[SETTINGS.jwt_algorithm], audience=SETTINGS.jwt_audience,
    )
    write("ev_t3_a1_token_claims_decoded.txt", json.dumps(claims, indent=2))

    token = data["access_token"]
    me = requests.get(f"{BASE}/api/me", headers={"Authorization": f"Bearer {token}"})
    playlists = requests.get(f"{BASE}/api/playlists", headers={"Authorization": f"Bearer {token}"})
    write(
        "ev_t3_a1_protected_resources_200.txt",
        f"GET /api/me -> {me.status_code}\n{json.dumps(me.json(), indent=2)}\n\n"
        f"GET /api/playlists -> {playlists.status_code}\n{json.dumps(playlists.json(), indent=2)}",
    )
    return token


# ===========================================================================
# A2 — invalid credentials / client
# ===========================================================================
def a2_invalid_cases():
    lines = []

    wrong_pw = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "username": "alumno.demo", "password": "wrong-password",
        "client_id": "legacy-client", "client_secret": LEGACY_SECRET, "scope": "profile.read",
    })
    lines.append(f"[wrong password]      -> {wrong_pw.status_code} {wrong_pw.json()}")

    unknown_user = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "username": "no-such-user", "password": "whatever",
        "client_id": "legacy-client", "client_secret": LEGACY_SECRET, "scope": "profile.read",
    })
    lines.append(f"[unknown username]     -> {unknown_user.status_code} {unknown_user.json()}")
    lines.append(
        "  -> same error_description as [wrong password]: "
        f"{unknown_user.json()['detail']['error_description'] == wrong_pw.json()['detail']['error_description']}"
        " (no user enumeration)"
    )

    wrong_secret = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "username": "alumno.demo", "password": USER_PASSWORD,
        "client_id": "legacy-client", "client_secret": "wrong-secret", "scope": "profile.read",
    })
    lines.append(f"[wrong client_secret]  -> {wrong_secret.status_code} {wrong_secret.json()}")

    unauthorized_client = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "username": "ana", "password": USER_PASSWORD,
        "client_id": "music-service-client", "client_secret": SERVICE_SECRET, "scope": "profile.read",
    })
    lines.append(f"[client not authorized for password grant] -> {unauthorized_client.status_code} {unauthorized_client.json()}")

    missing_fields = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "client_id": "legacy-client",
    })
    lines.append(f"[missing username/password/client_secret] -> {missing_fields.status_code} {missing_fields.json()}")

    write("ev_t3_a2_invalid_credentials_or_client.txt", "\n".join(lines))


# ===========================================================================
# A3 — protected resource failures
# ===========================================================================
def a3_protected_resource_failures(valid_token: str):
    lines = []

    no_token = requests.get(f"{BASE}/api/me")
    lines.append(f"[no Authorization header] GET /api/me -> {no_token.status_code} {no_token.json()}")

    now = datetime.now(timezone.utc)
    expired_claims = {
        "iss": SETTINGS.jwt_issuer, "sub": "expired-demo-subject", "aud": SETTINGS.jwt_audience,
        "exp": now - timedelta(minutes=1), "iat": now - timedelta(minutes=16),
        "jti": "evidence-expired-ropc", "client_id": "legacy-client", "scope": "profile.read",
    }
    expired_token = pyjwt.encode(expired_claims, SETTINGS.jwt_secret, algorithm=SETTINGS.jwt_algorithm)
    expired_resp = requests.get(f"{BASE}/api/me", headers={"Authorization": f"Bearer {expired_token}"})
    lines.append(f"[expired token] GET /api/me -> {expired_resp.status_code} {expired_resp.json()}")

    header, payload, signature = valid_token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
    tampered_resp = requests.get(f"{BASE}/api/me", headers={"Authorization": f"Bearer {tampered}"})
    lines.append(f"[altered signature] GET /api/me -> {tampered_resp.status_code} {tampered_resp.json()}")

    scoped = requests.post(f"{BASE}/oauth/token", data={
        "grant_type": "password", "username": "alumno.demo", "password": USER_PASSWORD,
        "client_id": "legacy-client", "client_secret": LEGACY_SECRET, "scope": "playlists.read",
    }).json()
    narrow_token = scoped["access_token"]
    forbidden = requests.get(f"{BASE}/api/me", headers={"Authorization": f"Bearer {narrow_token}"})
    lines.append(f"[insufficient scope: token has only playlists.read] GET /api/me -> {forbidden.status_code} {forbidden.json()}")
    still_ok = requests.get(f"{BASE}/api/playlists", headers={"Authorization": f"Bearer {narrow_token}"})
    lines.append(f"  same token -> GET /api/playlists -> {still_ok.status_code} (works for the scope it DOES have)")

    write("ev_t3_a3_protected_resource_failures.txt", "\n".join(lines))


# ===========================================================================
# B — Authorization Code + PKCE (server-side, non-browser scenarios)
# ===========================================================================
def authorize_and_get_code(session, *, username="ana", password=None, scope="catalog:read profile:read playlist:read playlist:write",
                            redirect_uri=REDIRECT_URI, state="evidence-state-xyz", challenge=None):
    verifier, chal = make_pkce_pair()
    if challenge is not None:
        chal = challenge
    params = {
        "client_id": "web-user-client", "redirect_uri": redirect_uri, "response_type": "code",
        "scope": scope, "state": state, "code_challenge": chal, "code_challenge_method": "S256",
    }
    get_resp = session.get(f"{BASE}/oauth/authorize", params=params)
    post_resp = session.post(
        f"{BASE}/oauth/authorize",
        data={**params, "username": username, "password": password or USER_PASSWORD, "action": "allow"},
        allow_redirects=False,
    )
    return get_resp, post_resp, verifier


def b1_valid_flow():
    session = requests.Session()
    get_resp, post_resp, verifier = authorize_and_get_code(session)
    location = post_resp.headers["location"]
    code = parse_qs(urlparse(location).query)["code"][0]
    token_resp = session.post(f"{BASE}/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": "web-user-client", "code_verifier": verifier,
    })
    data = token_resp.json()
    token = data["access_token"]
    me = session.get(f"{BASE}/api/me", headers={"Authorization": f"Bearer {token}"})
    playlists = session.get(f"{BASE}/api/playlists", headers={"Authorization": f"Bearer {token}"})
    write(
        "ev_t3_b1_pkce_valid_flow.txt",
        f"GET /oauth/authorize -> {get_resp.status_code} (login+consent form)\n"
        f"POST /oauth/authorize (allow) -> {post_resp.status_code}, redirect carries code=<redacted>&state={parse_qs(urlparse(location).query)['state'][0]}\n"
        f"POST /oauth/token -> {token_resp.status_code}\n"
        f"{json.dumps({**data, 'access_token': redact_jwt(token)}, indent=2)}\n\n"
        f"GET /api/me -> {me.status_code}\n{json.dumps(me.json(), indent=2)}\n\n"
        f"GET /api/playlists (Task 3, list-own) -> {playlists.status_code}\n{json.dumps(playlists.json(), indent=2)}",
    )


def b2_invalid_redirect():
    session = requests.Session()
    _, challenge = make_pkce_pair()
    params = {
        "client_id": "web-user-client", "redirect_uri": "https://attacker.example.com/steal",
        "response_type": "code", "scope": "catalog:read", "state": "s",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }
    resp = session.get(f"{BASE}/oauth/authorize", params=params, allow_redirects=False)
    write(
        "ev_t3_b2_invalid_redirect_uri.txt",
        f"GET /oauth/authorize?redirect_uri=https://attacker.example.com/steal -> {resp.status_code}\n"
        f"'location' header present: {'location' in resp.headers}  (never redirects to an unregistered URI)",
    )


def b3_invalid_verifier():
    session = requests.Session()
    get_resp, post_resp, _correct_verifier = authorize_and_get_code(session)
    code = parse_qs(urlparse(post_resp.headers["location"]).query)["code"][0]
    resp = session.post(f"{BASE}/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": "web-user-client", "code_verifier": "x" * 64,
    })
    write(
        "ev_t3_b3_invalid_code_verifier.txt",
        f"POST /oauth/token with a code_verifier that does NOT match the original code_challenge\n"
        f"-> {resp.status_code} {resp.json()}",
    )


def b4_code_reuse():
    session = requests.Session()
    get_resp, post_resp, verifier = authorize_and_get_code(session)
    code = parse_qs(urlparse(post_resp.headers["location"]).query)["code"][0]
    payload = {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": "web-user-client", "code_verifier": verifier,
    }
    first = session.post(f"{BASE}/oauth/token", data=payload)
    second = session.post(f"{BASE}/oauth/token", data=payload)
    write(
        "ev_t3_b4_authorization_code_reuse.txt",
        f"First exchange  -> {first.status_code} (access_token issued, redacted)\n"
        f"Second exchange (same code, replayed) -> {second.status_code} {second.json()}",
    )


def b5_server_echoes_state():
    session = requests.Session()
    tricky_state = "evidence-tricky-state~abc_123"
    get_resp, post_resp, _ = authorize_and_get_code(session, state=tricky_state)
    returned_state = parse_qs(urlparse(post_resp.headers["location"]).query)["state"][0]
    write(
        "ev_t3_b5_server_state_echo.txt",
        f"Sent state=\"{tricky_state}\" in the authorization request.\n"
        f"Server's 302 redirect echoes state=\"{returned_state}\" unaltered: {returned_state == tricky_state}\n\n"
        "This exact-echo behavior is what makes the client-side comparison in\n"
        "frontend/callback.html (`state !== savedState`) meaningful — see\n"
        "ev_t3_b5_browser_state_mismatch_abort.png / .txt for the live-browser\n"
        "evidence of the client aborting on a mismatched state.",
    )


if __name__ == "__main__":
    token = a1_valid_ropc()
    a2_invalid_cases()
    a3_protected_resource_failures(token)
    b1_valid_flow()
    b2_invalid_redirect()
    b3_invalid_verifier()
    b4_code_reuse()
    b5_server_echoes_state()
    print("\nAll Task 3 (non-browser) evidence written to", OUT)
