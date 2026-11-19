---
title: Agent Identity — the face, the persona, and the initial state
type: atlas-devnote
category: agents
order: 9
confidence: high
updated: 2026-09-10
tags: [type/devnote, domain/agents]
---

# Agent Identity — the face, the persona, and the initial state

What a NEW agent gets, and where the line runs between the CHARACTER
(which is cloned and shared) and the INSTANCE (which is never cloned).
Written for whoever authors the next reporter's persona.

## The line

| | the CHARACTER | the INSTANCE |
|---|---|---|
| what | persona, skills, beats, kit surface, face | the facts it learns (location, timezone, its watches) |
| cloned from a template? | **yes** | **NEVER** |
| where it lives | the template + the workspace files | `state.json` |

A template clones the character; the instance starts empty. Bob's
location is Bob's.

## The face

- The pool is `assets/agent-images/` (git-tracked); it is served from
  `data/profile_images/` at `/static/<name>.png`.
- **A new agent gets its own face**, whether created plainly or applied
  from a template — `pick_agent_face()` prefers one no other agent
  wears. A clone that wears the original's face is confusing in exactly
  the way a clone should not be.
- `save_agent_as_template` deliberately does NOT capture the face. The
  user sets a specific image in the agent's profile.
- When the pool is spent the first face is reused — a visible duplicate
  beats an invisible agent.

## The initial state

A new agent's `state.json` is:

```json
{"facts": {}, "sources": []}
```

**Both keys present, both empty** — so the `update-state` /
`update-sources` tools have a well-formed store from the first turn.
Nothing is defaulted with placeholder facts: the agent genuinely knows
nothing yet.

## The persona rule — never hardcode an instance fact

The system prompt is built with a `YOUR STORED STATE` block **only when
the store has facts or sources** (`build_state_block` returns `None`
while it is empty). So a persona must never say:

> Your locus is Omaha, Nebraska.

That is an INSTANCE fact baked into a CHARACTER. It is wrong for every
other agent and unverifiable for a new one. Instead the persona points
at the store and handles its absence:

> Your location, timezone and anything you have learned about the user
> live in your stored state — the YOUR STORED STATE block appears in
> your context once you have stored something. If it is not there, you
> do not have it: ask the user, or check your IP as your
> self-state-maintenance skill describes.

The skill already carries the operative rule — *"never claim a stored
fact you did not write"* — so the persona only has to point at it.

**Bob's existing persona still hardcodes "Omaha, Nebraska."** It is
left alone deliberately: personas are not edited (the house law —
skills grow, personas stand). Fix it when his persona is next
re-authored on purpose, not as a drive-by.

## The apply, end to end

An applied agent gets: `agent.json`, `persona.md` (from the row's
system prompt), an empty `state.json`, the seeded `skills/`, the
template's `workspace_files` (the beat sheets), its own face, and the
template's kits attached via the `agent_kits` join.
