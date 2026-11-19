---
title: Consulting Agent
type: atlas-note
path: wiki/dev-notes/agents/consulting-agent.md
confidence: medium
created: 2026-08-12
updated: 2026-09-10
tags: [type/note, domain/agents, status/active, feature/external-agent]
---

# Consulting Agent

**Naming convention (2026-08-12):**
- **Consulting Agent** = the *feature/capability* — asking the external
  agent for a second opinion on agent/workflow/log questions. This note.
- **External Agent** = the *technology* — the Hermes/OpenClaw ACP
  subprocess layer (`app/domain/external_agent/`,
  `dev-notes/agents/external-agent-domain.md`).
- **`consult`** = the tool slug / registry name (code-level, short).

## What it is

Reborn the original "talk to the system agent" debugging capability
with the external agent. **KEYBOARD-TAKEOVER model (CORRECTION
2026-08-12, twice):**

The consultant is a HERMES-LEVEL agent and manages its OWN diagnostics
the same way the assistant works on this codebase — "like letting a
coworker use your keyboard for a few minutes to fix something." The
Cogitate agent may not need to know what's happening.

- **PROVEN**: the ACP session exposes the FULL toolset (terminal,
  read_file, write_file, search_files, patch, process, execute_code,
  web_search, skill_view, skills_list, memory, todo) — the consultant
  can tail logs, query traces, form hypotheses, verify, iterate.
- **READ-ONLY FIRST (decision 2026-08-12):** diagnose with read-only
  tools only. No writes.
- **FIX MODE = EXPLICIT GRANT (BUILT 2026-08-13; the 3-WAY TIER
  2026-08-21):** the Agent Integration page persists `permission_tier`
  (`chat | fix | yolo`); `fix_mode` is a DEPRECATED compat view
  (`permission_tier == "fix"`), not the stored field. Enforcement is
  TOOL-LEVEL — Hermes' edit-approval policy (`workspace_session` vs
  `ask`) + strictTools + a server-side prompt directive. First real
  GRAS/Restricted application. See [[dev-notes/agents/hermes|Hermes vendor note]]
  for the gate matrix and [[dev-notes/agents/chat-authorization|Chat Authorization]]
  for the tier.
- **Skills are the root**: orientation + analyze-logs (triage method).
- **Panel = diagnostic workspace**: hand off active session +
  symptom; consultant works (tool calls + reasoning stream visibly);
  reports findings + proposed fix. User watches; user executes fixes
  until fix mode exists.

Secondary channel (kept): the `consult` tool — agent → consultant
second opinions. May prove handy; NOT the diagnostic loop.

Boundary: the consultant never reads raw session store / DB internals
directly; it works from the project cwd + observability surfaces
(logs, traces, session history) like a human dev would.

## Roadmap

The roadmap this page records (complete; the archive itself lives on the
dev machine, not in the tree) — phases:
1. Queue rework (single-consumer → per-prompt) ✅
2. Agent-askable consult tool (second-opinion channel) ✅
3. User-askable surface (in-session dialog) ✅
4. **Keyboard-takeover diagnostic mode** (read-only) ✅ BUILT
   2026-08-12 — Diagnose button, embedded skills, live tool-call
   streaming; fix mode = explicit grant, planned
5. (parked) Tool taxonomy rewrite — GRAS + Restricted(keyed) —
   fix-mode gating is the first real application

## What was built (2026-08-12) — Phase 4 live

- **Diagnose button** on the Agent Panel (situation-aware since
  2026-08-13: renders only on a plain/Chat open — hidden when a
  context hand-off is active): reads the ACTIVE session + agent from
  `cognitiveHubStore`, embeds the Cogitate skills in the hand-off
  prompt, streams the consultant's tool calls live in the panel —
  the watchable keyboard-takeover.
- **`GET /api/v1/external-agent/skills/{name}`** — consult-tool-
  injected delivery: WE read the SKILL.md and include it in the
  prompt. Hermes' OWN skill loader cannot see repo skills (verified
  live: it reported "both requested skills don't exist" when told to
  load them itself).
- **`AcpClient` routes `tool_call` events** (were dropped); the WS
  forwards them as `{"type": "tool_call", "update": {...}}` — Hermes
  sends `sessionUpdate: "tool_call"` with `{kind, locations, title,
  toolCallId}`.
