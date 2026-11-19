---
title: Attachment System
type: atlas-devnote
category: frontend
order: 2
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/frontend]
---

# Attachment System

## Overview

Chat attachments — upload, list, download, delete. Backend:
`attachments_router.py` (backend/app/api/v1/chat/) + models in
backend/app/infrastructure/database/models.py. Frontend:
AttachmentService (frontend/src/services/domain/) +
AttachmentPreview component.

## API surface

- `POST /chat/attachments` (+ `/batch`) — upload
- `GET /chat/attachments` — list; `GET /{id}` + `/{id}/download`
- `DELETE /{id}`

## Frontend flow

- AttachmentService handles upload + preview URLs; AttachmentPreview
  renders images/files inline in the chat thread.
- Upload size + allowed types come from Settings
  (max_upload_size, allowed_image_types).

## Multipart constraints (attachments_router.py)

- `POST /chat/{session_id}/attachments/batch` — multipart upload.
- **Max size**: 10MB (`MAX_FILE_SIZE = 10 * 1024 * 1024`).
- **MIME filter**: content_type must be in `ALLOWED_MIME_TYPES`;
  `application/octet-stream`/`binary/octet-stream` treated as
  binary — rejected types get a clear 400 ("File type X not
  allowed").
- Endpoints: `GET /{id}`, `GET /{id}/download`, `DELETE /{id}`.
- Uploads are **synchronous to the session** (not tied to the
  stream) — files attach to the session; the message references
  them. Streaming replies reference attachments by id in the
  message payload; there is no attachment-bytes-in-SSE — only
  metadata.
