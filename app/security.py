"""Cryptographic helpers: Argon2 hashing, PKCE S256, JWT issue/verify.

Security decisions (see docs/report and README):
- Argon2id (argon2-cffi defaults) for user passwords AND client secrets.
- JWT signed with a single explicitly configured algorithm; verification
  passes `algorithms=[settings.jwt_algorithm]` so `alg=none` or any
  substituted algorithm is rejected by PyJWT before signature check.
- Access tokens are short-lived (15 min default) and carry
  iss/sub/aud/exp/iat/jti/client_id/scope, all validated server-side
  (RFC 7519, RFC 9068).
"""
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()


# --------------------------------------------------------------------------
# Password / client-secret hashing
# --------------------------------------------------------------------------
def hash_secret(raw: str) -> str:
    return _hasher.hash(raw)


def verify_secret(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --------------------------------------------------------------------------
# Authorization codes / PKCE (RFC 7636)
# --------------------------------------------------------------------------
def generate_authorization_code() -> str:
    return secrets.token_urlsafe(48)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def pkce_challenge_from_verifier(code_verifier: str) -> str:
    """S256: BASE64URL(SHA256(code_verifier)) without padding."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def pkce_verify(code_verifier: str, code_challenge: str) -> bool:
    if not (43 <= len(code_verifier) <= 128):
        return False
    expected = pkce_challenge_from_verifier(code_verifier)
    return secrets.compare_digest(expected, code_challenge)


# --------------------------------------------------------------------------
# JWT access tokens (RFC 7519 / RFC 9068)
# --------------------------------------------------------------------------
class TokenError(Exception):
    """Raised when a bearer token cannot be authenticated (-> HTTP 401)."""


REQUIRED_CLAIMS = ["iss", "sub", "aud", "exp", "iat", "jti", "client_id", "scope"]


def create_access_token(*, subject: str, client_id: str, scope: str) -> tuple[str, int]:
    """Return (signed token, expires_in_seconds).

    `subject` is the user id for user flows, or the client_id for
    client_credentials tokens (machine identity).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_in = settings.access_token_minutes * 60
    claims = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "aud": settings.jwt_audience,
        "exp": now + timedelta(seconds=expires_in),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "client_id": client_id,
        "scope": scope,
    }
    token = pyjwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """Strictly validate signature, algorithm, iss, aud, exp, iat and
    required claims. Any failure raises TokenError (mapped to 401)."""
    settings = get_settings()
    try:
        claims = pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],  # whitelist: rejects alg=none/substitution
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "jti"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except pyjwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    for claim in REQUIRED_CLAIMS:
        if claim not in claims:
            raise TokenError(f"missing required claim: {claim}")
    if not isinstance(claims["scope"], str):
        raise TokenError("invalid scope claim")
    return claims
