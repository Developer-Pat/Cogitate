---
title: Image Management
type: atlas-page
path: frontend/src/pages/ImageManagement.tsx
confidence: high
updated: 2026-08-11
tags: [type/page, domain/atlas-ui]
---

# Image Management

**Component**: `frontend/src/pages/ImageManagement.tsx`
**Route**: `/images` (protected, `requiresAuth: true`, icon `photo`, breadcrumb "Image Management") — registered in `frontend/src/config/routes.ts` and linked from the sidebar navigation in `frontend/src/App.tsx` under the **Utilities** section (nav label "Images")
**Last Updated**: 2026-08-11

## Purpose

The **asset-management surface** for the application's image assets
(asset-management roadmap Phase 1 — images-only scope; other asset
kinds later). Lists, uploads, deletes, imports, and exports the
image store behind `GET /api/v1/images`.

The store is the filesystem: `data/profile_images/` (gitignored,
served at `/static/`). Two kinds of assets appear:

- **Curated** — the 15 "batteries-included" images whose canonical
  git-tracked home is `assets/agent-images/` (seeded into the store
  by `scripts/core/seed_agent_images.py` with stable lowercase-kebab
  names, e.g. `bob.png`). Flagged **curated** in the table.
- **Uploads** — user-uploaded images (uuid filenames), including
  agent profile images not drawn from the curated set.

## Key Features

- **Collection-pattern table** (user: "table setup instead of a card
  layout"): checkbox column, Preview thumbnail, Filename (mono),
  Size, Type, Used By badge (`agent N` / `unused`), Actions
- **Curated badge** — `badge-primary` "curated" next to the type
  for the 15 canonical assets
- **Search** (filename) — filters the current page; **pagination**
  (pageSize 50)
- **Curated filter dropdown** (2026-08-11) — All / Curated /
  Uploads; server-side (`?curated=`), filters BEFORE pagination so
  totals stay honest. Flow: filter to Uploads → select-all →
  bulk delete → curated untouched
- **Sortable columns** (2026-08-11) — Filename / Size / Type
  headers toggle asc/desc (▲/▼); default alphabetical (filename
  asc); server-side (`?sort_by=&sort_dir=`) so pages stay honest;
  changing sort resets page + selection
- **Bulk upload** (2026-08-11) — Upload button takes MULTIPLE files
  (`multiple`); per-file validation + pixel dedup; "Uploading…"
  state; per-file error reporting
- **Bulk delete** (2026-08-11) — checkbox selection (select-all in
  header), "N selected" bar, confirm modal; in-use images reported
  as failed (skipped, never destroyed); deleted-count + in-use-skips
  reported as separate toasts
- **Strip metadata checkbox** (2026-08-11) — DEFAULT ON; strips
  EXIF/ComfyUI workflow metadata from PNGs on upload (single, bulk,
  zip import); toasts report "metadata stripped" vs "metadata
  kept" — no surprises
- **♻️ Restore curated** (2026-08-11) — re-copies the 15 canonical
  files from `assets/agent-images/` into the store (additive-only:
  uploads untouched, existing files not overwritten, no agent
  rewiring, no orphan removal). The user's fallback safety net —
  deletion stays allowed, recovery is one click
- **Import / Export** — zip download of all images / zip upload
  that PRESERVES original filenames (round-trip: export → delete →
  import restores the store exactly; agent URLs keep working).
  Pixel-deduped, idempotent, optional strip; skips non-images,
  size-checks each
- **Delete** — per-row ✕; confirmation; the backend refuses (409)
  when an image is referenced by an agent (orphan protection)

## Tooltips (2026-08-11)

All interactive tooltips are DaisyUI `tooltip` + `data-tip` (no
native `title=` on buttons). Top-row action buttons (Import /
Export / Upload / Restore curated / Strip metadata) use
**`tooltip-bottom`** so the bubble opens DOWN and stays on screen;
mid-page elements (sort headers, checkboxes, filter select) use
`tooltip-top`.

## Data Flow

1. `load()` — `imageService.listImages(page, pageSize, curated,
   sortBy, sortDir)` → `GET /api/v1/images?page=&page_size=
   &curated=&sort_by=&sort_dir=`
2. Selection — local `Set<string>` of filenames; select-all covers
   the filtered (current-page) rows
3. Bulk delete — `imageService.batchDelete(filenames)` →
   `POST /api/v1/images/batch-delete` → per-file `deleted[]` /
   `failed[]`; in-use failures surfaced as an error toast
4. Upload — hidden `<input type="file" multiple>` →
   `imageService.uploadImagesBulk(files, strip)` →
   `POST /api/v1/images/upload-bulk?strip=`
5. Restore — `imageService.restoreCurated()` →
   `POST /api/v1/images/restore-curated`

## Related

- [[atlas/api/routers/images|Images API]]
- [[atlas/ui/services/domains/llm/imageService|imageService]]
- [[dev-notes/assets/agent-images|Agent Images (dev note)]]
