"""
Sound Management — API (thin, 2026-08-30 the F1 extraction).

Manage the application's notification-sound assets (the wav-assets:
a tiny gentle-ping WAV ~50KB + uploads — the assets-catalog pattern
mirrors the images store). Lists, uploads, deletes, and the curated
restore — the store behind the Sounds page (Assets section).

The BUSINESS RULES live in app/domain/messaging/sounds.py — this
router calls them and maps the domain errors to HTTP.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.domain.messaging import sounds

router = APIRouter(prefix="/sounds", tags=["sound-management"])


@router.get("")
async def list_sounds(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    curated: str = "all",
    sort_by: str = "filename",
    sort_dir: str = "asc",
):
    """List sound assets with the configured-flag (the notification
    sound reference). curated: "all" | "true" | "false". Sorting +
    pagination before the totals, like the images store."""
    return sounds.list_sounds(page, page_size, curated, sort_by, sort_dir)


@router.get("/{filename}/file")
async def serve_sound(filename: str):
    """Serve a sound's bytes (the Audio API's URL — through the
    API base, not a static mount: the /sounds mount collided with
    the SPA page route). Path-traversal guarded."""
    try:
        p = sounds.resolve_sound_path(filename)
    except sounds.InvalidSoundFilenameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except sounds.SoundNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    # NO-CACHE (2026-08-30, the stale-sound confusion): the files are
    # tiny + mutable (the curated seeds regenerate) — the browser's
    # media cache served the OLD bytes after a regen. Always
    # revalidate; the etag/last-modified still allow a 304.
    return FileResponse(
        p,
        media_type="audio/wav",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_sound(file: UploadFile):
    """Upload a single sound (validated audio/wav + size-capped,
    content-deduped like the images)."""
    content = await file.read()
    try:
        sounds.validate_sound(content, file.content_type or "")
    except sounds.SoundValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = sounds.sound_dedup(
        sounds.sounds_dir(),
        content,
        f"snd_{uuid.uuid4().hex}.wav",
    )
    return {"filename": filename, "url": f"/api/v1/sounds/{filename}/file", "size": len(content)}


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sound(filename: str):
    """Delete a sound. Refuses the configured notification sound
    (prevents a silent mute) + path-traversal garbage."""
    try:
        p = sounds.resolve_sound_path(filename)
    except sounds.InvalidSoundFilenameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except sounds.SoundNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if filename == sounds.configured_sound_id():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is the configured notification sound — pick another sound first",
        )
    p.unlink()
    return None


@router.post("/restore-curated")
async def restore_curated_sounds():
    """Re-copy the curated sound set (assets/notification-sounds/)
    into the runtime store. ADDITIVE-ONLY (the images' doctrine):
    copies any MISSING curated file back; existing files + user
    uploads are never touched. Idempotent."""
    try:
        return sounds.restore_curated_sounds()
    except sounds.CuratedAssetsMissingError as e:
        raise HTTPException(status_code=404, detail=str(e))
