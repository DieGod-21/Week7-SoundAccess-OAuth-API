"""Pydantic request/response schemas with strict input validation."""
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# Task 1 scopes (colon-separated), enforced across Authorization Code + PKCE
# and Client Credentials.
TASK1_SCOPES = {"catalog:read", "profile:read", "playlist:read", "playlist:write"}
# Task 3 scopes (dot-separated), used exclusively by the legacy ROPC client
# and request examples exactly as specified in the Task 3 assignment. Kept
# as a distinct, additive vocabulary rather than renaming Task 1's scopes,
# to avoid any regression risk (see docs/task3_gap_analysis.md). The
# Resource Server treats each Task 3 scope as an alias of its Task 1
# equivalent for authorization purposes (app/api/deps.py::SCOPE_ALIASES),
# while the JWT `scope` claim itself still reflects exactly what was granted.
TASK3_ROPC_SCOPES = {"profile.read", "playlists.read"}
VALID_SCOPES = TASK1_SCOPES | TASK3_ROPC_SCOPES
CLIENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,79}$")


# ----- OAuth client registration (POST /oauth/clients) --------------------
class ClientRegistrationRequest(BaseModel):
    client_id: str = Field(min_length=3, max_length=80)
    client_name: str = Field(min_length=3, max_length=100)
    client_type: str
    redirect_uris: list[str] = Field(default_factory=list, max_length=5)
    allowed_scopes: list[str] = Field(min_length=1, max_length=10)
    allowed_grant_types: list[str] = Field(min_length=1, max_length=3)

    @field_validator("client_id")
    @classmethod
    def _client_id_format(cls, v: str) -> str:
        if not CLIENT_ID_RE.fullmatch(v):
            raise ValueError("client_id must match ^[a-z0-9][a-z0-9-]{2,79}$")
        return v

    @field_validator("client_type")
    @classmethod
    def _client_type(cls, v: str) -> str:
        if v not in {"public", "confidential"}:
            raise ValueError("client_type must be 'public' or 'confidential'")
        return v

    @field_validator("redirect_uris")
    @classmethod
    def _redirect_uris(cls, v: list[str]) -> list[str]:
        for uri in v:
            if not (uri.startswith("https://") or uri.startswith("http://localhost")
                    or uri.startswith("http://127.0.0.1")):
                raise ValueError("redirect URIs must be https:// (or localhost for development)")
            if "#" in uri or len(uri) > 500:
                raise ValueError("invalid redirect URI")
        return v

    @field_validator("allowed_scopes")
    @classmethod
    def _scopes(cls, v: list[str]) -> list[str]:
        unknown = set(v) - VALID_SCOPES
        if unknown:
            raise ValueError(f"unknown scopes: {sorted(unknown)}")
        return v

    @field_validator("allowed_grant_types")
    @classmethod
    def _grants(cls, v: list[str]) -> list[str]:
        allowed = {"authorization_code", "client_credentials"}
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"unsupported grant types: {sorted(unknown)}")
        return v


class ClientRegistrationResponse(BaseModel):
    client_id: str
    client_name: str
    client_type: str
    redirect_uris: list[str]
    allowed_scopes: list[str]
    allowed_grant_types: list[str]
    client_secret: str | None = None  # returned ONCE for confidential clients


# ----- Token endpoint -----------------------------------------------------
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


# ----- Resource API -------------------------------------------------------
class TrackOut(BaseModel):
    id: str
    title: str
    artist: str
    album: str
    duration_seconds: int
    genre: str

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    display_name: str

    model_config = {"from_attributes": True}


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    track_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()

    @field_validator("track_ids")
    @classmethod
    def _track_id_format(cls, v: list[str]) -> list[str]:
        for tid in v:
            if not re.fullmatch(r"[0-9a-f]{32}", tid):
                raise ValueError("invalid track id format")
        return v


class PlaylistItemOut(BaseModel):
    position: int
    track: TrackOut


class PlaylistOut(BaseModel):
    id: str
    name: str
    description: str
    owner_username: str
    items: list[PlaylistItemOut]
