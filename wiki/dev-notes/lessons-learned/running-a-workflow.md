---
title: Running a Workflow
type: atlas-devnote
category: lessons-learned
order: 6
confidence: high
updated: 2026-09-10
tags: [type/dev-notes, domain/lessons-learned, domain/workflows]
---

# Running a Workflow

The operational rules for driving a LangGraph workflow to a green run.
These are the things that fail *silently* — a run that looks fine while
doing the wrong thing, or a state that looks empty while the work
succeeded on disk.

## The rules

1. **The state carries two shapes — supply both.** `WorkflowState` holds
   the ids FLAT (`workflow_id`, `template_id`) *and* a `metadata` object
   that carries `config`. The nodes read the flat keys; the dispatcher
   reads `metadata.config`. A caller providing only one gets a
   `KeyError` deep inside a node.
2. **A standalone run must build the tool registry.** Nodes read files
   through the tool system (`ToolRegistry.get_instance()`), which the
   app populates at startup. Outside the app, call
   `init_default_registry()` first — otherwise every read fails with
   `Tool not found`.
3. **`env_file` is relative — the CWD decides whether keys load.**
   Settings reads `.env` from the *current directory*. Run a script from
   the wrong directory and providers silently have no key. Run pipeline
   scripts from the repo root.
4. **The `outputs` channel has no reducer — merge, never replace.** A
   node returning a fresh `outputs` dict DROPS everything earlier nodes
   accumulated (last write wins). The deliverable files on disk stay
   correct while the final state looks empty. Use the shared
   `_merge_outputs` helper.
5. **A terminal-state builder must never raise.** Error and cancel
   handlers read state directly, so a state missing a key crashes
   *inside the handler* and hides the original failure behind a second
   exception. Read defensively (`state.get(...) or "unknown"`).
6. **A docstring is not a wiring.** A node docstring described a worker
   swap as "set by tag_dispatch"; no such node existed and nothing ever
   set the key, so batches silently ran the wrong worker. When docs
   describe a mechanism, confirm the mechanism exists — grep for the
   key, do not trust the comment.
7. **Bound the first run, then widen.** Run a limited slice with the
   adaptive pause (`batch_size` + `max_batches` + `trickle`) before a
   full pass. The first bounded run of the tag survey found four latent
   bugs — three reachable only on error paths or under a clobbered
   state, i.e. exactly the paths a full run would have hit midway.

## Why it matters

Rules 1–5 all fail the same way: the run reports success, or reports a
failure that is not the real one. Rule 6 fails worse — a wrong worker
produces plausible output. Only rule 7 catches any of them cheaply, so
the bounded run is not a smoke test to skip under time pressure; it is
the cheapest instrument for finding exactly this class of defect.

## Related

- [[dev-notes/workflows/workflow-architecture|Workflow Architecture]] —
  the structure these rules operate on
- [[dev-notes/lessons-learned/llm-fallback-chains|LLM Fallback Chains]]
  — the model-side rules for the same workflows
- [[dev-notes/known-issues|Known Issues]] — the bug-fix records
