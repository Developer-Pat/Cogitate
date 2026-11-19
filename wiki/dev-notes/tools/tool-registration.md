---
title: Tool Registration and Execution
type: atlas-devnote
category: tools
order: 4
confidence: high
updated: 2026-09-13
tags: [type/dev-notes, domain/tools]
---

# Tool Registration and Execution

There are **two stores** for tools, and they are not the same thing. Conflating
them is the source of a whole class of confusion, so they are set out separately
here.

| Store | Holds | Populated by | Answered by |
|---|---|---|---|
| The **registry** | executable handlers | code, at import | `ToolRegistry` |
| The `tools` **table** | the catalog: slug, name, capability, icon, schema | migrations (seed rows) | the DB |

**A catalog row is not an executable tool.** A row without a registered handler
lists in the UI and resolves to nothing at execution time.

## Where handlers live

`backend/app/domain/tools/builtin/` — one module per tool family, **32 modules**.
Each defines a handler class. The package's `__init__.py` re-exports the classes.

## How they are registered

`registry.py:init_default_registry()` calls `register_builtin(...)` for each
built-in — a **hard-coded list in code**, not a discovery scan. There is no
folder-scanning: adding a module to `builtin/` does **not** register anything.
Adding a tool means adding its `register_builtin` call.

The registry is a **singleton**, and initialisation is guarded:

```python
global _DEFAULT_REGISTRY_INITIALIZED
if _DEFAULT_REGISTRY_INITIALIZED:
    return ToolRegistry.get_instance()      # early return — no re-registration
_DEFAULT_REGISTRY_INITIALIZED = True
```

The guard exists because `init_default_registry()` is called from three places
(`main.py`, `monitor_nodes`, `context_indexer_nodes`) and re-registering logged
"Tool 'X' is already registered, overwriting" at every startup. Six test files
reset `_DEFAULT_REGISTRY_INITIALIZED = False` to force re-registration.

**Consequence for tests:** the registry is process-global state. A test that
empties or re-initialises it changes what every later test sees, and the
initialisation guard means a re-initialisation may be a no-op. Tests that depend
on a populated registry must not assume they are the only ones touching it.

## The execution path

```
ToolExecutionService.execute_tool_for_agent(agent_id, tool_slug, args)
    → resolve config → validate args → registry.execute_tool(slug, ...)
    → wrap in ToolExecutionResult (to_llm_message / to_user_message / to_summary_message)
```

`registry.execute_tool` raises `KeyError(f"Tool not found: {tool_slug}")` when the
slug is not in the in-memory registry — **regardless of whether a row with that
slug exists in the database.**

## No server is required to exercise a tool

`init_default_registry()` is **in-process** and returns in ~0.5s. A test can
register, look up and execute handlers without a running backend. The tools that
do reach outward are those whose *handlers* make a call — Ollama for embeddings,
a remote provider, a local HTTP endpoint — and those are the `live` tier, not a
`backend` requirement.

## agent_id: one name, three formats

`agent_id` is not one type across the codebase. Measured:

| Where | Type | Evidence |
|---|---|---|
| tools / grant tables | `Mapped[str]` | `tools/models.py:124,271,338` |
| agents repository | `agent_id: int` | `agents/repository.py:56,60,89,206,288` |
| tool-usage log | UUID, format-checked | `tools/services.py:916` |
| the tool tests | `int` | `test_tool_access_tiers.py:128` |

**Do not infer the identity from a format-checking helper.** The usage-log check
is a tolerance guard, and its comment says so — *"This allows workflows with
non-UUID IDs to function without errors"* — so it accommodates non-UUID ids and
establishes nothing.

Changing the three `int(agent_id)` casts to `str(...)` on a UUID reading **broke
four passing tests** (`KeyError: 'Tool not found: graph-query'`). `int(agent_id)`
works for those call sites.

