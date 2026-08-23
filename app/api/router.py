"""Protected Resource Server (music catalog, profile, playlists).

Every endpoint declares the OAuth scope it enforces; ownership of private
playlists is additionally verified against the token subject.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Playlist, PlaylistItem, Track
from ..schemas import PlaylistCreate, PlaylistOut, ProfileOut, TrackOut
from .deps import AuthContext, require_scopes, require_user

router = APIRouter(prefix="/api", tags=["Resource Server (protected API)"])


def _playlist_out(p: Playlist) -> PlaylistOut:
    return PlaylistOut(
        id=p.id,
        name=p.name,
        description=p.description,
        owner_username=p.owner.username,
        items=[
            {"position": i.position, "track": TrackOut.model_validate(i.track)}
            for i in sorted(p.items, key=lambda i: i.position)
        ],
    )


@router.get(
    "/catalog/tracks",
    response_model=list[TrackOut],
    summary="List the music catalog (scope: catalog:read)",
)
def list_tracks(
    ctx: AuthContext = Depends(require_scopes("catalog:read")),
    db: Session = Depends(get_db),
):
    return db.query(Track).order_by(Track.artist, Track.album, Track.title).all()


@router.get(
    "/me",
    response_model=ProfileOut,
    summary="Authenticated user's profile (scope: profile:read, user token only)",
)
def read_profile(
    ctx: AuthContext = Depends(require_scopes("profile:read")),
    db: Session = Depends(get_db),
):
    # Service tokens are valid credentials but are NOT authorized here (403).
    user = require_user(ctx, db)
    return user


@router.post(
    "/playlists",
    response_model=PlaylistOut,
    status_code=201,
    summary="Create a playlist owned by the authenticated user (scope: playlist:write)",
)
def create_playlist(
    body: PlaylistCreate,
    ctx: AuthContext = Depends(require_scopes("playlist:write")),
    db: Session = Depends(get_db),
):
    user = require_user(ctx, db)
    playlist = Playlist(name=body.name, description=body.description, owner_id=user.id)
    db.add(playlist)
    db.flush()
    for position, track_id in enumerate(body.track_ids, start=1):
        track = db.get(Track, track_id)
        if track is None:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"unknown track id: {track_id}")
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=track.id, position=position))
    db.commit()
    db.refresh(playlist)
    return _playlist_out(playlist)


@router.get(
    "/playlists/{playlist_id}",
    response_model=PlaylistOut,
    summary="Read an owned playlist (scope: playlist:read)",
)
def read_playlist(
    playlist_id: str = Path(pattern=r"^[0-9a-f]{32}$"),
    ctx: AuthContext = Depends(require_scopes("playlist:read")),
    db: Session = Depends(get_db),
):
    user = require_user(ctx, db)
    playlist = (
        db.query(Playlist)
        .options(joinedload(Playlist.items).joinedload(PlaylistItem.track))
        .filter(Playlist.id == playlist_id)
        .first()
    )
    # 404 for both "does not exist" and "not yours": the response must not
    # reveal whether another user's private playlist exists (no data leak).
    if playlist is None or playlist.owner_id != user.id:
        raise HTTPException(status_code=404, detail="playlist not found")
    return _playlist_out(playlist)


@router.delete(
    "/playlists/{playlist_id}",
    status_code=204,
    summary="Delete an owned playlist (scope: playlist:write)",
)
def delete_playlist(
    playlist_id: str = Path(pattern=r"^[0-9a-f]{32}$"),
    ctx: AuthContext = Depends(require_scopes("playlist:write")),
    db: Session = Depends(get_db),
):
    user = require_user(ctx, db)
    playlist = db.get(Playlist, playlist_id)
    if playlist is None or playlist.owner_id != user.id:
        raise HTTPException(status_code=404, detail="playlist not found")
    db.delete(playlist)
    db.commit()
