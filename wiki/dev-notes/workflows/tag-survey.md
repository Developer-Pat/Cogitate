---
title: The Tag Survey (and the pseudo-agent pattern)
type: atlas-devnote
category: dev-notes
order: 9
confidence: high
created: 2026-09-11
updated: 2026-10-07
tags: [type/dev-notes, domain/dev-notes, topic/workflows]
---

# The Tag Survey (and the pseudo-agent pattern)

Two things live here: **the tag survey** (a workflow that reads the wiki's frontmatter tags and
proposes consolidations) and **the pseudo-agent pattern** (the bare-LLM call that makes it work). The
pattern is the more reusable of the two — read that part even if you never touch the tag layer.

## The pseudo-agent pattern

A **pseudo-agent** is a named spec, not an agent: a system prompt + an ordered provider chain + params.
It is **stateless, tool-less and memory-less** — no workspace, no session, no tools. It exists so a
workflow node can make an LLM call without standing up an agent for it.

Defined in `backend/app/domain/pseudo_agents/catalog.py`:

- `tag-worker` — one call per batch; extracts tags from file contents
- `tag-boss` — one call over the whole manifest; produces the consolidation report (renames / adds /
  drops)

**The chain contract:** first success wins; every attempt is logged; a per-attempt timeout; **all-failed
RAISES**; and the provenance (`served_by` plus the attempt history) is **returned**. That last part
matters — it lets a caller prove *which model answered*, not merely that a client was built.

Both specs route **free route → the local model → deepseek**. The local step's model id is resolved at
call time rather than baked in at import, so a settings change reaches the next call.

## Running the survey

`backend/scripts/run_tag_survey_trickle.py` — discovers wiki files, batches them, runs the worker per
batch through the free route with an adaptive pause, merges the rows, then hands the manifest to the
boss.

Output lands in the agent workspace: `agents/tag-layer-sweeper/out/` (`tag-layer-manifest.md`,
`consolidation-report.md`) — the directory is the workspace path the run points at, not an agent it
needs.

## Applying it

`backend/scripts/apply_tag_proposals.py --dry-run`, then `--apply`. It parses the boss's report and
performs renames / adds / drops against the wiki. It is **idempotent** — a second run finds only what
remains.

## Gotchas

Each of these is a rule the applier has to honour, not a war story:

- **An untagged page has no `---` to insert after.** The applier must **PREPEND** frontmatter; an
  insert-only implementation silently does nothing for a page being tagged for the first time.
- **A drop can leave a page with ZERO tags.** It warns loudly; it never invents a replacement tag.
- **The probes must run from the repo root** — `env_file` is a relative path, so `Settings` finds no
  `.env` otherwise.
- **A terminal state builder must never raise.** A raise inside an error handler hides the original
  failure; an `outputs` channel must be merged, not clobbered.
- **A documented parameter must actually be wired.** `worker_fn` was documented and never read; a knob
  that nothing reads is worse than no knob.

## Registration

`tag-survey` is a registered workflow kind (`workflow_kinds`). **There is no UI template** — it runs
from the script or as a direct graph run.

## The survey needs no agent — and none belongs here

The survey's nodes call the **pseudo-agent specs**, not an agent: there is no system prompt to hold, no
workspace to own the call, and no tools to grant. Its output directory is a path the run is given.

An agent placed beside this workflow would be an identity with no function — no prompt, no skills, no
kit, and no caller — which is exactly the shape to avoid: a name in the catalog that nothing
references. The specs, the kind, and a workspace path for the output are the whole requirement.
