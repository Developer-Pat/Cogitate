---
title: imageService
type: atlas-service
path: frontend/src/services/domains/llm/imageService.ts
confidence: high
updated: 2026-08-11
tags: [type/service, domain/atlas-ui]
---

# imageService

**File**: `frontend/src/services/domains/llm/imageService.ts`
**Last Updated**: 2026-08-11

## Purpose

The API client for the image-asset store — the only service used by
the [[atlas/ui/pages/ImageManagement|Image Management]] page
(page → service, no hook layer needed for a single surface).

## API

| Method | Endpoint | Returns |
|---|---|---|
| `listImages(page, pageSize, curated, sortBy, sortDir)` | `GET /api/v1/images` | `ImageListResponse` (`images[]`, `total`, `page`, `page_size`) — curated filter + sort applied server-side (2026-08-11) |
| `uploadImage(file, strip?)` | `POST /api/v1/images/upload?strip=` | `ImageUploadResult` (`filename`, `url`, `size`) — deduped by pixel fingerprint; optional metadata strip |
| `uploadImagesBulk(files[], strip?)` | `POST /api/v1/images/upload-bulk?strip=` | `BulkUploadResult` (`added[]`, `errors[]`, `total_*`) |
| `batchDelete(filenames[])` | `POST /api/v1/images/batch-delete` | `BatchDeleteResult` (`deleted[]`, `failed[]` with reasons, `total_*`) |
| `restoreCurated()` | `POST /api/v1/images/restore-curated` | `{ restored[], skipped, total }` |
| `deleteImage(filename)` | `DELETE /api/v1/images/{filename}` | void (409 if in use) |
| `importZip(file, strip?)` | `POST /api/v1/images/import?strip=` | `ImageImportResult` (`added[]`, `added_count`, `errors[]`, `stripped_count`) |
| export | `POST /api/v1/images/export` | zip blob (fetched directly in the page, not via this service) |

## Types

- `ImageAsset` — `filename`, `url` (`/static/<name>`), `size`,
  `mime`, `created_at`, `used_by: number[]` (agent ids referencing
  it), `is_curated?: boolean`
- `ImageListResponse` / `ImageUploadResult` / `ImageImportResult`
- `BulkUploadResult` — `added[]`, `errors[]`, `total_requested`,
  `total_added`, `total_errors`
- `BatchDeleteResult` — `deleted[]`, `failed[]` (with per-file
  `reason`), `total_requested`, `total_deleted`, `total_failed`

## Notes

- Export is fetched directly (`fetch('/api/v1/images/export',
  { method: 'POST' })`) so the page can download the blob — the
  apiClient abstraction doesn't do blob responses.
- `is_curated` is set by the backend (matches
  `assets/agent-images/*.png` filenames) — the UI never decides
  curation.

## Related

- [[atlas/api/routers/images|Images API]]
- [[atlas/ui/pages/ImageManagement|Image Management]]
