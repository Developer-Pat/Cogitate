---
title: CuratedModelsManager
type: atlas-component
path: frontend/src/components/features/providers/CuratedModelsManager.tsx
confidence: high
updated: 2026-08-03
tags: [type/component, domain/atlas-ui]
---

# CuratedModelsManager

In-app management UI for the **curated model list** (human-owned
recommendations). Phase 3 admin UX: the curated list is now manageable
from the app, not just via DB/seed edits.

## Location & integration

- Rendered as the **Curated tab** on the Provider Dashboard
  (`frontend/src/pages/ProviderDashboard.tsx`, 4th tab)
- Backed by `/api/v1/curated-models` CRUD (built Phase 1:
  `curated_models_router.py` + `curated_models_service.py`)
- Uses `curatedModelsService.ts` API client (fetch/add/update/remove)

## Features

- **Provider filter** — a select: `All` (the default) plus every provider with
  its count in the option label
- **Table** — provider, display name, model id (mono), **cost** (`free` / `paid` /
  `unpriced`, read from the provider's own pricing), thinking, actions (copy /
  verify / edit / remove); sorted by whichever header is pressed. The two long
  columns are FIXED-WIDTH under `table-fixed` and truncate, each carrying its full
  value in a tooltip. **The NAME's tooltip also carries the row's description**
  when it has one — that is the description's only read path (it is not a column:
  per-item notes are extended content), and a row with no note reads as its name alone
- **Add modal** — provider + category dropdowns, model id (read-only on
  edit), display name, description, context length, thinking + location. NO cost
  control: the API derives it from the provider's cached pricing and refuses a
  request that states it
- **Edit** — same modal pre-filled; model id + provider locked (identity)
- **Delete** — window.confirm + API delete + toast
- Toasts (notificationStore) on every mutation; errors logged via
  frontendLoggingService

## Data flow

- `fetchCuratedModels()` → DTO → `toCuratedModel()` (snake→camel;
  `curatedRowId` = DB row id for update/delete targeting)
- Create: `addCuratedModel()` (provider, model_id, model_name, category,
  description, context_length, thinking, location — NOT `is_free`: the API derives it)
- Update: `updateCuratedModel(id, ...)` (name/category/description/
  context/flags only — model id is immutable)
- The DB is the source of truth; `curatedModels.ts` config is seed only

## Notes

- **The table lost three columns on purpose** (2026-09-28): `Location` and `Verify` each
  carried one value on every row of the live table (every row is `cloud`, and every row is
  already verified), so neither column conveyed anything — and `Category` came off by the
  user's call, because it is a descriptor of what a row is FOR rather than something you
  scan: **the add/edit modal owns it**. The **Verify ACTION** survives in the Actions cell —
  it is what FILLS a row's context window, and 10 of the 12 live rows have none — while the
  verified STATE lives in the Verify dialog (see the arc's R2).
- **`Cost` replaced the `Free` badge** (R1's one column), and the fact is **DERIVED** (Phase 4):
  the row carries what the provider's own cached pricing said when it was created, so the modal
  has no cost control and the API refuses a request that states `is_free`. Three reads: `free`,
  `paid`, and `unpriced` — the catalog states no price for this model, which is a different
  statement from "it costs money" and is why the column is nullable. Order is free → paid →
  unpriced, the same order the substitution matcher ranks candidates in.
- Provider list falls back to static names (openrouter/ollama/deepseek/
  ollama_cloud) if the providers API is empty
- Tested: `__tests__/CuratedModelsManager.test.tsx` (render, filter, sort, columns,
  cost's three reads, copy, verify, add, edit, delete)
