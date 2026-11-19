---
title: ProviderKeyManager
type: atlas-component
path: frontend/src/components/features/providers/ProviderKeyManager.tsx
confidence: high
updated: 2026-08-03
tags: [type/component, domain/atlas-ui]
---

# ProviderKeyManager

Keys tab on the Provider Dashboard (Phase 4, mini-map item 8) — the
single place to see/set/rotate/clear provider API keys.

## Location & integration

- Rendered as the **Keys tab** (5th) on ProviderDashboard
- Backed by the key-management endpoints in
  `management_router.py`:
  - `GET /api/v1/providers/managed/keys` — all providers' key status
    with `key_source` (env | db | none)
  - `PUT /api/v1/providers/managed/{id}/key` — set/rotate (encrypted
    at rest via EncryptionService)
  - `DELETE /api/v1/providers/managed/{id}/key` — clear stored key
- Requires the EncryptionService fix (2026-08-03) — DB-stored keys
  were undecryptable before it

## Key-source semantics

| Source | Meaning | UI |
|---|---|---|
| env | settings (.env) key for this provider type | badge-info, Set Key |
| db | encrypted key on the provider row (takes precedence) | badge-success, Rotate + Clear |
| none | no key (local ollama needs none) | badge-ghost, "No key needed" |

## Features

- Provider × type × source table with action buttons per row
- Set/Rotate modal: password input with Show/Hide, precedence hint
  when the provider currently uses .env
- Clear with confirm; toast on every mutation
- Keys are never shown back (only source); errors logged via
  frontendLoggingService

## Notes

- Route ordering matters: `/managed/keys` must be registered before
  `/managed/{provider_id}` or FastAPI shadows it (int-parsing error).
- Help: wiki/help/providers-keys.md; HelpButton context
  `providers-keys` (dashboard header).
- Tested: `__tests__/ProviderKeyManager.test.tsx` (render, set, clear)
  — 3 tests; backend `test_provider_key_management.py` — 3 tests.