**The row id is the contract — for now.** An agent is addressed by its numeric
`agents.id`, and callers pass a value of that shape. The tests follow the same
rule: a numeric id for `execute_tool_for_agent`, a string for the string-lookup
paths that never cast (`get_enabled_tools_for_agent`, `list_agent_tools`).

**The deeper question is deliberately deferred.** Whether an agent's identity
should instead be its durable workspace key (the folder — which trivial and
pseudo agents do not have) or its row id (a locator storage may reuse) is an open
design question, and it cannot be settled before an agent packaging system
exists to move an agent between installations. `local/agent-packaging-and-identification/preliminary-report.md`
holds the question inventory, the identifier measured per surface, and the
analogies to borrow from. Until it is settled, the code bridges the difference by
casting — which works wherever caller and callee happen to agree, and nowhere
else.

## A GENERATED enum — when a tool's argument list must match another system

`open-page` offers a model a closed set of destinations, and that set has to BE
the app's real pages. A hand-kept list drifts; the model then gets offered a page
that no longer exists and the jump 404s.

The pattern: **generate it from the single source, commit the artifact, and gate
the two together.**

| Piece | Path |
|---|---|
| the source of truth | `frontend/src/config/routes.ts` (the route table) |
| the generator | `scripts/core/gen_page_map.py` |
| the artifact | `backend/app/domain/tools/page_map.json` |
| the loader | `backend/app/domain/tools/page_map.py` |
| the gate | `backend/tests/unit/test_page_map_sync.py` |

The gate runs the **real generator** with `--check` rather than re-implementing
its parse, so the test cannot itself drift from the thing it checks.

### The guard has to be TWO guards

A count comparison — *parsed objects vs raw `path:` matches* — is the natural
check, and **it passes at `0 != 0` is False, i.e. it passes when the parser finds
NOTHING.** A file-shape change would then emit an empty map and every test would
stay green while the model silently lost every destination.

So the generator also refuses an empty result outright:

```python
if not routes:
    raise ParseError("parsed ZERO route objects from routes.ts — refusing to emit an empty map")
```

**A check that reports "clean" over a real loss is the same failure as no check.**
This is the "never let a broken check silently pass" rule applied to generators.

### Three kinds of destination, because the app has three

- **route** — a path from the route table
- **alias** — a surface that is NOT a route (the Settings tabs are `useState`, so
  they cannot be derived)
- **tab** — an app that opens as its own tab

### The tool still does not navigate

`open-page` resolves and returns a **verified path**; the frontend moves. Which
tab a destination opens in is the frontend's convention, not the backend's.

### The synonyms in the mirror are RESOLVED, not just carried

The nav table records, per alias and per tab app, the words the app answers to
(`match: ["logging"]` for `/logs`), and those ride into the generated map. The
loader resolves them: `resolve_page`'s synonym step takes an EXACT declared word
and returns the entry whose alias/tab block declares it — so a model naming a
surface in prose (`logging`, `themes`, `session list`) lands where the person who
typed `nav logging` lands.

Exact only: a near-miss falls through to the loud miss with the nearest labels,
because opening a plausible wrong page is worse than saying "I do not know that
one". Precedence is deliberate — exact key, then exact label, then a path-ish
spelling, and only then a nickname. Two declared words are also another entry's
exact label (`message center` is the `/messages` route's title, `agent chat` is
`/agent-interaction`'s); the entry whose LABEL matches wins.

The gate: `test_page_map_sync.py` walks every `match` word in the generated map
and asserts each resolves to the block that declares it, with a floor on the
count so a broken scrape cannot make the check vacuous.

## Related

- [[dev-notes/tools/tools-architecture|Tools Architecture]] — the model
- [[dev-notes/tools/capability-error-handling|Capability Error Handling]]
- [[dev-notes/frontend/app-navigation-channels|Navigating the app]] — where the resolved path goes
- [[dev-notes/testing/test-tiers|Test Tiers]] — why a tool test needs `app`, not `backend`
