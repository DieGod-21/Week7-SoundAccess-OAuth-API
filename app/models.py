"""Database models.

Entities: users, oauth_clients, authorization_codes, tracks, playlists,
playlist_items.  Passwords and client secrets are stored only as Argon2
hashes — never in plaintext.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    playlists: Mapped[list["Playlist"]] = relationship(back_populates="owner")


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    client_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    # NULL for public clients (PKCE); Argon2 hash for confidential clients.
    client_secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "public" | "confidential"
    # Space-separated whitelists.
    redirect_uris: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    allowed_scopes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    allowed_grant_types: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def redirect_uri_list(self) -> list[str]:
        return self.redirect_uris.split()

    def scope_set(self) -> set[str]:
        return set(self.allowed_scopes.split())

    def grant_set(self) -> set[str]:
        return set(self.allowed_grant_types.split())


class AuthorizationCode(Base):
    __tablename__ = "authorization_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    # Only the SHA-256 hash of the code is stored; the raw value is returned
    # once to the client and cannot be recovered from the database.
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("oauth_clients.client_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(10), nullable=False, default="S256")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    artist: Mapped[str] = mapped_column(String(200), nullable=False)
    album: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)

    items: Mapped[list["PlaylistItem"]] = relationship(back_populates="track")


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="playlists")
    items: Mapped[list["PlaylistItem"]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    __table_args__ = (UniqueConstraint("playlist_id", "position"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlists.id"), nullable=False, index=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    playlist: Mapped[Playlist] = relationship(back_populates="items")
    track: Mapped[Track] = relationship(back_populates="items")
