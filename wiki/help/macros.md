---
title: Macros
category: macros
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-09-03
tags: [domain/help]
---

# Macros

Macros are keyboard shortcuts for the chat page — F1-F5 for macro text and M1-M5 for topic selection.

## Structure
- **Meta-topics** — Top-level groupings (System Guide, Coding, Creative Writing, etc.)
- **Topic Mappings** — Up to 5 M-keys per meta-topic (e.g. Testing, Debugging, Refactoring)
- **Macro Sets** — F1-F5 macro text per topic

## Chat Page Usage
1. **Select a meta-topic** — click the F selector (the small icon
   after the M keys, on the chat input's keyboard row — the tooltip:
   "Select F-Key Macros"); its flyout picks the topic driving F1-F5
2. **Click an M-key** (M1-M5) to switch topics within the meta-topic
3. **Click an F-key** (F1-F5) to insert the macro text into your message

## Macros Management Page
Use the Macros page to manage all meta-topics and their macro sets:
- Create/rename/delete meta-topics — the actions live behind the
  three-dot (⋮) button next to Select Meta
- Add/remove topic mappings (up to 5 per meta-topic)
- Edit F1-F5 macro text for each topic
- Save/reload from file (the ⋮ menu)
- Clear (left of the Save button) wipes the F-key fields — and
  selecting an empty M-slot clears the form too

## Ask Exa to write macros
Editing every F-key slot by hand is tedious. The **Ask Exa** button
(header) opens the Exa panel ready to GENERATE or maintain macros
for you — it knows the macro system (sets, slots, meta-topics) and
will discover what exists before creating or updating. The request
appears as a hand-off you confirm (Send/Discard), and Exa needs
fix-mode to actually write — otherwise it proposes the macros for
you to apply.

## The A-keys — the action-key bank

The A-keys (A1-A5 in the chat input) are a SECOND macro bank —
the conversational / diagnostic / response prompts — distinct
from the F-keys' topic content. Each A-key is a FLYOUT: click it
to see that slot's prompts.

- **The A-keys are configurable** — they are fed by a meta-topic
  (the "A-Key source"). The seeded **A-Key Macros** meta-topic is
  the out-of-box source (Yes / No / Please continue / greeting /
  conversation / diagnostic / mode prompts). Edit its macro sets
  on the Macros page and the A-keys follow.
- **Select the source directly on the keyboard** — each bank has a
  small icon selector beside its keys (the F selector after M5,
  the A selector beside A1-A5). Picking a meta-topic there makes
  it that bank's source IMMEDIATELY and persists it — no
  page-hopping, no refresh (select = the new default).
- **Agent vs Exa — separate states** — the agent chat and the Exa
  page each keep their OWN F-topic and A-source. Setting Exa's
  A-keys never moves the agent chat's (and vice versa).
- **No source = deactivated** — if no source is set, the A-keys
  row disables with a note. Empty slots are fine — a blank A-key
  simply sits disabled.
- **The Macros page shows the audit state** — the current A-key
  source readout (of the last-used surface) sits under the
  meta-topic name; changes happen on the chat keyboards.

## Features
- **Default topic** — "System Guide" auto-selected on first visit
- **Set as default** — Mark any meta-topic as your permanent default
- **Persistence** — Selected topic saved across page refreshes
- **Auto-sync** — macro changes made anywhere (the Macros page,
  the API) propagate to open chat pages automatically via the
  event bus — no manual refresh button

## Tips
- Set a default meta-topic to avoid re-selecting every session
- M-keys and F-keys are per-meta-topic, so they change when you switch topics
- The A-keys source is a separate setting from the F/M topic — changing the topic does not change the A-keys
- The A-source (and the F-topic) are per surface: the agent chat and Exa remember their own

## See Also
- [[help/cognitive-pipeline|cognitive-pipeline]] — How profiles affect agent behavior
