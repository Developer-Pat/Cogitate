"""THE SOUNDS DOMAIN (2026-08-30, the F1 extraction of the
architecture-fit review): the business rules for the notification-
sound assets — the resolvers, the content-hash dedup, the
validation, the configured-guard, the catalog, the curated restore.

The API layer (sounds_router) calls here and maps the domain errors
to HTTP; the domain knows nothing about HTTP. The store is the
filesystem: data/notification-sounds/ (gitignored, served through
the API — the /sounds static mount collided with the SPA route).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Paths, get_settings


class SoundValidationError(Exception):
    """The uploaded bytes fail the allowlist or the size cap."""


class SoundNotFoundError(Exception):
    """No such sound in the runtime store."""


class InvalidSoundFilenameError(Exception):
    """Path-traversal garbage in a filename."""


class ConfiguredSoundError(Exception):
    """The configured notification sound cannot be deleted."""


class CuratedAssetsMissingError(Exception):
    """The canonical curated-sound source does not exist."""


def sounds_dir() -> Path:
    settings = get_settings()
    d = Paths.from_settings(settings).notification_sounds_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def curated_dir() -> Path:
    """Canonical curated-sound source (assets/notification-sounds/)."""
    return Paths.from_settings(get_settings()).curated_sounds_dir


def curated_names() -> set[str]:
    """Canonical curated-sound filenames (assets/notification-sounds/)."""
    d = curated_dir()
    if not d.exists():
        return set()
    return {p.name for p in d.glob("*.wav")}


def sound_dedup(store_dir: Path, data: bytes, name_for_new: str) -> str:
    """Content-hash dedup (the images' dedup is PNG-pixel-specific;
    sounds dedupe by the raw bytes). Returns the stored filename —
    the existing file when the bytes match, the new write otherwise."""
    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    if store_dir.exists():
        for p in store_dir.iterdir():
            if not p.is_file() or p.suffix.lower() != ".wav":
                continue
            try:
                if hashlib.sha256(p.read_bytes()).hexdigest() == digest:
                    return p.name
            except Exception:
                continue
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / name_for_new).write_bytes(data)
    return name_for_new


def validate_sound(content: bytes, content_type: str) -> None:
    """The allowlist + the size cap (the upload gate)."""
    settings = get_settings()
    if content_type not in settings.allowed_sound_types:
        raise SoundValidationError(
            f"Invalid file type. Allowed: {settings.allowed_sound_types}"
        )
    if len(content) > settings.max_sound_upload_size:
        raise SoundValidationError(
            f"File too large. Max size: {settings.max_sound_upload_size} bytes"
        )


def configured_sound_id() -> str | None:
    """The notifications config's sound_id (sync sqlite read — the
    delete guard's source; mirrors the images' _agent_usage pattern)."""
    import json
    import sqlite3

    from app.core.config import Paths as P, get_settings as gs

    db_path = P.from_settings(gs()).shared_db
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT settings FROM user_settings WHERE user_key = 'default'"
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        blob = json.loads(row[0])
        cfg = blob.get("notifications") or {}
        return cfg.get("sound_id") if isinstance(cfg, dict) else None
    except Exception:
        return None


def sound_exists(filename: str) -> bool:
    """The notifications config's sound_id validation — the router
    used to reach INTO the API layer for this; the domain owns it."""
    return (sounds_dir() / filename).is_file()


def resolve_sound_path(filename: str) -> Path:
    """The traversal-guarded path resolution (the file serving)."""
    if "/" in filename or ".." in filename:
        raise InvalidSoundFilenameError("Invalid filename")
    p = sounds_dir() / filename
    if not p.exists():
        raise SoundNotFoundError("Sound not found")
    return p


def list_sounds(
    page: int = 1,
    page_size: int = 50,
    curated: str = "all",
    sort_by: str = "filename",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    """The catalog query: filter (all/curated/uploads) + sort +
    paginate + the item shape (the configured flag included)."""
    d = sounds_dir()
    configured = configured_sound_id()
    curated_set = curated_names()
    all_files = (
        sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if d.exists()
        else []
    )
    files = [p for p in all_files if p.is_file() and p.suffix.lower() == ".wav"]
    if curated == "true":
        files = [p for p in files if p.name in curated_set]
    elif curated == "false":
        files = [p for p in files if p.name not in curated_set]
    if sort_by not in {"filename", "size", "created_at"}:
        sort_by = "filename"
    reverse = sort_dir == "desc"

    def keyfn(p: Path) -> Any:
        if sort_by == "size":
            return p.stat().st_size
        if sort_by == "created_at":
            return p.stat().st_mtime
        return p.name.lower()

    files.sort(key=keyfn, reverse=reverse)
    total = len(files)
    start = (page - 1) * page_size
    items = []
    for p in files[start : start + page_size]:
        st = p.stat()
        items.append(
            {
                "filename": p.name,
                "url": f"/api/v1/sounds/{p.name}/file",
                "is_curated": p.name in curated_set,
                "is_configured": p.name == configured,
                "size": st.st_size,
                "mime": "audio/wav",
                "created_at": st.st_mtime,
            }
        )
    return {"sounds": items, "total": total, "page": page, "page_size": page_size}


def restore_curated_sounds() -> dict[str, Any]:
    """Re-copy the curated set into the runtime store. ADDITIVE-ONLY
    (the images' doctrine): copies any MISSING curated file back;
    existing files + user uploads are never touched. Idempotent."""
    d = curated_dir()
    if not d.exists():
        raise CuratedAssetsMissingError("Curated asset directory not found")
    store = sounds_dir()
    restored: list[str] = []
    skipped = 0
    for p in sorted(d.glob("*.wav")):
        target = store / p.name
        if target.exists():
            skipped += 1
            continue
        target.write_bytes(p.read_bytes())
        restored.append(p.name)
    return {"restored": restored, "skipped": skipped, "total": len(restored) + skipped}
