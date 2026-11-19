---
title: Images
type: atlas-api
path: wiki/atlas/api/routers/images.md
category: api-atlas
order: 12
confidence: high
updated: 2026-08-11
tags: [type/api, domain/assets, status/active]
---

# Images — API

> Router: `backend/app/api/v1/images_router.py` — the
> image-asset store (asset-management roadmap Phase 1; images-only
> scope, other asset kinds later).
> Status: **ACTIVE** — the store behind the
> [[atlas/ui/pages/ImageManagement|Image Management]] page.

## Purpose

Manage the application's image assets: list, upload, delete
(orphan-protected), import/export (zip). The store is the
filesystem: `data/profile_images/` (gitignored, served at
`/static/` via the `StaticFiles` mount in `backend/app/main.py`).
No DB table — usage is derived by matching
`agents.profile_image_url`.

Curated assets (the 15 git-tracked images in `assets/agent-images/`)
are flagged `is_curated`; user uploads are uuid-named
(`img_<uuid>.png`) and never flagged.

## Endpoints

### List images

`GET /api/v1/images?page=1&page_size=50&curated=all&sort_by=filename&sort_dir=asc`

Returns `{ images: [...], total, page, page_size }`. Each image:

| Field | Meaning |
|---|---|
| `filename` | Store filename |
| `url` | `/static/<filename>` |
| `is_curated` | True when the file is one of the 15 canonical assets |
| `size` / `mime` / `created_at` | File metadata |
| `used_by` | `number[]` — agent ids whose `profile_image_url` references it |

**Query params (2026-08-11)**:

| Param | Values | Meaning |
|---|---|---|
| `curated` | `all` (default) / `true` / `false` | Filter BEFORE pagination — totals reflect the filter |
| `sort_by` | `filename` (default) / `size` / `created_at` / `mime` | Sort key, applied BEFORE pagination |
| `sort_dir` | `asc` (default) / `desc` | Direction; default = alphabetical |

### Upload

`POST /api/v1/images/upload?strip=false` (multipart `file`)

Validates content-type (`image/png|jpeg|gif|webp|svg+xml`) + size
(5MB), stores as `img_<uuid>.<ext>`. Returns
`{ filename, url, size }`. 201 on success.

**Dedup (2026-08-11)**: uploads are deduplicated by **pixel
fingerprint** (`app/domain/assets` — MD5 of PNG dimensions +
decompressed IDAT). Re-uploading the same image — including a
metadata-stripped copy with different bytes — reuses the existing
file instead of creating a duplicate uuid copy. Returns the
existing filename; no duplicate file is written.

**Strip metadata (2026-08-11)**: `strip=true` strips EXIF/ComfyUI
workflow metadata (tEXt/zTXt/iTXt/eXIf chunks) from PNGs before
storing, via `app/domain/assets.strip_metadata()`. Pixels/colors
untouched (critical + color chunks kept). The backend NEVER strips
silently — opt-in param, and the UI always reports the outcome.
JPEG/WebP pass through (need Pillow; none in store — tracked gap).

### Bulk upload

`POST /api/v1/images/upload-bulk?strip=false` (multipart `files`,
multiple)

Up to 50 files. Per-file validation + pixel dedup; never fails
wholesale. Returns:

```json
{ "added": [{"filename","url","size"}], "errors": [{"filename","reason"}],
  "total_requested": 3, "total_added": 2, "total_errors": 1 }
```

### Delete

`DELETE /api/v1/images/{filename}`

204 on success. **409 Conflict** when `used_by` is non-empty (an
agent references the image) — orphan protection. 404 when missing.

### Batch delete

`POST /api/v1/images/batch-delete` (body `{"filenames": [...]}`,
max 500)

Per-file results, never fails wholesale. In-use images → `failed`
with reason `in use by agent(s) [...]`; missing → `failed`; path
traversal → `failed`. Mirrors the Sessions bulk-delete shape:

```json
{ "deleted": ["a.png"], "failed": [{"filename":"b.png","reason":"in use by agent(s) [19]"}],
  "total_requested": 2, "total_deleted": 1, "total_failed": 1 }
```

### Restore curated

`POST /api/v1/images/restore-curated`

Re-copies the 15 canonical files from `assets/agent-images/` into
the store. **Additive-only** (2026-08-11 decision): uploads
untouched, existing files not overwritten, no agent rewiring, no
orphan removal. Idempotent — safe to click repeatedly. Returns
`{ restored: [...], skipped: N, total: N }`. 404 when the curated
directory is missing.

### Export (zip)

`POST /api/v1/images/export`

Streams a zip of all image files (`cogitate-images.zip`,
`application/zip`). 404 when the store is empty.

### Import (zip)

`POST /api/v1/images/import?strip=false` (multipart `file`, zip)

Extracts image files (png/jpeg/gif/webp/svg), skips non-images,
size-checks each. `strip=true` strips PNG metadata per file.
Returns `{ added: [...], added_count, errors: [...],
stripped_count }` — 201.

**Round-trip semantics (2026-08-11, user-caught bug)**: import
PRESERVES original filenames — it does NOT rename to `img_<uuid>`.
Export → delete → import restores the store exactly (agent URLs
reference canonical names like `/static/blondie.png`, so renaming
broke restore + left agent references 404). Pixel-deduped per
file, so re-importing an unchanged store adds nothing (idempotent
round-trip).

## Related

- [[atlas/ui/pages/ImageManagement|Image Management]] (the UI)
- [[atlas/ui/services/domains/llm/imageService|imageService]]
- [[dev-notes/assets/agent-images|Agent Images — canonical home]]
- `scripts/core/seed_agent_images.py` (curated seeding + remap)
