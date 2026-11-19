---
title: Macro System Architecture
type: atlas-devnote
category: macros
order: 1
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/macros]
---

# Macro System Architecture

## Overview

The macro system is built around `AgentMacroService`
(backend/app/domain/macros/services.py) — macro SETS organized under
meta-topics, with export/backup support.

## Core model

- **Macro sets** — collections of related macros; CRUD + search via
  AgentMacroService (create/get/search/list/update/delete_macro_set).
- **Meta topics** — organizing layer above sets; each set can be
  grouped under a topic (create/list/update/delete_meta_topic,
  list_topics, get_macro_set_by_topic, load_meta_topic).
- **Slots** — sets can reference slot numbers (parsed by
  `_parse_slot_number`) for templated positioning.

## API surface

- **CRUD**: backend/app/api/v1/macros/router.py — macro sets,
  meta-topics, search, saves, load/save.
- **Export/import**: export_router.py — macro-sets, meta-topics,
  all, import, templates.
- **Backup/restore**: backup_router.py — create/list/restore/delete.

## Supporting services

- export_service.py, backup_service.py, cmn_resolver.py,
  db_retry_utils.py (retry wrappers for DB calls).

## Macro set → agent binding (CMN addresses)

`cmn_resolver.py` resolves CMN addresses programmatically (no LLM
mapping — a former error source):

```
System (full):     SM.<MT>.<T>.<M>.<F>
System (shorthand): SM.<MT>.<M>.<F>
Agent:             AM.<MT>.<T>.<F>
```

- `SM`/`AM` = namespace (System Macro / Agent Macro)
- `MT<n>` = Meta Topic ID (DB pk), `T<n>` = topic index (0-based
  within topic_mappings), `M<n>` = macro set index (0-based),
  `F<n>` = function slot (0-based: F0→f1_macro ... F4→f5_macro)

## Frontend Macros page

`frontend/src/pages/Macros.tsx` + `useSystemMacrosStore`
(`stores/macroSetsStore.ts`) using raw `fetch` against the REST
surface (`/api/v1/macros/*`) — the legacy `chatMacrosStore` and the
`macroSetsService`/`metaTopicsService` modules are gone (deleted;
the store is the only macro state holder).

## The A-key bank (the second macro surface)

The chat input's A1-A5 keys are a SECOND macro bank, distinct from
the F/M topic keys (2026-09-03, the akeys arc):

- **Semantics**: F-keys are topic-scoped CONTENT (what to ask —
  changes with the selected M topic). A-keys are
  context-independent UTILITY (conversational / diagnostic /
  response prompts). Same data machinery, different content axis.
- **Rendering**: A1-A5 are FLYOUTS (multi-item) — no M-key
  selector; a flyout IS the content. Each A-key = one of the A
  source's first-5 mapped macro sets; the flyout items = that
  set's non-empty f1-f5 macros. Full + compact layouts render
  from the same builder (MacroKeyboard.tsx).
- **THE SURFACE SPLIT (2026-09-03, Phase 5a)**: the agent chat and
  the Exa page render the SAME ChatInterface but keep FOUR
  independent selections — Agent/Exa × F/A. utils/macroSurface.ts
  scopes the storage keys: the agent surface keeps the legacy
  BARE keys (`cogitate_selected_meta_topic`,
  `cogitate_akeys_meta_topic` — no migration); exa gets
  ':exa'-suffixed keys. The store holds the ACTIVE surface
  (`surface` + `setSurface`, called by ChatInterface from the
  agentId — the pages are separate routes, never co-mounted) and
  routes every load/save/resolve through it.
- **THE SOURCE RESOLUTION (the conflation guard)**: the A bank is
  fed by a meta-topic designated in its OWN persisted setting
  (utils/aKeysSource.ts, surface-scoped) — NEVER the F/M keys.
  The cascade: explicit A-default → the seeded "A-Key Macros"
  meta-topic → NULL (deactivated with a visible reason).
  Deliberately NOT the F-side first-available fallback — A
  content is semantic, wrong content is worse than none.
- **DIRECT SELECTION — the keyboard selectors (Phase 5b)**: each
  bank has a tiny icon selector on the keyboard row (TopicFlyoutButton
  with bank='f'|'a' + iconOnly): the F selector after the M group,
  the A selector beside the A keys. SELECT IS PERSIST — the A
  pick calls setAKeysDefault (no separate Load/Set steps); the
  tooltips carry the state readout ("F topic: X" / "A source:
  Y"). The standalone row-2 topic pill is gone. The Macros page
  shows only the audit readout (Phase 5d).
- **NO REFRESH BUTTON (Phase 5c)**: MacroReloadButton.tsx is
  DELETED — useMacroSync (App-level, the event bus) reloads both
  banks on every macro:* / meta-topic:* change event. Edits made
  anywhere propagate to open chat pages automatically.
- **The seed**: backend/app/domain/macros/seeds.py — idempotent
  startup seed (wired in main.py beside seed_agent_packages)
  creating the "A-Key Macros" meta-topic (A1-A5 mappings) + 5
  starter sets. Creates only what is missing; never overwrites
  user edits.
- **Store**: macroSetsStore (surface + aKeysMetaTopicId +
  setAKeysDefault); the cascade re-resolves on every
  loadMetaTopics/reloadMacros/setSurface.
