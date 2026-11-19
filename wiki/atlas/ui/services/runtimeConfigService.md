---
title: runtimeConfigService (REMOVED)
type: atlas-service
path: frontend/src/services/runtimeConfigService.ts (DELETED)
confidence: high
updated: 2026-09-25
tags: [type/service, domain/atlas-ui]
---
# runtimeConfigService — REMOVED

**Path**: `frontend/src/services/runtimeConfigService.ts` — **DELETED**. No file exists at that
path; this is a removal record, kept so the links that named it still resolve.

## What it was

The client for the session-override API: `getSessionConfig`, `createOrUpdateConfig`, `updateConfig`,
`deleteConfig`, `resetToDefaults`, all against `/api/v1/runtime-config`, plus the `RuntimeConfig`,
`RuntimeConfigCreate` and `RuntimeConfigUpdate` types.

## Why it is gone

`QuickSettingsPanel` was its ONLY caller, and that component was unreachable (its mount was
commented out) and wrote a sampling pair nobody had chosen. With the panel deleted the service had
no consumer, so it went too.

## Where the surface lives now

The API is unchanged and live — an external caller (an ACP agent on the Exa path) is the intended
user of a session override:

- `GET /api/v1/runtime-config/session/{session_id}` — the row for a session, or nothing
- `POST /api/v1/runtime-config` — create or update
- `PUT /api/v1/runtime-config/{session_id}` — update
- `DELETE /api/v1/runtime-config/{session_id}` — delete
- the per-session reset route

Every column on that row is nullable and NULL means "no override for this field" — the reading
`merge_sampling` implements (agent first, overridden per field). `max_tokens` on the same row is the
resolver's highest-precedence writer for a session's output budget. The generated OpenAPI types for
these routes still live in `frontend/src/types/api.generated.ts`.
