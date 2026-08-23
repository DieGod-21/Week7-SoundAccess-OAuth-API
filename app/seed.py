"""Idempotent development seed data.

Creates: three demo users, one public PKCE client (web-user-client), one
confidential service client (music-service-client), one confidential legacy
ROPC client (legacy-client, Task 3), fictitious tracks and example
playlists. Demo credentials come from the environment
(SOUNDACCESS_SEED_USER_PASSWORD / SOUNDACCESS_SEED_SERVICE_SECRET /
SOUNDACCESS_SEED_LEGACY_CLIENT_SECRET) so no secret lives in source code or
Git.
"""
from sqlalchemy.orm import Session

from .config import get_settings
from .models import OAuthClient, Playlist, PlaylistItem, Track, User
from .security import hash_secret

SCOPES_ALL = "catalog:read profile:read playlist:read playlist:write"
SERVICE_SCOPES = "catalog:read"
# Task 3: ROPC is a legacy flow used strictly for controlled comparison, so
# the legacy client is deliberately restricted to a minimal read-only scope
# set (no playlist:write-equivalent) — it cannot do anything a compromised
# password grant shouldn't be able to do.
LEGACY_ROPC_SCOPES = "profile.read playlists.read"

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
    legacy_client_secret = settings.seed_legacy_client_secret or "changeme-legacy"

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
    # Task 3: fictitious user used exclusively to demonstrate/exercise the
    # legacy ROPC grant, kept distinct from the Task 1 PKCE demo users.
    alumno = User(
        username="alumno.demo",
        email="alumno.demo@example.com",
        password_hash=hash_secret(user_password),
        display_name="Alumno Demo",
    )
    db.add_all([ana, bruno, alumno])

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
    # Task 3 — legacy ROPC client. Confidential (must present client_secret),
    # authorized ONLY for grant_type=password, and restricted to a minimal
    # read-only scope set. Never registrable through POST /oauth/clients —
    # provisioned only here, in the trusted seed process (see
    # docs/task3_gap_analysis.md for the rationale).
    legacy_client = OAuthClient(
        client_id="legacy-client",
        client_secret_hash=hash_secret(legacy_client_secret),
        client_name="SoundAccess Legacy Integration (ROPC — laboratory use only)",
        client_type="confidential",
        redirect_uris="",
        allowed_scopes=LEGACY_ROPC_SCOPES,
        allowed_grant_types="password",
    )
    db.add_all([web_client, service_client, legacy_client])

    tracks = [
        Track(title=t, artist=a, album=al, duration_seconds=d, genre=g)
        for (t, a, al, d, g) in TRACKS
    ]
    db.add_all(tracks)
    db.flush()

    p1 = Playlist(name="Estudio nocturno", description="Para concentrarse", owner=ana)
    p2 = Playlist(name="Ruta a la U", description="Camino a clases", owner=bruno)
    p3 = Playlist(name="Legacy Mix", description="Playlist de demostración ROPC", owner=alumno)
    db.add_all([p1, p2, p3])
    db.flush()
    db.add_all(
        [
            PlaylistItem(playlist_id=p1.id, track_id=tracks[0].id, position=1),
            PlaylistItem(playlist_id=p1.id, track_id=tracks[4].id, position=2),
            PlaylistItem(playlist_id=p2.id, track_id=tracks[2].id, position=1),
            PlaylistItem(playlist_id=p2.id, track_id=tracks[6].id, position=2),
            PlaylistItem(playlist_id=p3.id, track_id=tracks[1].id, position=1),
        ]
    )
    db.commit()
    return {
        "status": "seeded",
        "users": ["ana", "bruno", "alumno.demo"],
        "clients": ["web-user-client", "music-service-client", "legacy-client"],
        "tracks": len(tracks),
        "playlists": 3,
    }
