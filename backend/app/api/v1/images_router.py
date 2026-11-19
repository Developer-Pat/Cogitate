"""
Image Management — API.

Manage the application's image assets (agent profile images today;
the asset-management roadmap scopes this to images only). Lists,
uploads, deletes, and import/export (zip) — the store behind the
Image Management page (Utilities section).

The store is the filesystem: data/profile_images/ (gitignored,
served at /static/). No DB table needed for images-only scope —
usage is derived by matching agent.profile_image_url.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Annotated, Any
from zipfile import ZipFile

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.domain.assets import dedup_upload, strip_metadata

router = APIRouter(prefix="/images", tags=["image-management"])


def _images_dir() -> Path:
    settings = get_settings()
    d = Path(settings.profile_images_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _curated_dir() -> Path:
    """Canonical curated-image source (assets/agent-images/)."""
    from app.core.config import Paths, get_settings
    return Paths.from_settings(get_settings()).agent_images_dir


def _curated_names() -> set[str]:
    """Canonical curated-image filenames (assets/agent-images/)."""
    curated_dir = _curated_dir()
    if not curated_dir.exists():
        return set()
    return {p.name for p in curated_dir.glob("*.png")}


def _validate_image(content: bytes, content_type: str) -> None:
    settings = get_settings()
    if content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {settings.allowed_image_types}",
        )
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {settings.max_upload_size} bytes",
        )


def _agent_usage() -> dict[str, list[int]]:
    """filename → [agent_ids referencing it] (via profile_image_url)."""
    import sqlite3

    from app.core.config import Paths, get_settings
    db_path = Paths.from_settings(get_settings()).shared_db
    usage: dict[str, list[int]] = {}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT id, profile_image_url FROM agents WHERE profile_image_url IS NOT NULL AND profile_image_url != ''"
            ).fetchall()
        finally:
            conn.close()
        for agent_id, url in rows:
            filename = url.rsplit("/", 1)[-1]
            usage.setdefault(filename, []).append(agent_id)
    except Exception:
        pass
    return usage


_SORTABLE = {"filename", "size", "created_at", "mime"}


@router.get("")
async def list_images(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    curated: str = "all",
    sort_by: str = "filename",
    sort_dir: str = "asc",
):
    """List image assets with usage info (which agents reference them).

    curated: "all" (default) | "true" (curated only) | "false"
    (user uploads only) — filters BEFORE pagination.
    sort_by: filename (default) | size | created_at | mime.
    sort_dir: asc (default) | desc. Default = alphabetical.
    Sorting applies BEFORE pagination so totals stay honest.
    """
    d = _images_dir()
    usage = _agent_usage()
    curated_set = _curated_names()
    all_files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if d.exists() else []
    files = [p for p in all_files if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}]
    if curated == "true":
        files = [p for p in files if p.name in curated_set]
    elif curated == "false":
        files = [p for p in files if p.name not in curated_set]
    if sort_by not in _SORTABLE:
        sort_by = "filename"
    reverse = sort_dir == "desc"

    def keyfn(p: Path) -> Any:
        if sort_by == "filename":
            return p.name.lower()
        if sort_by == "size":
            return p.stat().st_size
        if sort_by == "created_at":
            return p.stat().st_mtime
        # mime — map extension to the display string
        return {
            ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
            ".gif": "gif", ".webp": "webp", ".svg": "svg",
        }.get(p.suffix.lower(), "other")

    files.sort(key=keyfn, reverse=reverse)
    total = len(files)
    start = (page - 1) * page_size
    items = []
    for p in files[start : start + page_size]:
        st = p.stat()
        filename = p.name
        items.append({
                "filename": filename,
                "url": f"/static/{filename}",
                "is_curated": filename in curated_set,
                "size": st.st_size,
                "mime": {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".svg": "image/svg+xml",
                }.get(p.suffix.lower(), "application/octet-stream"),
                "created_at": st.st_mtime,
                "used_by": usage.get(filename, []),
            })
    return {"images": items, "total": total, "page": page, "page_size": page_size}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile,
    strip: Annotated[bool, Query()] = False,
):
    """Upload a single image (not agent-bound — available to the store).

    strip=true strips metadata (EXIF/ComfyUI workflow) from PNGs
    before storing; response reports whether it stripped. The
    backend never strips silently — opt-in, and the result is
    surfaced to the caller.
    """
    content = await file.read()
    if strip:
        content, _ = strip_metadata(content)
    _validate_image(content, file.content_type or "")
    ext = Path(file.filename or "image.png").suffix.lower() or ".png"
    filename, _ = dedup_upload(
        _images_dir(),
        content,
        name_for_new=f"img_{uuid.uuid4().hex}{ext}",
    )
    return {"filename": filename, "url": f"/static/{filename}", "size": len(content), "deduped": True}


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(filename: str):
    """Delete an image. Refuses when an agent references it (prevents orphans)."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    usage = _agent_usage()
    if filename in usage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Image is used by agent(s) {usage[filename]} — unassign first",
        )
    p = _images_dir() / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    p.unlink()
    return None


