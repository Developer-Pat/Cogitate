---
title: UI Redesign Reports via Exa's Vision
type: howto
path: wiki/dev-notes/design/ui-redesign-vision-reports.md
confidence: proven
updated: 2026-08-22
tags: [type/howto, domain/dev-notes, domain/design]
---

# UI Redesign Reports via Exa's Vision

How to have Exa LOOK at a page and write a redesign report — the
dual-brain setup (the main brain orchestrates, the vision model
reads the screenshot).

## The two brains (both selected on the Exa Agent page)

1. **The main brain** (the "Quick switch (tested brains)" dropdown)
   — Exa itself: navigation, tool use, writing the report.
   Recommended for reports: `nvidia/nemotron-3-ultra-550b-a55b:free`
   (deep reasoning) or the current chat brain.
2. **The vision model** (the "Vision model (screenshot analysis)"
   dropdown) — reads the page screenshot when Exa calls
   `browser_vision`. Recommended: `google/gemini-3.1-flash-lite`
   (GA, proven vision) or `deepseek/deepseek-v4-flash-vision-exp`
   (experimental, cheap).

**No model switching mid-task**: both are selected once, then one
prompt runs. The main brain orchestrates; the vision model is the
"eyes" (Hermes routes browser_vision to AUXILIARY_VISION_MODEL in
Exa's .env — the UI writes it).

## The mechanics (verified 2026-08-22)

- Exa has the `browser` toolset (browser_navigate / screenshot /
  browser_vision) — confirmed in its platform toolset.
- The app is reachable at `http://localhost:5173/<route>` (same
  host, no auth).
- Flow: navigate → screenshot → browser_vision (the vision model
  reads the PNG) → the main brain writes the report.
- The report lands in `.exa-workspace/reports/<name>.md` (the
  workspace delivery convention).

## The prompt

The redesign-report prompt + the frontend-stack context live in
`.exa-workspace/drafts/ui-redesign-prompt.md`. Give Exa:
- the URL (e.g. `http://localhost:5173/agent-integration`)
- the report name (e.g. `agent-integration-redesign.md`)
- the prompt text (or "read the prompt file in .exa-workspace")

## The stack context (for functional groupings)

The app uses Tailwind CSS + DaisyUI (cards, buttons, tooltips,
modals, dropdowns, badges) + a CSS-variable theme system
(--primary, --button-radius, --button-padding, --button-transition)
+ the PRIMARY PILL assist-button style (bg-primary/20 text-primary
border-primary/30). No emojis in the UI (agent faces are PNG
assets). Group controls per these primitives: a card = a
functional group; a badge = metadata; the ⋮ = overflow actions.

## Caveats

- The vision models are new to the setup — the first run tells us
  if their "eyes" are good (Gemini is the proven bet).
- Screenshots capture the RENDERED page; browser_vision describes
  pixels, the main brain composes the report from that.
- Exa's workspace is `.exa-workspace/` (the delivery convention).
