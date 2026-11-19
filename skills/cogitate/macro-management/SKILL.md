---
name: cogitate-macro-management
description: "Generate, review, and maintain macro sets and meta-topics in the Cogitate macro system. Use when the user asks to create, edit, or improve macros (F1-F5 slots, meta-topics, slot mappings, namespaces)."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [macros, meta-topics, f-keys, authoring, cogitate]
    related_skills: [cogitate-orientation, cogitate-analyze-logs]
---

# Cogitate Macro Management

The user works with the **Macro Management** page (/macros). You help
them generate, review, and maintain macros. The macro system is
EXTENSIVE — hand-editing every slot is tedious and error-prone, which
is exactly why they asked you. Produce complete, correct macros, not
stubs.

## The data model

- **Macro set** — the unit of authoring: `topic` (category, e.g.
  "Algebra"), `name`, `description`, **five slots** `f1_macro` …
  `f5_macro` (each a full prompt/command string), `is_active`,
  `sort_order`, `user_key` (default "default").
- **Meta-topic** — an agent-level topic that maps macro sets onto a
  **25-slot F-key grid** (F1–F25 = up to 5 topics × 5 F-slots each):
  `topic_mappings: [{topic, slot_start}]` where slot_start ∈ {F1,
  F6, F11, F16, F21} (each topic occupies 5 consecutive slots).
  A mapping of `{"topic": "Algebra", "slot_start": "F1"}` places
  Algebra's sets at F1–F5, the next at F6–F10, etc.
- **Legacy M-slot notation** — older meta-topics (e.g. id 1, 7,
  10, 11, 12) store `slot_start` as `M1`–`M5`, the topic-position
  convention: `M{n}` = F-slot `5*(n-1)+1` (M1→F1, M2→F6, M3→F11,
  M4→F16, M5→F21). The API reads both; **write new mappings in
  F-form** (F1/F6/F11/F16/F21). The load response ALWAYS reports
  F-form (normalized), so the grid is consistent regardless of
  what's stored.
- **Namespace** — `agent` (and user-level equivalents); macro sets
  can be scoped per user_key.

## The API (base: /api/v1/macros)

| Purpose | Route |
|---|---|
| List macro sets | `GET /api/v1/macros?user_key=&topic=&all=` |
| List topics | `GET /api/v1/macros/topics/list` |
| List meta-topics | `GET /api/v1/macros/meta-topics` |
| Get one meta-topic | `GET /api/v1/macros/meta-topics/{id}` |
| Create meta-topic | `POST /api/v1/macros/meta-topics` — `{name, description, topic_mappings:[{topic, slot_start}], is_active}` |
| Update meta-topic | `PUT /api/v1/macros/meta-topics/{id}` |
| Delete meta-topic | `DELETE /api/v1/macros/meta-topics/{id}` |
| Search sets | `GET /api/v1/macros/search?q=` |
| Get one set | `GET /api/v1/macros/{id}` |
| Create set | `POST /api/v1/macros` — `{user_key, topic, name, description, f1_macro..f5_macro, is_active, sort_order}` |
| Update set | `PUT /api/v1/macros/{id}` |
| Delete set | `DELETE /api/v1/macros/{id}` |

## How to author good macros

1. **Discover first**: `GET /api/v1/macros?all=true` + `/topics/list`
   + `/meta-topics` to see what exists. Reuse topics; propose
   meta-topic mappings for new ones. NEVER duplicate an existing
   set.
2. **Write full prompts, not labels**: each F-key slot is a
   complete instruction the agent will execute — say what to DO,
   what to check, and what to report. Example (a diagnostics
   macro): *"Check the logs for errors and warnings. Cluster them
   by timestamp; report the top clusters with evidence."*
3. **End-user language**: macros run in the user's chat area —
   plain instructions, no dev jargon, no naming archaeology.
4. **Slot conventions**: each macro set has F1-F5; a meta-topic
   places sets at F1/F6/F11/F16/F21 (5 slots each). Write new
   mappings in F-form; if you read an existing mapping in M-form
   (M1-M5, legacy topic-position), convert via M{n} -> 5*(n-1)+1
   — never store or echo M-form in new writes. Respect the grid
   when mapping (no overlapping ranges).
5. **Active by default** unless the user says otherwise.
6. **Show your work**: when creating/updating via the API, show the
   user the resulting slot layout (F1-F5 per set, meta-topic grid)
   so they can verify before using.

## Verification

- After creating/updating, re-`GET` the set/meta-topic and confirm
  it round-trips (name, slots, mappings present).
- If the user says a macro "doesn't work", fetch it, read the
  prompt, and check the topic/mapping wiring before proposing edits.

## Boundary

Authoring macros (creating/updating/deleting via the API) requires
fix-mode. In read-only mode, produce the macros as a proposal and
let the user apply them.
