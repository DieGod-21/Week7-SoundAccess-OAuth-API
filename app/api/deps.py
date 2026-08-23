"""Resource Server dependencies: bearer extraction, JWT validation and
scope/subject authorization.

401 -> the request could not be AUTHENTICATED (missing/malformed/invalid/
       expired token, wrong issuer or audience).
403 -> the token is valid but the subject is not AUTHORIZED (missing scope,
       machine token on a user-only endpoint, or foreign resource).
"""
import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import TokenError, decode_access_token

logger = logging.getLogger("soundaccess.auth")

WWW_AUTH = 'Bearer realm="soundaccess-api"'

# Task 3 introduces a second, dot-separated scope vocabulary
# (profile.read, playlists.read) used only by the legacy ROPC client, kept
# deliberately separate from Task 1's colon-separated scopes rather than
# renaming them (see docs/task3_gap_analysis.md — avoids any regression to
# the already-tested Task 1 contract). To avoid fragmenting authorization by
# "which grant issued the token", each Task 3 scope is treated as an
# authorization-equivalent alias of its Task 1 counterpart here, at the
# single point where scopes are enforced. The JWT `scope` claim itself is
# NOT rewritten — a ROPC token still literally carries "profile.read", as
# the assignment's example expects; only the *comparison* is alias-aware.
SCOPE_ALIASES: dict[str, set[str]] = {
    "profile:read": {"profile:read", "profile.read"},
    "playlist:read": {"playlist:read", "playlists.read"},
}


@dataclass
class AuthContext:
    claims: dict
    scopes: set[str]
    client_id: str
    subject: str

    @property
    def is_user_token(self) -> bool:
        """User tokens carry a user id as `sub`; client_credentials tokens
        carry the client_id itself (machine identity, RFC 9068 §2.2)."""
        return self.subject != self.client_id


def _unauthorized(description: str):
    raise HTTPException(
        status_code=401,
        detail={"error": "invalid_token", "error_description": description},
        headers={"WWW-Authenticate": f'{WWW_AUTH}, error="invalid_token"'},
    )


def _forbidden(description: str):
    raise HTTPException(
        status_code=403,
        detail={"error": "insufficient_scope", "error_description": description},
        headers={"WWW-Authenticate": f'{WWW_AUTH}, error="insufficient_scope"'},
    )


def get_auth_context(request: Request) -> AuthContext:
    """RFC 6750: the token is accepted ONLY from the Authorization header."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if not header:
        _unauthorized("missing bearer token")
    if scheme.lower() != "bearer" or not token.strip():
        _unauthorized("invalid authorization header")
    try:
        claims = decode_access_token(token.strip())
    except TokenError as exc:
        # Log the precise cause server-side; the client only gets a generic,
        # RFC 6750-style reason (never raw library/codec exception text).
        logger.info("bearer token rejected: %s", exc)
        _unauthorized("token is missing, malformed, expired, or fails signature/issuer/audience validation")
    return AuthContext(
        claims=claims,
        scopes=set(claims["scope"].split()),
        client_id=claims["client_id"],
        subject=claims["sub"],
    )


def require_scopes(*needed: str):
    """Dependency factory enforcing OAuth scopes on an endpoint.

    Each required scope is satisfied by itself OR by any of its aliases
    (see SCOPE_ALIASES) — so a Task 3 ROPC token carrying "profile.read"
    satisfies an endpoint declared as require_scopes("profile:read"), and
    vice versa.
    """

    def checker(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        missing = [
            scope for scope in needed
            if not (SCOPE_ALIASES.get(scope, {scope}) & ctx.scopes)
        ]
        if missing:
            _forbidden(f"required scope(s) missing: {' '.join(sorted(missing))}")
        return ctx

    return checker


def require_user(ctx: AuthContext, db: Session) -> User:
    """Endpoints tied to a person reject machine (client_credentials) tokens."""
    if not ctx.is_user_token:
        _forbidden("this endpoint requires a user token, not a service token")
    user = db.get(User, ctx.subject)
    if user is None:
        _unauthorized("token subject no longer exists")
    return user


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db
