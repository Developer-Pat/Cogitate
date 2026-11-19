---
title: Macro Development Workflow
type: atlas-devnote
category: macros
order: 2
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/macros]
---

# Macro Development Workflow

## Howto — adding a macro

1. Create the macro set via `POST /api/v1/macros/` (router.py) with
   its content + metadata.
2. Attach it to a meta topic (`POST /api/v1/macros/meta-topics`), or
   leave it topic-less (list_topics shows both).
3. Export templates (`GET /api/v1/macros/templates`) if the macro
   ships a template file.
4. Validate via the Macros page UI (frontend/src/pages/Macros.tsx).

## Key files

- Service: backend/app/domain/macros/services.py
- CRUD API: backend/app/api/v1/macros/router.py
- Export/import: export_router.py; backup: backup_router.py
- Frontend page: frontend/src/pages/Macros.tsx

## Macro file format / slot syntax

- Each macro set has f1_macro..f5_macro (5 slots) — the slot
  content is the macro body (prompt text / instructions).
- Meta topics group macro sets: `meta_topics.topic_mappings`
  (JSON) maps topic names → slot_start; `meta_topics.slot_start`
  anchors topic groups in the CMN address space.

## Meta-topic load/save flow

- **Load**: `GET /api/v1/macros/meta-topics` → topic list with
  slot_start; `GET /api/v1/macros/sets?topic=...` → sets per topic.
- **Save**: `POST/PUT /api/v1/macros/sets` (AgentMacroService
  upserts f1..f5 + namespace); meta topics via
  `POST /api/v1/macros/meta-topics`.
- **Search**: `GET /api/v1/macros/search?q=...` searches name,
  topic, description, or macro content (f1_...).
