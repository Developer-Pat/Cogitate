---
title: Dev Notes — Design
type: atlas-index
path: wiki/dev-notes/design
confidence: stub
updated: 2026-09-06
tags: [type/index, domain/design]
---

# Design — Dev Notes

The **why-we-build-this-way** layer. Where `architecture/` documents
how the system IS built (structure, topology, patterns), design notes
document the PHILOSOPHY that drives those structures — the principles
we hold and why, distilled from real decisions.

These are forward-looking and transferable: they apply to the next
feature, not just the last one.

## Pages

- [[dev-notes/design/honesty-loop|The Honesty Loop]] — the
  verification loop: operate → verify → record → report. The
  framework insight (honesty = loop property, trust =
  f(verification coverage)), the verify tools, the
  verification store, the panel surface, the limits. The Exa
  program's Phase 6 (2026-08-19).
- [[dev-notes/design/integration-boundaries|Integration Boundaries]] —
  integrating EXTERNAL systems (agents, services): thin clients,
  enforcement points, boundaries, vendor neutrality. Founded on the
  external-agent / consulting-agent arc (2026-08-11 → 13).
- [[dev-notes/design/control-system|The Control System]] — the UI
  house rules: hue meanings, the one-solid-CTA ladder, the selected
  state, Quiet Mode, the tooltip + expander + dropdown rules, the
  cascade law. Distilled from the UI-loudness passes (start here
  before any page's button/badge work).

## Reading order

Start with integration-boundaries — it is the most recent and the
most complete. Other design notes join this index as they earn
their place.
