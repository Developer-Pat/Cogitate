---
title: Agent Images — canonical home
type: dev-note
category: dev-notes
order: 9
confidence: high
created: 2026-08-10
updated: 2026-08-11
tags: [type/dev-notes, domain/assets]
---

# Agent Images — canonical home

> Where agent images live, and why there is only one source of
> truth. Part of the asset-management roadmap (Phase 2 — the
> bundled-images seed story).

## The two stores

| Store | Path | Tracked? | Role |
|---|---|---|---|
| **Canonical source** | `assets/agent-images/` | ✅ git-tracked (15 PNGs, ~9.3MB) | The curated "batteries-included" set — the source of truth |
| **Runtime store** | `data/profile_images/` | ❌ gitignored | Served at `/static/`; derived from the source + user uploads |

The curated source was moved from the old `img/profile_images/`
(which was gitignored — a fresh clone had no images at all). The
blanket `*.png` rule in `.gitignore` needed a negation
(`!assets/agent-images/`) to track them.

## Why the names matter

- **Canonical**: lowercase-kebab (`bob.png`, `alien-rocky.png`)
  — stable, human-meaningful, referenced directly by agents
- **Uploads**: uuid (`img_<uuid>.png`) — collision-safe for
  arbitrary user content

The **old design copied a curated image per agent assignment**
(`agent_19_b2e437….png` ← `Bob.png`), duplicating files. The
remap ended that: agents reference `/static/bob.png` directly.

## The seed script

`scripts/core/seed_agent_images.py` (idempotent):

1. Copies curated → runtime store with stable names (skip if
   identical)
2. **Remaps** agent `profile_image_url` from old uuid copies →
   canonical names (by content hash, then **pixel fingerprint**)
3. Removes orphaned uuid copies

### Pixel fingerprints (the metadata lesson)

A byte-MD5 comparison **misses re-encoded copies** — e.g. a PNG
that had its metadata stripped has identical pixels but different
file bytes (agents 15/22 were exactly this: copies of
`scheherazade.png` / `alien-01.png`). The script's
`_pixel_fingerprint()` hashes PNG dimensions + decompressed IDAT,
so re-encoded copies are still recognized for remap + cleanup.

## The image store today

```
data/profile_images/ → 15 files, all canonical (0 dupes, 0 orphans)
14 agents → all resolve 200 (0 broken)
```

Two genuine uploads existed at the remap and were kept (agents
15/22) until proven pixel-identical to curated assets — then they
were remapped too.

## Upload dedup (2026-08-11)

Both upload paths — the profile form's Upload (`POST
/agents/{id}/image`) and the Image Management page's Upload
(`POST /api/v1/images/upload`) — deduplicate by **pixel
fingerprint** via `backend/app/domain/assets/__init__.py`:

1. Fingerprint the incoming bytes: MD5 of PNG dimensions +
   decompressed IDAT (byte hashes miss metadata-stripped copies)
2. Scan `data/profile_images/` for an existing file with the
   same pixels
3. Found → **reuse it** (return the existing filename, no new
   file written). Not found → save as a fresh uuid file

This closes the last duplication source: re-uploading the same
image (or a re-encoded copy) no longer creates duplicate uuid
files — the same dedup logic that cleans the curated set now
guards uploads. `dedup_upload()` returns `(filename, saved_new)`
so callers know whether a new file was written.

Behavior: uploading an identical image twice returns the same
filename both times; the store keeps exactly one file.

## Metadata stripping (2026-08-11) — optional, never silent

`app/domain/assets.strip_metadata()` removes non-color PNG chunks
(tEXt/zTXt/iTXt/eXIf) — where EXIF/GPS and **ComfyUI's embedded
generation workflow** live. Users are expected to generate their
own agent images from Comfy etc., so stripping is:

- **OPTIONAL** (user decision: "no one likes surprises") — a
  "Strip metadata" checkbox on the Image Management page, default
  ON, plus `strip=true` on all upload endpoints
- **REPORTED** — the upload toast says "(metadata stripped)" vs
  "(metadata kept)"; the backend never strips silently
- **PIXEL-SAFE** — critical + color chunks (IHDR/PLTE/IDAT/IEND/
  tRNS/gAMA/sRGB/iCCP/pHYs/bKGD/sBIT) are kept, so pixels and
  colors are untouched; when there is nothing to strip the
  original bytes are returned (byte-identity preserved for dedup)
- **BOUNDED** — PNG only (stdlib). JPEG/WebP EXIF stripping needs
  Pillow (a new dep); none in the store today — tracked gap

## Import/export round-trip (2026-08-11, user-caught bug)

The zip Import PRESERVES original filenames (does NOT rename to
`img_<uuid>`). Export → delete → import restores the store
exactly. This matters because agent URLs reference canonical
names: the old rename-on-import broke restore (blondie never came
back) and left `/static/<name>` references 404. Import is also
pixel-deduped + idempotent — re-importing an unchanged store adds
nothing.

## Deletion policy + Restore curated (2026-08-11)

User decision: curated images are **deletable** (users may deploy
their own resources — don't fight them) and **not auto-restored**
(don't fight the user between delete and restore). Instead:

- Deletion stays allowed (in-use → 409 orphan protection remains)
- **♻️ Restore curated** (`POST /images/restore-curated`) re-copies
  the canonical set into the store — **additive-only**: uploads
  untouched, existing files not overwritten, no agent rewiring,
  no orphan removal (the seed's orphan step would delete user
  uploads — exactly the fighting-the-user problem). Idempotent.
- Result: delete → restore round-trip is safe to test forever.

## Management UI

The [[atlas/ui/pages/ImageManagement|Image Management]] page
(Utilities → Images) is now a full collection: curated badge,
filename search, **curated filter** (All/Curated/Uploads),
**sortable columns** (Filename/Size/Type, default alphabetical),
**bulk upload** (multi-file), **bulk delete** (checkbox + select-
all, in-use reported not destroyed), **Strip metadata** checkbox,
**♻️ Restore curated**. In-use images protected from deletion
(409). DaisyUI tooltips; top-row buttons open downward
(tooltip-bottom) so they stay on screen.

## Related

- [[atlas/api/routers/images|Images API]]
- [[atlas/ui/pages/ImageManagement|Image Management]]
- [[atlas/ui/services/domains/llm/imageService|imageService]]
- Roadmap: `local/roadmaps/asset-management-roadmap.md`
