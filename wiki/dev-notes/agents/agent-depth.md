---
title: Agent Depth — the Nomenclature
type: dev-note
path: wiki/dev-notes/agents/agent-depth.md
created: 2026-09-02
updated: 2026-09-10
status: current
tags: [type/dev-note, domain/agents]
---

# Agent Depth — the Nomenclature

> THE STANDARD (2026-09-02, the user's call): the depth ladder for
> agents. What an agent HAS (a name, a row, a workspace, memory)
> defines its depth tier. Current-state only — the code's "depth"
> axis (the ARM card, `deep | shallow | balanced`) folds into this.

## The ladder

| Tier | Name | Has | Example / notes |
|---|---|---|---|
| 0 | **pseudo** | no name, no row | un-named — a transient/placeholder actor, never persisted |
| 1 | **trivial** | a name/row, NO state, NO workspace | a stateless quick-answer agent (the row exists; nothing on disk) |
| 2 | **shallow** | a workspace, NO memory | the Bob class: workspace folder (agent.json + persona.md + skills/ + state files) but no cognitive memory pipeline |
| 3 | **deep** | a workspace AND memory | the research class: cognitive profile, memory stores, fact extraction |

## The deciding question per tier

- **Does it have a persistent identity (a row)?** No → pseudo.
- **Does it have any state or a workspace?** No → trivial.
- **Does it have a workspace?** No memory → shallow.
- **Does it have memory too?** → deep.

The workspace is what the scaffold creates (`agents/<key>/`:
derived agent.json + a `skills/` seeded from the shared library + a
fresh `state.json` (`{"facts": {}, "sources": []}`) + `persona.md`
from the row; deep agents also keep their memory DB there). Memory =
the cognitive pipeline (memory profiles, stores). **Shallow does NOT
mean stateless** —
a shallow agent can own state files (e.g. a sources store) inside
its workspace; it just has no memory subsystem.

## Why this matters now

1. **The git-repo packaging study** (local/proposals/agent-repos-
   packaging.md): the depth tier determines what ships. Definitions
   ship for every tier above pseudo; state files ship/install with
   the workspace for shallow+; memory is per-install, never shipped.
2. **Bob is shallow** — he HAS a workspace now (2026-09-02, the
   provisioning build; upgraded 2026-09-10): `agents/bob/` holds
   agent.json + persona.md + `state.json` + a `skills/` carrying
   both `self-state-maintenance.skill.md` and `beat-sheets.skill.md`
   + `news-beats/middle-east-vox.md`. Giving him the folder did NOT
   promote him to deep. The workspace-first partition: the persona +
   the beat sheets + the facts/sources store + the personal skills
   live in HIS folder (git-excluded); the DB row keeps registry
   fields + the synced persona fallback + access control
   (grants/kit — never agent-writable). Deep requires the memory
   pipeline. See [[dev-notes/agents/beats|Beats]].
3. **The ARM card** already carries a depth axis; the code should
   speak this ladder's vocabulary (tier name, not just deep/shallow).

## Code touchpoints

- `backend/app/domain/agents/schemas.py` — the ARM card's depth
  field ("deep = research/memory, shallow = quick-response")
- `backend/app/domain/agents/workspace.py` — the scaffold (the
  trivial→shallow line: the workspace)
- `backend/app/services/cognitive_pipeline/memory_manager.py` —
  the shallow→deep line (the memory subsystem)
- `backend/app/domain/agents/repository.py` — the seam (row +
  workspace; memory is per-agent store, not the repo)

## Migration note

"balanced" (the ARM depth family) is not a ladder tier — it is a
deep-tier agent with a balanced driver band. The ladder names what
an agent IS; the driver band names what it RUNS on.