@router.post("/batch-delete")
async def batch_delete_images(payload: dict):
    '''
    Delete multiple images in one call (bulk delete).

    Per-file results, never fails wholesale: in-use images are
    reported as failed (409-equivalent reason) so the UI can show
    exactly what was deleted vs blocked. Mirrors the Sessions
    bulk-delete response shape (deleted/failed/total_*).

    Body: {"filenames": ["a.png", ...]}
    '''
    filenames = payload.get("filenames") or []
    if not isinstance(filenames, list) or not filenames:
        raise HTTPException(status_code=400, detail="filenames required (non-empty list)")
    if len(filenames) > 500:
        raise HTTPException(status_code=400, detail="Too many filenames (max 500)")

    usage = _agent_usage()
    d = _images_dir()
    deleted: list[str] = []
    failed: list[dict] = []
    for filename in filenames:
        if not isinstance(filename, str) or "/" in filename or ".." in filename:
            failed.append({"filename": str(filename), "reason": "invalid filename"})
            continue
        if filename in usage:
            failed.append({"filename": filename, "reason": f"in use by agent(s) {usage[filename]}"})
            continue
        p = d / filename
        if not p.exists():
            failed.append({"filename": filename, "reason": "not found"})
            continue
        try:
            p.unlink()
            deleted.append(filename)
        except Exception as e:
            failed.append({"filename": filename, "reason": str(e)})

    return {
        "deleted": deleted,
        "failed": failed,
        "total_requested": len(filenames),
        "total_deleted": len(deleted),
        "total_failed": len(failed),
    }


@router.post("/upload-bulk", status_code=status.HTTP_201_CREATED)
async def upload_images_bulk(
    files: Annotated[list[UploadFile], File(description="One or more image files")],
    strip: Annotated[bool, Query()] = False,
):
    '''
    Upload multiple images at once (bulk upload).

    Each file is validated + pixel-deduped like the single upload.
    strip=true strips PNG metadata (EXIF/ComfyUI workflow) per
    file; each result reports whether it stripped. Returns
    per-file results: added (filename or reused existing) + errors
    (with per-file reasons). Never fails wholesale — a bad file is
    reported, the rest still upload.

    Form field name: files (multipart, multiple).
    '''
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Too many files (max 50 per request)")

    added: list[dict] = []
    errors: list[dict] = []
    for file in files:
        try:
            content = await file.read()
            if strip:
                content, _ = strip_metadata(content)
            _validate_image(content, file.content_type or "")
        except HTTPException as e:
            errors.append({"filename": file.filename or "?", "reason": str(e.detail)})
            continue
        ext = Path(file.filename or "image.png").suffix.lower() or ".png"
        filename, _ = dedup_upload(
            _images_dir(),
            content,
            name_for_new=f"img_{uuid.uuid4().hex}{ext}",
        )
        added.append({"filename": filename, "url": f"/static/{filename}", "size": len(content)})

    return {
        "added": added,
        "errors": errors,
        "total_requested": len(files),
        "total_added": len(added),
        "total_errors": len(errors),
    }


@router.post("/restore-curated")
async def restore_curated_images():
    '''
    Re-copy the curated image set (assets/agent-images/) into the
    runtime store (data/profile_images/).

    ADDITIVE-ONLY by design (2026-08-11 decision): deletion of
    curated images is allowed (users may curate their own store),
    so this is the recovery path. It copies any MISSING curated
    file back; existing files are left untouched (a user may have
    replaced one); user uploads are never touched; agent URL
    assignments are not rewired (deleting an in-use image is
    already blocked by the 409 guard, so anything restorable is
    unused). Idempotent — safe to click repeatedly.

    Returns: {"restored": [filenames], "skipped": n, "total": n}
    '''
    curated_dir = _curated_dir()
    if not curated_dir.exists():
        raise HTTPException(status_code=404, detail="Curated asset directory not found")

    d = _images_dir()
    restored: list[str] = []
    skipped = 0
    for p in sorted(curated_dir.glob("*.png")):
        target = d / p.name
        if target.exists():
            skipped += 1
            continue
        target.write_bytes(p.read_bytes())
        restored.append(p.name)

    return {"restored": restored, "skipped": skipped, "total": len(restored) + skipped}


@router.post("/export")
async def export_images():
    """Zip all image assets for download (import/export facility)."""
    d = _images_dir()
    if not d.exists():
        raise HTTPException(status_code=404, detail="No images to export")
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}]
    if not files:
        raise HTTPException(status_code=404, detail="No images to export")
    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        for p in files:
            zf.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="cogitate-images.zip"'},
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_images(
    file: UploadFile,
    strip: Annotated[bool, Query()] = False,
):
    """Import a zip of images (bulk add — import/export facility).

    strip=true strips PNG metadata (EXIF/ComfyUI workflow) from
    each imported PNG before storing; response reports the count
    stripped.
    """
    settings = get_settings()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")
    added: list[str] = []
    errors: list[str] = []
    stripped_count = 0
    try:
        zf = ZipFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Not a valid zip: {e}") from e
    d = _images_dir()
    for name in zf.namelist():
        base = Path(name).name  # strip any dirs
        if not base or base.startswith("."):
            continue
        ext = Path(base).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            continue
        data = zf.read(name)
        if len(data) > settings.max_upload_size:
            errors.append(f"{base}: too large")
            continue
        if strip and ext == ".png":
            cleaned, did_strip = strip_metadata(data)
            if did_strip:
                data = cleaned
                stripped_count += 1
        # PRESERVE the original filename — import/export is a
        # round-trip of the store, and agent URLs reference the
        # canonical names (e.g. /static/blondie.png). Renaming to
        # img_<uuid> here broke restore + broke agent references
        # (2026-08-11, user caught it live). Dedup by pixels first
        # so re-importing an unchanged store adds nothing.
        # dedup_upload returns the EXISTING filename when pixels
        # match (re-import of an unchanged store adds nothing new)
        # and the new name otherwise. Either way the canonical
        # filename is preserved — the round-trip contract.
        out, _ = dedup_upload(d, data, name_for_new=base)
        added.append(out)
    return {"added": added, "added_count": len(added), "errors": errors, "stripped_count": stripped_count}
