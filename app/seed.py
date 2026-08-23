"""Idempotent development seed data.

Creates: two demo users, one public PKCE client (web-user-client), one
confidential service client (music-service-client), fictitious tracks and
example playlists.  Demo credentials come from the environment
(SOUNDACCESS_SEED_USER_PASSWORD / SOUNDACCESS_SEED_SERVICE_SECRET) so no
secret lives in source code or Git.
"""
from sqlalchemy.orm import Session

from .config import get_settings
from .models import OAuthClient, Playlist, PlaylistItem, Track, User
from .security import hash_secret

SCOPES_ALL = "catalog:read profile:read playlist:read playlist:write"
SERVICE_SCOPES = "catalog:read"

TRACKS = [
    ("Neon Rivers", "Cassette Foxes", "Midnight Atlas", 214, "Synthpop"),
    ("Paper Planets", "Cassette Foxes", "Midnight Atlas", 187, "Synthpop"),
    ("Cumbia del Volcán", "Marimba Norte", "Tierra Viva", 243, "Cumbia"),
    ("Antigua al Amanecer", "Marimba Norte", "Tierra Viva", 198, "Folk"),
    ("Static Bloom", "Velvet Circuit", "Low Orbit", 276, "Electronic"),
    ("Gravity Well", "Velvet Circuit", "Low Orbit", 231, "Electronic"),
    ("Last Bus Home", "The Umbral Days", "Streetlight Letters", 205, "Indie Rock"),
    ("Ink & Amber", "The Umbral Days", "Streetlight Letters", 222, "Indie Rock"),
]


def seed(db: Session) -> dict:
    """Populate the database if empty. Returns a summary dict."""
    settings = get_settings()
    if db.query(User).count() > 0:
        return {"status": "already-seeded"}

    user_password = settings.seed_user_password or "changeme-demo"
    service_secret = settings.seed_service_secret or "changeme-service"

    ana = User(
        username="ana",
        email="ana@example.com",
        password_hash=hash_secret(user_password),
        display_name="Ana Morales",
    )
    bruno = User(
        username="bruno",
        email="bruno@example.com",
        password_hash=hash_secret(user_password),
        display_name="Bruno Castillo",
    )
    db.add_all([ana, bruno])

    web_client = OAuthClient(
        client_id="web-user-client",
        client_secret_hash=None,  # public client -> PKCE mandatory
        client_name="SoundAccess Web Player",
        client_type="public",
        redirect_uris="http://127.0.0.1:8000/client/callback http://localhost:8000/client/callback",
        allowed_scopes=SCOPES_ALL,
        allowed_grant_types="authorization_code",
    )
    service_client = OAuthClient(
        client_id="music-service-client",
        client_secret_hash=hash_secret(service_secret),
        client_name="SoundAccess Catalog Sync Service",
        client_type="confidential",
        redirect_uris="",
        allowed_scopes=SERVICE_SCOPES,
        allowed_grant_types="client_credentials",
    )
    db.add_all([web_client, service_client])

    tracks = [
        Track(title=t, artist=a, album=al, duration_seconds=d, genre=g)
        for (t, a, al, d, g) in TRACKS
    ]
    db.add_all(tracks)
    db.flush()

    p1 = Playlist(name="Estudio nocturno", description="Para concentrarse", owner=ana)
    p2 = Playlist(name="Ruta a la U", description="Camino a clases", owner=bruno)
    db.add_all([p1, p2])
    db.flush()
    db.add_all(
        [
            PlaylistItem(playlist_id=p1.id, track_id=tracks[0].id, position=1),
            PlaylistItem(playlist_id=p1.id, track_id=tracks[4].id, position=2),
            PlaylistItem(playlist_id=p2.id, track_id=tracks[2].id, position=1),
            PlaylistItem(playlist_id=p2.id, track_id=tracks[6].id, position=2),
        ]
    )
    db.commit()
    return {
        "status": "seeded",
        "users": ["ana", "bruno"],
        "clients": ["web-user-client", "music-service-client"],
        "tracks": len(tracks),
        "playlists": 2,
    }
