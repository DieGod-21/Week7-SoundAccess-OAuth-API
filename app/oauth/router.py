"""Authorization Server endpoints (RFC 6749, 7636, 9700).

- POST /oauth/clients   — controlled client registration (admin key required)
- GET  /oauth/authorize — validated authorization request -> login + consent
- POST /oauth/authorize — authenticate user, record consent, issue auth code
- POST /oauth/token     — authorization_code (+PKCE S256) and client_credentials

Design notes:
* redirect_uri is compared EXACTLY against the registered whitelist; when it
  does not match, the server renders a local error page and never redirects
  (open-redirect prevention, RFC 9700 §4.1).
* Authorization codes are stored hashed (SHA-256), short-lived, single-use,
  and bound to client, user, redirect_uri, scope and PKCE challenge.
* Only S256 is accepted as code_challenge_method ("plain" is rejected).
* ROPC and implicit grants are intentionally not implemented.
"""
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import AuthorizationCode, OAuthClient, User, utcnow
from ..schemas import (
    VALID_SCOPES,
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    TokenResponse,
)
from ..security import (
    create_access_token,
    generate_authorization_code,
    hash_secret,
    pkce_verify,
    sha256_hex,
    verify_secret,
)

router = APIRouter(prefix="/oauth", tags=["OAuth 2.0 Authorization Server"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

SCOPE_DESCRIPTIONS = {
    "catalog:read": "Consultar el catálogo público de música",
    "profile:read": "Leer tu perfil (nombre, correo)",
    "playlist:read": "Leer tus playlists privadas",
    "playlist:write": "Crear y eliminar tus playlists",
}


# --------------------------------------------------------------------------
# Client registration (controlled — requires the admin registration key)
# --------------------------------------------------------------------------
@router.post(
    "/clients",
    response_model=ClientRegistrationResponse,
    response_model_exclude_none=True,
    status_code=201,
    summary="Register an OAuth client (admin-controlled)",
)
def register_client(
    body: ClientRegistrationRequest,
    db: Session = Depends(get_db),
    x_registration_key: str = Header(default="", alias="X-Registration-Key"),
):
    settings = get_settings()
    if not secrets.compare_digest(x_registration_key, settings.client_registration_key):
        # Registration is not public: an admin key must be presented.
        raise HTTPException(status_code=401, detail="invalid registration key")

    if db.query(OAuthClient).filter_by(client_id=body.client_id).first():
        raise HTTPException(status_code=409, detail="client_id already registered")
    if body.client_type == "public" and "client_credentials" in body.allowed_grant_types:
        raise HTTPException(status_code=400, detail="public clients cannot use client_credentials")
    if "authorization_code" in body.allowed_grant_types and not body.redirect_uris:
        raise HTTPException(status_code=400, detail="authorization_code requires redirect_uris")

    raw_secret = None
    secret_hash = None
    if body.client_type == "confidential":
        raw_secret = secrets.token_urlsafe(32)
        secret_hash = hash_secret(raw_secret)

    client = OAuthClient(
        client_id=body.client_id,
        client_secret_hash=secret_hash,
        client_name=body.client_name,
        client_type=body.client_type,
        redirect_uris=" ".join(body.redirect_uris),
        allowed_scopes=" ".join(body.allowed_scopes),
        allowed_grant_types=" ".join(body.allowed_grant_types),
    )
    db.add(client)
    db.commit()
    return ClientRegistrationResponse(
        client_id=client.client_id,
        client_name=client.client_name,
        client_type=client.client_type,
        redirect_uris=body.redirect_uris,
        allowed_scopes=body.allowed_scopes,
        allowed_grant_types=body.allowed_grant_types,
        client_secret=raw_secret,  # shown exactly once; only the hash is stored
    )


# --------------------------------------------------------------------------
# Authorization endpoint
# --------------------------------------------------------------------------
def _validate_authorize_request(
    db: Session,
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
) -> tuple[OAuthClient | None, str | None, str | None]:
    """Returns (client, fatal_error, redirect_error).

    fatal_error    -> render local page, never redirect (bad client/redirect).
    redirect_error -> RFC error code to deliver via redirect.
    """
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if client is None:
        return None, "client_id desconocido.", None
    if redirect_uri not in client.redirect_uri_list():
        return client, "redirect_uri no registrada para este cliente.", None
    if "authorization_code" not in client.grant_set():
        return client, None, "unauthorized_client"
    if response_type != "code":
        return client, None, "unsupported_response_type"
    requested = set(scope.split())
    if not requested or not requested <= VALID_SCOPES or not requested <= client.scope_set():
        return client, None, "invalid_scope"
    if not code_challenge or len(code_challenge) < 43 or len(code_challenge) > 128:
        return client, None, "invalid_request"
    if code_challenge_method != "S256":  # plain / none are rejected
        return client, None, "invalid_request"
    return client, None, None


def _redirect_with(redirect_uri: str, params: dict) -> RedirectResponse:
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{urlencode(params)}", status_code=302)


@router.get("/authorize", response_class=HTMLResponse, summary="Authorization request (login + consent)")
def authorize_get(
    request: Request,
    client_id: str = Query(min_length=3, max_length=80),
    redirect_uri: str = Query(max_length=500),
    response_type: str = Query(max_length=20),
    scope: str = Query(max_length=500),
    state: str = Query(default="", max_length=200),
    code_challenge: str = Query(default="", max_length=128),
    code_challenge_method: str = Query(default="", max_length=10),
    db: Session = Depends(get_db),
):
    client, fatal, redir_err = _validate_authorize_request(
        db,
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    if fatal:
        return templates.TemplateResponse(
            request, "oauth_error.html", {"message": fatal}, status_code=400
        )
    if redir_err:
        params = {"error": redir_err}
        if state:
            params["state"] = state
        return _redirect_with(redirect_uri, params)

    return templates.TemplateResponse(
        request,
        "authorize.html",
        {
            "client_name": client.client_name,
            "scopes": [
                {"name": s, "description": SCOPE_DESCRIPTIONS.get(s, s)}
                for s in scope.split()
            ],
            "params": {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": response_type,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
            },
            "error": None,
        },
    )


@router.post("/authorize", summary="Authenticate the user and decide on consent")
def authorize_post(
    request: Request,
    client_id: str = Form(max_length=80),
    redirect_uri: str = Form(max_length=500),
    response_type: str = Form(max_length=20),
    scope: str = Form(max_length=500),
    state: str = Form(default="", max_length=200),
    code_challenge: str = Form(default="", max_length=128),
    code_challenge_method: str = Form(default="", max_length=10),
    username: str = Form(max_length=50),
    password: str = Form(max_length=128),
    action: str = Form(max_length=10),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    # Re-validate everything: hidden form fields are attacker-controlled input.
    client, fatal, redir_err = _validate_authorize_request(
        db,
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    if fatal:
        return templates.TemplateResponse(
            request, "oauth_error.html", {"message": fatal}, status_code=400
        )
    if redir_err:
        params = {"error": redir_err}
        if state:
            params["state"] = state
        return _redirect_with(redirect_uri, params)

    if action == "deny":
        params = {"error": "access_denied"}
        if state:
            params["state"] = state
        return _redirect_with(redirect_uri, params)

    user = db.query(User).filter_by(username=username).first()
    if user is None or not verify_secret(password, user.password_hash):
        ctx = {
            "client_name": client.client_name,
            "scopes": [
                {"name": s, "description": SCOPE_DESCRIPTIONS.get(s, s)}
                for s in scope.split()
            ],
            "params": {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": response_type,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
            },
            "error": "Credenciales incorrectas. Inténtalo de nuevo.",
        }
        return templates.TemplateResponse(request, "authorize.html", ctx, status_code=401)

    # Issue a short-lived, single-use authorization code bound to
    # client + user + redirect_uri + scope + PKCE challenge.
    raw_code = generate_authorization_code()
    db.add(
        AuthorizationCode(
            code_hash=sha256_hex(raw_code),
            client_id=client.client_id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=utcnow() + timedelta(seconds=settings.auth_code_seconds),
        )
    )
    db.commit()

    params = {"code": raw_code}
    if state:
        params["state"] = state
    return _redirect_with(redirect_uri, params)


# --------------------------------------------------------------------------
# Token endpoint
# --------------------------------------------------------------------------
def _token_error(error: str, description: str, status: int = 400):
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    if status == 401:
        headers["WWW-Authenticate"] = 'Basic realm="soundaccess-token"'
    raise HTTPException(
        status_code=status,
        detail={"error": error, "error_description": description},
        headers=headers,
    )


@router.post("/token", response_model=TokenResponse, summary="Token endpoint")
def token(
    grant_type: str = Form(max_length=40),
    code: str = Form(default="", max_length=200),
    redirect_uri: str = Form(default="", max_length=500),
    client_id: str = Form(default="", max_length=80),
    client_secret: str = Form(default="", max_length=200),
    code_verifier: str = Form(default="", max_length=128),
    scope: str = Form(default="", max_length=500),
    db: Session = Depends(get_db),
):
    if grant_type == "authorization_code":
        return _grant_authorization_code(
            db, code=code, redirect_uri=redirect_uri,
            client_id=client_id, code_verifier=code_verifier,
        )
    if grant_type == "client_credentials":
        return _grant_client_credentials(
            db, client_id=client_id, client_secret=client_secret, scope=scope
        )
    # ROPC ("password") and any other grant are intentionally unsupported.
    _token_error("unsupported_grant_type", f"grant_type '{grant_type}' is not supported")


def _grant_authorization_code(db: Session, *, code: str, redirect_uri: str,
                              client_id: str, code_verifier: str) -> TokenResponse:
    if not code or not client_id or not redirect_uri or not code_verifier:
        _token_error("invalid_request", "code, client_id, redirect_uri and code_verifier are required")

    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if client is None or "authorization_code" not in client.grant_set():
        _token_error("invalid_client", "unknown client or grant not allowed", status=401)

    record = db.query(AuthorizationCode).filter_by(code_hash=sha256_hex(code)).first()
    if record is None:
        _token_error("invalid_grant", "authorization code is not valid")
    if record.used:
        # Single-use enforcement (RFC 6749 §4.1.2: replayed codes are rejected).
        _token_error("invalid_grant", "authorization code already used")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as _tz
        expires_at = expires_at.replace(tzinfo=_tz.utc)
    if expires_at < utcnow():
        _token_error("invalid_grant", "authorization code expired")
    if record.client_id != client_id:
        _token_error("invalid_grant", "authorization code was issued to another client")
    if record.redirect_uri != redirect_uri:
        _token_error("invalid_grant", "redirect_uri does not match the authorization request")
    if record.code_challenge_method != "S256" or not pkce_verify(code_verifier, record.code_challenge):
        _token_error("invalid_grant", "PKCE verification failed")

    # Invalidate the code BEFORE issuing the token.
    record.used = True
    db.commit()

    access_token, expires_in = create_access_token(
        subject=record.user_id, client_id=client_id, scope=record.scope
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in, scope=record.scope)


def _grant_client_credentials(db: Session, *, client_id: str,
                              client_secret: str, scope: str) -> TokenResponse:
    if not client_id or not client_secret:
        _token_error("invalid_client", "client authentication required", status=401)

    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if (
        client is None
        or client.client_type != "confidential"
        or client.client_secret_hash is None
        or not verify_secret(client_secret, client.client_secret_hash)
    ):
        _token_error("invalid_client", "client authentication failed", status=401)
    if "client_credentials" not in client.grant_set():
        _token_error("unauthorized_client", "client_credentials not allowed for this client")

    requested = set(scope.split()) if scope else client.scope_set()
    if not requested <= client.scope_set() or not requested <= VALID_SCOPES:
        _token_error("invalid_scope", "requested scope exceeds the client's allowed scopes")

    granted = " ".join(sorted(requested))
    # sub == client_id: the token represents the CLIENT, not a user.
    access_token, expires_in = create_access_token(
        subject=client.client_id, client_id=client.client_id, scope=granted
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in, scope=granted)