- **Skills built**: `orientation` + `analyze-logs` (below) +
  `macro-management` (2026-08-13, the Macros-page builder hand-off:
  discover-then-write macro sets + meta-topics via the API) +
  `create-agent` + `create-workflow` (2026-08-14 — the
  Profiles/Workflow-Templates builder hand-offs; create-workflow
  required the template CRUD fix first, see known-issues). The
  loader validates all PASS.
- Live proof: Diagnose → the consultant greps `app.log` for the
  session id, scans ERROR/WARNING surfaces, inspects
  `pipeline_traces.db`, checks processes + git state — all its own
  loop, read-only.

Known limits (2026-08-14; defaults raised 2026-08-22/09-08): the
whole-turn caps now EXIST — `max_turn_seconds` (default 900, 0 =
unlimited, Exa Agent page) and `max_tool_calls_per_turn` (default 75);
a run that exceeds either auto-halts via the two-stage stop and reports
`time_limit` / `tool_call_limit`. The 120s per-event wait is unchanged.

## Making the consultant effective — the Cogitate skills

The consultant is only as good as its knowledge of Cogitate
**conventions**. Skills (SKILL.md files in the repo, the
restart-cogitate pattern) are the vehicle. **BUILT** (first asset
class):

1. **`skills/cogitate/orientation/SKILL.md`** ✅ BUILT — the map:
   repo layout, where truth lives (wiki atlas, dev notes), verify
   commands (health, validator, sweep, tests), diagnostic context
   (logs, traces, DBs, the UI bridge). Loaded first.
2. **`skills/cogitate/analyze-logs/SKILL.md`** ✅ BUILT — the triage
   method below, as a skill with the full diagnostic loop
   (tail → cluster by timestamp → grep the real signal → verify →
   report with evidence).
3. **`skills/cogitate/create-agent/SKILL.md`** ✅ BUILT — agent creation:
   API shape (`POST /agents`), fields (system_prompt, cognitive
   profile, provider/model, image), gotchas (tool gating lives in
   AgentToolManager, not chat-time; canonical image URLs), verify
   steps (agent card loads, profile page shows it).
4. **`skills/cogitate/create-workflow/SKILL.md`** ✅ BUILT —
   workflow construction: template → nodes → triggers, the
   distribution layer (file/display/toast), static-before-dynamic
   route gotcha, triggers ship DEACTIVATED, verify (Execution page
   runs, product lands in Products).

Each skill includes **verify steps** that hit the real system — a
consultant must check its own claims (curl the API, run the workflow,
tail the log). That is the consultant value: report what you
actually see, not what you assume.

## Rooting the consultant

Three layers:

1. **cwd** (have it) — project root as working directory; reads wiki,
   code, logs, skills directly.
2. **Context primer** — `skills/cogitate/orientation/SKILL.md`:
   "You are consulting on Cogitate: wiki/atlas = UI/API truth,
   wiki/dev-notes = hard-won lessons, logs at backend/logs/app.log,
   API at localhost:8000, atlas documents every router." Read first,
   every consult starts oriented.
3. **Verification** — skills' verify steps hit the real API/logs.

## RAG — improving the consultant WITHOUT giving it RAG

The clean integration, respecting the boundary: the **consult tool's
context builder** uses Cogitate's existing RAG index (wiki/entities +
wiki/dev-notes via sqlite-vec) to retrieve the top-k relevant
snippets, and passes them **as context** in the prompt to Hermes.

- Cogitate does the retrieval (it owns the index); we curate what the
  consultant sees; Hermes reasons over the snippets.
- No new Hermes tooling; our RAG index is never exposed to the
  external process.
- Value: semantic questions ("which dev note covers the modal bug?")
  and knowledge-base growth past the context window.

## Skill delivery — consult-tool-injected (decision)

How skills reach Hermes:
- **(a) Project-loaded** — point Hermes at `skills/cogitate/`; its own
  loader surfaces them. Requires Hermes-side config.
- **(b) Consult-tool-injected** — the consult tool reads the relevant
  SKILL.md (task type from the agent's request) and includes it in
  the prompt. Zero Hermes config; works for any ACP agent.
- **DECISION (2026-08-12): (b)** — keeps Cogitate in control of what
  the consultant sees; same injection point RAG will use.

## Synthesis

**Skills-as-content (repo) + consult-tool-injection (delivery) +
RAG-retrieval (context enrichment) — all on our side of the boundary.**
