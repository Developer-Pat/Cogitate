---
title: Image Management
category: image-management
subtopic: Overview
order: 1
confidence: high
created: 2026-08-11
updated: 2026-09-10
tags: [domain/help]
---

# Image Management

The Images page (Assets → Images) is where the application's
image assets live — the pictures agents use as profile images.
You can browse, upload, organize, and clean up images from one
place.

## What you see

- **The table** lists every image: a preview thumbnail, the
  filename, size, type, and which agents use it (a green "agent
  3" badge) or "unused".
- **curated** badge — these are the images that ship with the
  app. They're always available; if you delete one, you can
  bring it back with Restore curated.
- **Search** — type in the search box to filter by filename.
- **Filter dropdown** (All / Curated / Uploads) — narrow the
  list to just the built-in images or just your uploads.
- **Column headers sort** — click Filename, Size, or Type to
  sort the list; click again to flip the order.

## Uploading images

1. Click **Upload** and pick one or more files (hold Ctrl/Cmd
   to select several).
2. **Strip metadata** is on by default: it removes hidden
   details like camera info or the generation workflow that
   some image tools (e.g. ComfyUI) embed. Uncheck it if you
   want those details kept. The upload message tells you which
   happened.
3. Uploaded images appear at the top of the list.

You can also **Import** a .zip of images to add several at once.

## Deleting images

- **One at a time** — click the ✕ in an image's row.
- **Several at once** — tick the checkboxes, then **Delete
  selected**.
- Images that an agent is currently using can't be deleted
  (they'd break the agent's picture). Unassign them from the
  agent's profile first.
- **Tip**: filter to **Uploads** first, then select all — it's
  an easy way to clean up your own uploads without touching the
  built-in images.

## Restore curated

If you delete built-in images (or want to reset them), click
**Restore curated**. It brings back the images that ship with
the app. Your own uploads are never touched.

## Export

**Export** downloads all images as a .zip file — handy for
backing up or moving your image collection.

## Related

- [[help/agent-profiles|Agent Profiles]] — where images are
  assigned to agents
