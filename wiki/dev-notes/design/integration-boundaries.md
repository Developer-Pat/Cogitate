---
title: Integration Boundaries (design philosophy)
type: atlas-devnote
category: design
order: 1
confidence: high
created: 2026-08-13
updated: 2026-08-13
tags: [type/dev-notes, domain/design, status/active, feature/external-agent]
---

# Integration Boundaries — design philosophy

How Cogitate integrates EXTERNAL systems (agents, services, tools):
the principles distilled from the external-agent / consulting-agent
arc (2026-08-11 → 13). These are the WHY behind the architecture —
apply them to the next integration, not just this one.

## Principle 1 — The thin-client rule

**Never reimplement an external system inside the app.** When the
capability belongs to something outside (a thinking agent, a service,
a tool), Cogitate manages the *connection* and relays — it does not
rebuild the capability.

- The external agent does all its own thinking, tools, and memory;
  Cogitate manages a subprocess + relays text over JSON-RPC (ACP)
- The failed experiment this corrects: an in-app rule-engine agent
  ("the in-app agent experiment") that reimplemented agent behavior
  inside the app — own tables, own session logic — and was removed

**Test**: if you are writing *behavior* for an external system, stop.
Write the *interface* instead.

## Principle 2 — Boundary at the enforcement point

**The boundary is real only where it is ENFORCED — and enforcement
lives at the tool/API layer, not the prompt layer.** A prompt
directive ("do not write") is a request; the external system may
ignore it. The gate must be where the capability actually executes.

The fix-mode grant is the canonical case:

1. **Tool-level (the real gate)**: the external agent's own
   edit-approval policy (`workspace_session` vs `ask`) — the agent
   ITSELF denies edits in read-only. Verified live both ways.
2. **Tool-layer hardening**: `strictTools` on session/new blocks the
   dedicated write tools.
3. **Server-side prompt directive**: injected by OUR server (the
   client cannot spoof it) as the third layer.

Two of three layers are enforcement; the third is defense-in-depth.
Never rely on a single prompt directive for a security boundary.

## Principle 3 — Consultant-with-boundary

**An integrated system sees only what the app passes it — never the
app's internals.** The consultant can *suggest* and (with grant)
*act*, but it cannot reach into session stores, DBs, or agent state
on its own. It works the same surfaces a human dev would: logs,
traces, session history, the API.

Two corollaries:

- **Observability-as-trust**: the user watches every tool call stream
  live. Trust is not assumed — it is *witnessed*.
- **Evidence over self-report**: a diagnostic agent reports what it
  OBSERVED (logs, traces, verified claims), not what it assumes. Its
  verify steps hit the real system ("tell me what you actually see").

## Principle 4 — Grant, don't assume

**Capabilities that can cause harm start OFF and are turned ON by an
explicit user grant — never by default, never silently.** The
fix-mode toggle is the pattern: read-only first, fix = explicit
grant, the grant is visible (badge) and revocable (toggle off).

The grant must also be **scoped**: `workspace_session` (inside the
project) rather than `session` (everything). Scope is part of the
grant, not an afterthought.

## Principle 5 — Vendor neutrality

**Feature docs are generic; vendor quirks live in per-vendor notes.**
The feature is "external agent via ACP"; Hermes is one vendor. Its
quirks (edit-approval policy, startup race, protocol pydantic gates)
live in `wiki/dev-notes/agents/hermes.md`; OpenClaw gets its own
note when it joins. The code has the same seam: `command` is
configurable, the domain is `external_agent` (not `hermes`).

**Test**: swap the vendor and the feature docs should not change.

## Principle 6 — User-facing copy says what things DO

**End-user surfaces (help, UI text, tooltips) say what things DO, in
end-user language — developer knowledge stays in dev notes.**
Over-sharing (naming archaeology, "what it is not" sections, protocol
acronyms like ACP, vendor-promotion) adds cognitive load without
value. The test: if a user must know it to USE the feature, it
belongs in the UI/help; if it's context for MAINTAINING the feature,
it belongs in dev notes.

- Canonical example (2026-08-13): the Exa Agent help page initially
  told the naming story (Exa-Agent, the old system-agent name), had a
  "What it is not" section, and leaked implementation talk
  (subprocess, ACP). Rewritten lean; the naming story lives only in
  the dev notes now.
- The user flags over-shares as **TMI** and they accumulate in
  `todo/ideas.md` for a dedicated cleanup session.

## How these interact

```
Thin client (P1) ── defines ──▶ what we build: an interface, not behavior
Boundary at enforcement (P2) ─ defines ──▶ where the interface is enforced
Consultant-with-boundary (P3) ─ defines ──▶ what the interface may see/do
Grant-don't-assume (P4) ─ defines ──▶ how capabilities are unlocked
Vendor neutrality (P5) ─ defines ──▶ how the interface is documented/tested
```

## Related

- [[dev-notes/agents/consulting-agent|Consulting Agent]] — the feature that birthed these
- [[dev-notes/agents/hermes|Hermes vendor note]] — the enforcement-point case study
- [[dev-notes/agents/external-agent-domain|External Agent Domain]] — the thin client
- [[atlas/api/routers/external-agent|External Agent API]]
- [[atlas/ui/components/features/agentInteraction/AgentPanel|AgentPanel]]
