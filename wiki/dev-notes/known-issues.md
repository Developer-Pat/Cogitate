---
title: Known Issues
type: atlas-devnote
category: dev-notes
order: 99
confidence: high
created: 2026-08-11
updated: 2026-09-10
tags: [type/dev-notes, domain/dev-notes]
---

# Known Issues

Operational quirks, non-obvious behaviors, and noise sources —
things that look wrong but are expected, or are known-broken and
tracked. When something surprising shows up (log noise, phantom
activity, a modal that won't open), check here before debugging.

## 3 frontend tests fail on a clean tree — `AgentService.test.ts`

**Found:** 2026-09-11, while shipping the Deselect/Kill buttons.
**Status:** latent — no user-visible effect, but it makes "the suite is
green" a false statement, and a real regression in this file would hide
inside the noise.

`npx vitest run` on a **clean** working tree reports **584 passed / 3
failed**. All three are in
`src/services/domain/__tests__/AgentService.test.ts`, all the same cause:

```
TypeError: profileService.clearAll is not a function
  at AgentService.clearCache (src/services/domain/AgentService.ts:193)
```

`AgentService.clearCache()` calls `profileService.clearAll()`, but the
service or its mock no longer exposes `clearAll` — a stale test against a
renamed or removed method, not a production defect (`clearCache` is only
reached from the tests today).

**Proven pre-existing** by stashing the working tree and re-running the file
alone: identical 3 failures, 19 passed.

**Do not** read a 3-failure run as "your change broke it." Baseline it
first: `npx vitest run src/services/domain/__tests__/AgentService.test.ts`.

## The agent-chat stale-context race — FIXED

**The audit** (the user's ask: does the agent chat suffer from the
Exa bugs?): the agent-chat's send is a single-response REST call —
the closure-capture CANNOT apply (the message's passed directly to
the pipeline; the SSE's a read-only trace-poller). BUT the pipeline
was unguarded: two quick sends to the same session ran CONCURRENTLY
— the second's history-read happened BEFORE the first's save (the
stale context, the agent-chat cousin of the every-other).

**The fix**: the per-session asyncio lock — the same-session sends
serialize (the history read + the pipeline + the commit inside the
lock). Verified: the two concurrent sends' wall-clock ≈ the serial
sum (4.2s + 1.7s) + the session's rows land in order.

## The Exa every-other input skip — FIXED

**Symptom**: the Exa chat skipped every other input — two quick
messages produced ONE response (the agent answered the SECOND, the
first's text was never seen).

**Root cause**: two bugs in the ws handler's prompt path —
1. THE CLOSURE CAPTURE: the `_stream_run` task captured the main
   loop's `data` variable BY REFERENCE; the loop's reassignment on
   the next message leaked into the RUNNING task, so the agent's
   first turn got the SECOND prompt's text (the log: "Prompt on
   session: Now say goodbye" with history=0 — the first prompt
   never reached the agent).
2. THE CONCURRENT STREAM: no busy-guard — a prompt during a stream
   started a second concurrent `stream_prompt` (the ACP allows one
   active prompt per session; the interleave corrupts the turns).

**The fix**: the default-arg capture pins the task's prompt
(`def _stream_run(prompt_data=data)`) + the PROMPT QUEUE (the
overlapping prompts queue behind the busy-guard + the stream's end
wakes the drain via a `_stream_ended` sentinel) — the turns are
always sequential. Verified: two back-to-back prompts → two aligned
replies (Hello → Goodbye).

Test sweeps generate warning noise in the logs (2026-08-11)

Running the test suites / sweeps writes **warning and error lines
into `backend/logs/app.log`** — they are NOT app failures.

- **~85% of all warnings in the log are test-generated.** The
  tests deliberately exercise failure paths (mocked providers
  down, `disk full`, `connection refused`, invalid tools, unknown
  templates, `FNBot` fallback chains), and those mocks log
  warnings at WARNING/ERROR level.
- **How to tell test noise from real problems:**
  1. **Timestamp clustering** — warnings cluster in the exact
     minutes a pytest/sweep run happened (e.g. all of
     `07:40–07:44`, `07:57–07:59`, `08:03` in one session).
     Real app warnings are spread across normal usage.
  2. **Content markers** — `wf-test-*`, `test-template-*`,
     `invalid-tool-id`, `nonexistent-*`, `boom`, `FNBot`,
     `Intentional failure`, `id=x` are test fixtures.
  3. **Source** — `app.workflows.*` test artifacts vs
     startup-time registrations (e.g. `init_default_registry`)
     which run on every boot regardless of tests.
- **A real bug found this way (2026-08-11)**: the
  `Tool 'macro-manager' is already registered, overwriting`
  warnings at every startup were NOT test noise — they exposed a
  duplicate registration in `init_default_registry()` (two
  `register_builtin` calls for the same tool). Fixed.

**Rule of thumb**: warnings at startup/reload time are real;
warnings clustered during known test runs are usually expected.

## Ghost databases — sqlite creates empty files for wrong paths (2026-08-13)

`sqlite3.connect(path)` (and aiosqlite / SQLAlchemy URLs) **silently
CREATES the file if it doesn't exist**. Connect to a wrong or typo'd
path and you get a 0-byte ghost DB that the sweep's ghost scan flags.

- **Symptom**: `scripts/core/sweep.py backend` fails the *Ghost
  database scan* — a `.db` file under the repo root that is < 1 KB
  and not a canonical DB. Example: `data/cogitate.db` (0 bytes).
- **The canonical main DB is `./cogitate.db` (project root)** — NOT
  `data/cogitate.db`. The `data/` dir holds the derived/side DBs
  (`cogitate_docs_en.db`, `pipeline_traces.db`, `cognitive_memory.db`,
  vector DBs).
- **Cause found live**: a probe script connected to
  `data/cogitate.db` (wrong relative path) while looking for a
  table — sqlite created the empty file instantly.
- **Rule**: before opening a SQLite path, verify it exists
  (`Path.exists()` / `os.path.isfile`) — or use the path from
  `app.core.config` (BASE_DIR-anchored), never a guessed relative
  path. Agents/scripts that go straight to a DB path are the usual
  ghost creators.
- **Fix**: `rm <path>` (it's 0 bytes; nothing to lose). The scan's
  canonical-DB + skip-prefixes (backups, trash, caches) already
  protect the legitimate files.

## Test pollution of the live data store (2026-08-11, fixed)

Deliver-node tests used to write real products + toasts into
`data/monitor/` — the frontend toast poller then drained them as
**phantom workflow activity** (toasts appearing with no active
trigger). Fixed: deliver tests isolate via
`monkeypatch.setattr("...distributors._products_dir", lambda: tmp_path)`.
**Any new test that calls a deliver node must isolate the store
the same way** — the workflow suite asserts zero pollution.

## DaisyUI `modal-box` — mask with no box (2026-08-14, RECURRED)

**Symptom**: clicking a button that should open a modal shows a
dark mask/overlay but the dialog itself never appears. Clicking
the mask closes it.

**Root cause**: the modal markup used DaisyUI's `modal-box` class
inside a **plain fixed overlay div** (`fixed inset-0 ... bg-black/50`
+ `modal-box` child). DaisyUI's `modal-box` defaults to
`opacity: 0` — it is only revealed by a parent `.modal.modal-open`
wrapper. The mask is real; the box is transparent. Computed style
shows `opacity: 0` on the box.

**Hit twice**:
- 2026-08-11 — ProfileImagePicker (browse-store modal): fixed via
  portal + explicit classes (see
  [[dev-notes/frontend/modal-dialogs|Modal Dialogs]]).
- 2026-08-14 — WorkflowProducts report viewer + Clear confirm
  (user: "the view button does not produce a view. It looks like a
  mask for a modal dialog without the modal dialog ever showing
  up"). Fixed by replacing `modal-box` with a plain styled
  container (`rounded-2xl bg-base-100 text-base-content
  shadow-xl`); live-verified `opacity: 1`. Regression tests in
  `WorkflowProducts.test.tsx` assert the container has NO
  `modal-box` class.

**The rule**: never use `modal-box` unless the parent is the full
DaisyUI `.modal modal-open` wrapper or a `<dialog>.showModal()`.
Audited 2026-08-14: 10 of 13 uses are safe (`.modal.modal-open`
wrapper or native `<dialog>`); the broken pattern is a plain
`fixed` div + `modal-box`.

**RECURRED 2026-08-18** (scheduler modal + the products delete
modal): `modal-box` renders at **48px wide** in this Tailwind
v4/DaisyUI setup — the width classes (`max-w-lg`) do nothing.
Measured via getBoundingClientRect. Fixed with the documented
pattern + the width var (`min(var(--dialog-width-md), 95vw)`) +
`p-6`. The modal-dialogs note has the full recipe.

**RECURRED 2026-08-25 — the 4TH/5TH HIT** (the PackageTab detail +
confirm modals): `modal-box` again → 48px again. The user: "this
is the 4th or 5th time we have had this problem." Fixed by copying
the SchedulerModal's pattern verbatim (the plain fixed overlay +
the plain container — NO modal-box at all). The modal-dialogs note
now LEADS with the copy-paste template + the measure-verify step —
the recurrence is designed out.

## Ollama tool calls silently become JSON text in chat/stream (2026-08-14, FIXED)

**Symptom**: with a local Ollama model (qwen3, etc.) + tools
enabled, the agent answers with raw JSON like `{"name":
"calculator", "arguments": {...}}` instead of calling the tool.
`metrics.tool_calls` stays 0 and the tool never executes.

**Root cause**: LiteLLM treats the `ollama` provider as
function-UNSUPPORTED (`litellm/utils.py:3731`): it forces
`format=json` and injects the tools as *prompt text* instead of a
structured schema. Capable models (qwen3) then emit the tool call
as JSON content; the streaming path never sees `delta.tool_calls`,
so the tool loop doesn't run. LiteLLM's `ollama_chat` provider is
the tool-capable handler (in the supported list at utils.py:3724).

**How we found it** (the investigation trail — save yourself the
hours):
1. User asked to live-test `metrics.tool_calls` with a local model.
   The model never called the tool — it emitted JSON as text.
2. Isolated the variable chain — what WORKS and what DOESN'T:
   - Native Ollama `/api/chat` streaming → ✅ proper `tool_calls`
   - LiteLLM non-streaming (`stream=False`) → ✅ proper `tool_calls`
   - LiteLLM `ollama` + streaming → ❌ JSON-as-content (the bug)
   - LiteLLM `ollama_chat` + streaming → ✅ proper `tool_calls`
3. LiteLLM debug logs revealed the smoking gun:
   `Final returned optional params: {'format': 'json',
   'functions_unsupported_model': [...]}` — LiteLLM had classified
   `ollama` as a functions-unsupported provider and forced JSON
   mode, turning the tool schema into prompt text.
4. `tool_choice` did not help (it never reaches Ollama — the
   format=json + prompt-text path bypasses it).

**The update we tried (did NOT fix it)**: upgraded litellm
1.83.0 → 1.96.2 (pyproject pin `>=1.81.15`, so in-spec; later
raised to `>=1.96.0`). Upstream PRs #11171/#6155/#11528
(streaming tool-call parsing for Ollama) suggested newer versions
might help — but the provider-classification bug at utils.py:3731
persisted. The upgrade is still a good thing (kept), it just
wasn't the fix.

**The work-around (our fix)**: `litellm_route.litellm_model_string()` (the
domain's ONE mapping, since 2026-10-12) maps the DB provider `ollama` →
`ollama_chat` for the LiteLLM model string (api_base lookup unchanged).
Applied in the stream path (context.py), the delegate path (chat/router.py)
and the failover rebuild. 18 regression tests (test_litellm_route.py).

**LIVE-VERIFIED**: qwen3 + Calculator via the app stream — tool
executed, 1234×5678 = 7,006,652 returned, trace persisted
`tool_calls: 1`.

**Lesson**: when a capable model "refuses" to use tools, check the
LLM-gateway's provider classification before blaming the model —
LiteLLM has TWO Ollama providers (`ollama` = legacy/unsupported,
`ollama_chat` = tool-capable) and silently downgrades tool calls to
prompt text on the legacy one. Same class of trap exists for other
providers listed as function-unsupported at utils.py:3731.

## Workflow template write-path entirely missing (2026-08-14, FIXED)

**Symptom**: the WorkflowTemplates page's **New Template** button
opened nothing; editing an existing template's Save never
persisted; Execute appeared to work only on the 33 SEEDED
templates.

**Root cause** (three layers, found while scoping the
create-workflow skill):
1. The backend had only `GET /workflows/templates` +
   `/categories`. **POST/PUT/DELETE /workflows/templates → 405/404**
   — the editor's create/update/delete paths hit nothing. The 33
   templates are seeds.
2. The editor validates before EVERY save via
   `POST /templates/validate` (also 405) and before execute via
   `POST /templates/{id}/validate-execution` (404) — so even a
   working CRUD couldn't be reached through the UI.
3. Frontend: `handleCreateNewTemplate` set `editingTemplate(null)`
   but the render gate is `showEditor && editingTemplate` — the
   editor NEVER opened for creates.

**Fix**: full CRUD + both validate endpoints in
template_router.py (config/inputs are free-form JSON; validate
checks name + steps, execution-inputs checks required keys).
Frontend: New Template seeds a skeleton (`id: ''` = create mode).
**Pitfall hit live**: `validate-execution` binding — the frontend
POSTs the body WRAPPED (`{inputs: {...}}`); binding the raw body
as the inputs dict made every required-key check fail silently
(always "Missing required input"). Match the frontend's wire shape.

**The pattern**: when the UI calls an endpoint that doesn't exist
(405/404), check the WHOLE write path — the missing half usually
has siblings. Live-verified end-to-end (Create → fill → save → DB
row → cleaned); 9 regression tests.

## Phantoms and stale UI

- **Vite restarts break HMR for open tabs**: after killing and
  restarting the Vite dev server, already-open tabs keep running
  the OLD JavaScript bundle until hard-refreshed (`Ctrl+Shift+R`
  or a fresh tab). "I fixed it but the user still sees the bug"
  is usually this.
- **Modals**: DaisyUI `modal-box` renders as an invisible panel
  in this app's Tailwind v4/DaisyUI setup — use the documented
  working pattern (`bg-base-200 rounded-lg shadow-xl` +
  `z-[9999]`), see [[dev-notes/frontend/modal-dialogs|Modal Dialogs]].
- **Composition facility was three latent bugs deep (2026-08-14,
  fixed)**: the `workflow_compositions` table was never
  created by any migration (early service runs created it ad-hoc
  outside alembic); `build_composition_graph` returned an
  UNCOMPILED StateGraph while the service called `.invoke()` (every
  execution failed with `'StateGraph' object has no attribute
  'invoke'`); and the execution node dispatched through the
  multi-agent service only, so monitor/simple/chain templates
  failed (their config is `{feeds, max_items}`, not a
  MultiAgentConfig). All three fixed: the table is an ORM model now
  (and create_all builds it), compile in the service + kind policy injection, and the
  general workflow executor. Also: composition CRUD tests wrote
  ~1650 `test-comp-*` rows to the LIVE DB (the recurring
  test-pollution pattern) — fixed with a temp-DB fixture.
- **Compositions need ≥2 workflows**: the WorkflowComposition
  schema enforces it (`List should have at least 2 items`) — the
  building-block contract, not a bug.
- **System Info page REMOVED (2026-08-16, pre-push Phase C)**: the
  monitoring page (status/CPU/memory/disk/health checks) is gone —
  monitoring isn't the product. The RAG tab became the standalone
  RAG Index page (/rag-index). The Dashboard QuickStats tiles are
  summary-only (no /system-info link). KEPT: SystemHealthCard +
  useSystemHealth/useSystemMetrics (the dashboard + the sidebar
  status indicator consume them) + the backend /system/* +
  /diagnostics endpoints (the API surface, verified in Phase B).
- **Lifecycle UI (2026-08-16, agent-lifecycle Phase D)**: the
  delete dialog discloses the BOM (tool links, memory, workspace),
  the delete response is the result report (BOM + archive path),
  the restore view (GET /agents/deleted + POST /{id}/restore)
  re-imports a deleted agent ADDITIVELY. Pitfalls: (1) the
  /deleted route MUST register before /{agent_id} (FastAPI
  path-param order); (2) soft-deleted agents are now EXCLUDED from
  the live pool (list/resolve/select filter deleted_at IS NULL —
  the registry contract); (3) ProfileDetail needs a Router in
  tests (useNavigate); (4) missing workspace_key mapping in
  convertToProfile hid the depth marker until fixed.
- **Recoverable delete (2026-08-16, agent-lifecycle Phase C)**: the
  DELETE endpoint now returns the REPORT (200) not 204 — the row is
  SOFT-deleted (deleted_at + archived_path), the
  workspace MOVES onto the trash's agents shelf
  (`trash/agents/<key>-<ts>/`, never hard-deleted), relational rows
  removed, history KEPT. The
  regression test was updated (soft-delete assertions + expire_all
  — the client's commit is invisible to a stale test_session copy).
  Pitfall: shallow agents (no workspace_key — created via the
  service directly) archive nothing — archived_path is None.
- **Repository seam (2026-08-16, agent-lifecycle Phase A)**: the
  storage seam — AgentRepository ABC + DiskAgentRepository + the
  factory; agents.workspace_key column (0070, backfilled:
  researcher→45, system-manager→48; math-tutor left NULL — its
  agent.json lacks db_id, the scaffold phase fixes it).
  export_service's folder-scan heuristic replaced by
  agent_workspace() (the column read). Pitfall: the remaining
  os.listdir in export_service is the SKILLS listing — legitimate.
- **Workflows address via the registry (2026-08-16, ARM Phase D)**:
  agent steps accept `agent_name` (registry identity) + resolve
  STRICT via resolve_agent; the AgentDistributor hands a product
  to a named agent (file-it → agents/<name>/inbox/; hand-it-a-task
  → a chat session + message — live: Bob received + responded).
  The distributor is sync by ABC contract but resolves via
  asyncio.run — tests must call deliver in a THREAD (no nested
  loop) + inject the session factory bound to the test engine
  (a fresh engine on the conftest temp DB sees NO tables).
- **Agent select + tool sync (2026-08-16, ARM Phase B)**: the
  agent-select tool (yellow pages) + THREE startup-sync bugs found
  + fixed in auto_sync_tools (main.py): (1) the flush was once,
  not per-tool — the insertmanyvalues sentinel crash at 34 tools
  (the comment SAID flush individually but the code flushed once)
  → per-tool flush; (2) the session was autocommit=False with NO
  commit — the sync silently rolled back every startup → explicit
  commit; (3) capability/access_tier weren't carried on upsert →
  now synced. UUID-form pitfall (the recurring one): agent_tools
  rows inserted via raw sqlite with a hyphenated tool_id BREAK the
  ORM lookup — the ORM reads UUID columns hyphen-LESS; store the
  hyphen-less form. Also: AgentResponse.skills was
  required-but-nullable (the unique-name table rebuild left NULL) →
  Optional. Selection: the capability criterion matches the
  CANONICAL vocabulary (Tool.capability), not provider slugs.
- **Registry addressing (2026-08-16, ARM Phase A)**: the white
  pages — agents.name is now UNIQUE (rebuilt the
  table in SQLite batch mode; the 5 shallow test agents — Test
  Agent, Test 3A, probe-tmp-1, O Tool, Researcher-imported — were
  removed, 18 → 13). Create rejects exact-name duplicates with a
  clear 400; resolve_agent(name) is STRICT (404 on missing); GET
  /agents/by-name/{name} is the lookup surface. Pitfall: alembic
  ALTER on the SQLite constraint fails — must use batch mode; the
  Agent MODEL needed unique=True so the test DB matches the
  migration. The lifecycle todo (thoughtful create/delete for
  deep agents) is tracked in master.md.
- **ARM resource card (2026-08-15, Phase F)**: the agent card
  endpoint (/agents/{id}/card) now carries the `arm` block —
  depth (cognitive profile name), competence (declared skills),
  spec (provider location/size — the new classifier), capability
  (enabled tool slugs). The selection surface the ARM project
  will read; skills also flow through AgentCreate (migrations
  0065 cognitive mapping, 0066 skills column). 7 arm-card tests.
- **usage_count + contract audit (2026-08-15, Phase E)**: the
  usage_count column was DEAD (sum 0 despite 144 usage logs) —
  two causes: (a) log_usage's increment looked up tool_id with
  the hyphenated runtime form against hyphen-less raw rows (the
  recurring UUID-form split — fixed with _norm_uuid), and (b)
  log_usage SILENTLY SKIPS non-UUID agent_ids (e.g. Bob = 19)
  before reaching the increment. Fix: execute_tool_for_agent now
  increments usage_count directly on every successful call
  (live-verified 0 → 2). The contract audit (_validate_tool_
  contracts) now checks handler signatures vs arguments_schema —
  a required param the schema omits is flagged loudly at startup
  (the soft-failure pattern, proposal Phase 1); the real registry
  passes clean.
- **YOLO button + run grants (2026-08-15, Phase D)**: the
  fix-mode toggle is now a deliberate, immediate, session-scoped
  button (POST /external-agent/fix-mode — study 14). The grant
  rows under agent_id="external" are the INSPECTABLE RECORD, NOT
  the gate (Exa is decoupled — its real gate is ACP strictTools);
  documented honestly. Workflows can declare tool_grants on
  execute → run-scoped grants issued at dispatch, revoked at run
  end (the declarative ARM path). **Pitfalls hit**: (a) migration
  0064 inserted hyphen-less tool_ids → 10 orphan grants the
  runtime couldn't see/revoke (the _norm_uuid lesson again) —
  normalized; (b) uvicorn --reload served stale workflow_router
  code (tool_grants silently ignored) until a manual restart —
  the recurring reload hazard.
- **Keyed-tier access control (2026-08-15, Phase C)**: tools
  whose capability is keyed (file-write, db-write, clipboard-io,
  the admin family, todo-mgmt) now need an explicit grant
  (`agent_tool_grants`: agent, tool, granted_by user|exa|system,
  scope session|permanent|run:<workflow_id>, expires_at) before
  `execute_tool_for_agent` runs them — else `ToolKeyRequired`
  (dead-letter, not a hang). GRAS tools (read) keep the enabled
  check only. **Pitfall hit**: the runtime's `tool_def.id` is the
  hyphenated UUID form but raw sqlite3 reads return hyphen-less —
  the grant service normalizes (`_norm_uuid`) so lookups match;
  grants inserted via raw SQL must use the hyphenated form.
  Live-verified all three paths; 11 access-tier tests.
- **Toolbox layer + tool-crib removed (2026-08-15, Phase B —
  removal record)**: the team→toolbox assignment layer was REMOVED
  after existing in code with NO table (the half-built pattern,
  like composition pre-fix);
  `team_tools` had 4 stale rows from 2026-04-03; the tool-crib
  (checkout/checkin tool lifecycle) was registered with ZERO
  agents linked. Both cut per the tooling study (page 08: the
  many-to-many pain). Also removed: 7 DB-only orphan tools
  (boris-* ×2, calc_*/e2e ×4, check_schema, test-tool-1), the
  echo handler, "checked out from tool-crib" docstrings, the
  "Checkout X from tool-crib" skill instructions, and Boris-era
  description prose (6 tools — the LLM-facing contract). Verified
  by 8 cruft-removal tests; 42 → 33 tools.
- **A tuple-order bug that "succeeded" silently (2026-08-14,
  fixed)**: `record_execution_complete` had the
  metadata value appended AFTER `execution_id` in the params tuple
  while the SQL had `metadata = ?` BEFORE `WHERE id = ?` — so the
  WHERE clause got a JSON dict, matched nothing, and the update
  was a silent no-op (status stayed 'started', no error, no
  warning). Lesson: when extending a parameterized UPDATE, the
  tuple order MUST mirror the SQL column order; verify with a
  rowcount check, not just 'no exception'. Also: partial-write
  failures (execute_code edits that print ✅ but don't land) —
  always READ BACK the file to verify signature/SQL changes.

## Exa's tools have silent contract traps (2026-08-17)

The Exa capability probes (QA Phase C) found TWO tool-contract
traps — both produced confident-but-wrong agent conclusions:

1. **The search tool treats regex alternation as a LITERAL**
   (Hermes-native search_files). A pattern like
   `deleted_at|archived_path` returns ZERO matches even when both
   fields exist (models.py:146 HAS `deleted_at`). Exa searched
   the repo, got 0, and reported "deleted_at and archived_path do
   not exist" — FALSE. Single-term searches work; multi-term
   alternation silently false-negatives. The agent cannot detect
   this. **Lesson**: multi-term patterns need separate single-term
   searches (or structured tools that don't need regex).
2. **The pagination trap** (FIXED 2026-08-17): the agents list
   defaulted to page_size=10; Exa got 10 of 14 agents and
   reported "10 agents" with `total: 14` sitting in the response.
   Bounded collections now return the FULL LIST by default —
   pagination is UI opt-in. **Lesson**: API defaults should serve
   the complete truth for bounded collections; clients (agents
   especially) don't reconcile `total`.

3. **The ripgrep-missing silent-empty** (2026-08-21, found by Exa):
   `search_files` returned 0 for EVERYTHING when ripgrep wasn't
   installed — the `find` fallback matches FILENAMES, so a content
   pattern like `import|class|def` across 22 Python files returned
   0 hits with NO error. Exa initially reported "the repo search
   came back empty", then ran a control test, found `rg: command
   not found`, ruled out ignore-rules via git check-ignore, and
   CORRECTED its own claim. Two deeper facts: (a) `_has_command`
   caches per-process — a process spawned before the install
   believes rg is absent until restarted; (b) the tool's contract
   fails silent-empty instead of erroring. FIXED LOCALLY (uncommitted,
   hermes-agent repo): the fallback now logs a warning AND surfaces
   a `warning` field in the SearchResult — the degradation is loud
   on both channels. Upstream report queued (the fix is PR-ready;
   the stale-cache wart is the maintainers' call).

Both are the same class: **the tool's contract is subtly wrong in
a way that produces a confident false conclusion the agent can't
detect.** The mitigation direction: purpose-built structured
tools (list-agents, list-workflows) over raw terminal/search —
typed data removes the ambiguity class.

## The tier-vocabulary trap — a declared tier outside gras/keyed becomes GRAS (2026-08-19, FIXED)

`tier_for()` falls back to `gras` for ANY unknown slug — including
a tool's declared `access_tier`. `restart-backend` declared
`access_tier="admin"` (Phase 2); the runtime treated it as GRAS
(the handler's own fix-mode gate still protected it). The declared
tier must be the canonical `gras`/`keyed` — fixed. A
future guard: the registry should validate `access_tier` against
the vocabulary at registration.

## The RAG ingest cadence is a policy decision (2026-08-19, OPEN)

The whole-wiki index is CURRENT (506 files/3527 chunks, 2026-08-19)
but nothing re-ingests it automatically — the 2026-06-11 staleness
is how it got here. Options: a startup incremental, a trigger, or
a wiki-change hook. OPEN — not decided.

## `workflow_triggers` has NO declared FK (2026-08-19)

The triggers→templates relationship is IMPLICIT (no FK constraint).
The derived FK walk (Phase 5) needed the semantic-edge layer — a
declared-FKs-only walk would have missed the most important edges.
If the schema is ever normalized, add the constraint.

## The AgentDistributor is sync-only (2026-08-17, carried)

Its `asyncio.run()` cannot nest inside a running event loop — an
async caller hits "asyncio.run() cannot be called from a running
event loop". Production calls it sync; documented, not fixed.

## The EMPTY-completion phantom bubble — the model streamed 42s and said nothing (2026-09-02, FIXED)

**Symptom**: Bob's turns occasionally ended with an EMPTY assistant
message — the DB row existed with content='', replaying as "Bob
said nothing". Bob's own recoveries claimed "the thread got cut
off" (he genuinely never saw the failed turn). The usage logs
told the story: pt~2800, ct=0 — the model streamed chunks for
15-42s and produced ZERO completion tokens, an intermittent
provider-side empty completion.

**Root cause — TWO layers**: (1) the empty completion itself is a
transient model behavior (streaming the empty turns' requests
again succeeds); (2) the REAL bug was the system's handling: the
stream wrapper (`_stream_llm_response`) STORED the empty result
BEFORE validating, so the main loop logged "No tool calls -
conversation complete" and finalize PERSISTED an empty assistant
message. The wrapper's no_content error fired only to the
frontend stream — never prevented the empty DB save.

**The fix (three parts)**: (1) THE WRAPPER FLAG — an empty
completion (chunks but no content AND no tool calls) is never
stored as a usable result; the holder carries
`empty_completion=True` with chunk counts. (2) THE ONE-SHOT
RETRY — the main tool loop sees the flag and retries the SAME
request once (tools intact, history untouched) before the visible
fallback; empty completions are transient, so the retry heals
them. (3) THE FINALIZE GUARD — an empty assistant message is
NEVER persisted; the refusal logs session/model/provider loudly
and the metadata carries `empty_guard=True`. Log markers:
"EMPTY COMPLETION DETECTED" / "EMPTY COMPLETION RETRY" /
"EMPTY-MESSAGE GUARD".

**Lesson**: a stream that produces chunks-but-no-content must be
treated as a FAILED turn, never a completed one — and a message
row with empty content should be structurally impossible to
persist.

## The DOUBLE-glitch — the deep pass re-answered tool turns (2026-09-02, FIXED)

**Symptom**: EVERY tool-using Bob turn doubled — one message
contained two complete, differently-phrased reports glued
together ("…for a fuller picture?Here's what the alternative
boards…", msg 52 = 3,606 chars, msg 56 = 2,977 chars, each with
two full reports).

**Root cause — two compounding defects**: (1) THE STALE TOOLS
TRIGGER — Bob's cognitive profile (chat-skill) is
`executor=hybrid`, and the conduit routed HYBRID whenever
`tools_were_used`. But in the streaming router the tool loop
already runs until the model writes its FINAL text answer — the
synthesis happened; re-answering duplicated the whole report.
History: an earlier change had deliberately disabled conduit
auto-routing ("always SHALLOW — auto-routing confused the
user"); a frontend profile-cache fix 22 minutes later
accidentally re-enabled the HYBRID branch. (2) THE
APPEND-OVER-REPLACE MERGE — the router's HYBRID branch stored
`first_pass_content + deep_content` even though its own deep-pass
prompt says "the previous answer was insufficient — provide a
thorough response" (REPLACEMENT semantics). The canonical
`HybridExecutor` returns only the deep text; the router glued
them.

**The fix**: (1) `conduit.py` — `tools_were_used` no longer
forces HYBRID; the deep pass fires only for genuinely
insufficient first passes (content < 500 chars, or deep-keyword
queries). Tool turns now route SHALLOW — one pass, one report.
(2) `router.py` — when HYBRID does fire, the deep pass REPLACES
the first pass (deep content when non-empty; first pass only as
a fallback), matching canonical semantics.

**Lesson**: "tools were used" is not a signal that the answer is
incomplete when the tool loop already produces the final text —
and a second pass prompted to "provide a thorough response" is a
REPLACEMENT, never a continuation to append.

## Related

Its `asyncio.run()` cannot nest inside a running event loop — an
async caller hits "asyncio.run() cannot be called from a running
event loop". Production calls it sync; documented, not fixed.

## The frontend log funnel's single-endpoint 500s — OPEN

**Symptom**: `POST /api/v1/logs/frontend` intermittently 500s — the
funnel receives entries but not every flush lands in
`backend/logs/frontend.log`.

**Current state**: the failures are absorbed by design — a dropped
log can never trip the app's outage signal (the flush opts out of
outage tracking) and the entries still render in the Logs page's
in-memory store. A dedicated dig is queued.

## The notify feed's fresh-load warm-up gap — OPEN (behavior)

**Symptom**: an arrival in the first seconds after a page reload can
miss the Message Center (the feed reconnects after the load).

**Current state**: a re-send / re-run (the Messaging Test Center's
Full Test) is the workaround. The test suite's arrival windows count
visible time only — a backgrounded tab's throttled stream must never
false-fail it.

## The reasoning-model budget behavior — OPEN (mitigated)

**Symptom**: a thinking-first model (deepseek-v4, ox-alpha, the
r1/-r families) can return an EMPTY completion — it spends the
entire `max_tokens` budget reasoning, the stream ends with zero
content and zero tool calls, and the user gets the "The tool-path
fell back" warning + a tool-less answer (or, pre-fix, a generic
apology).

**Current state**: the chat route floors the output budget to 16k
for detected reasoning models (`is_reasoning_model` +
`effective_max_tokens` in reasoning_support.py). Residual open
bits: (1) the detection is name-pattern based — an unrecognized
thinking-first family on a capped path can still empty; (2)
reasoning beyond the 16k floor repeats the chain (the fallback
then answers without tools — by design, with the visible
warning); (3) the infinite-loop-blocked fallback (the loop guard
in generate_stream) builds minimal kwargs and predates the
full-request inheritance — its api_base/key ride is unverified.

## Two sources of truth that disagree — the day's dominant shape

Two parts of the system read the same fact from different places and
disagree — silently, because each reader is individually correct.
Four faces, all in the agent/clone surface (the long-form narrative is
[[dev-notes/agents/agent-cloning|Agent Cloning]]):

- **The write schema.** `AgentCreate` inherits its fields from a base;
  `AgentUpdate` re-declares them by hand. The hand-written list drifts:
  ten columns were dropped on every PUT and an assigned profile image
  never stuck. Guarded by
  `backend/tests/unit/test_agent_schema_contract.py` (the contract
  test) and `backend/scripts/audit_agent_schema.py` (the audit).
- **A value altered in transit.** The frontend prefixed its own origin
  onto an image URL; the edit form wrote the absolute value back into
  the DB, so the row and the page disagreed about the same URL.
- **A duplicate client-side cache.** `AgentService` kept its own
  `agentsCache` that nothing invalidated — the profiles page was
  right, the chat was stale.
- **Tool visibility vs. the permission gate.** Visibility read the
  agent's **kits**; the gate read the legacy `agent_tools` table. Tools
  were offered, then refused, and the model answered around the
  refusal.

**What to do**: give each fact one home and point every reader at it.
Do not add a reconciler or a third invalidation path. When one page is
right and another is stale, look for the second copy first.

## The tool-loop guards fire on a correct agent — THRESHOLDS RELAXED

`ToolCallTracker` (`backend/app/api/v1/chat/tool_call_tracker.py`)
blocked an agent for doing what the system asks: the **verify pattern**
(read a file, write it, read it back). Two identical reads in a row
tripped `max_consecutive_calls`; building a tool/skill inventory
tripped `max_total_calls_per_tool`.

- `max_consecutive_calls`: 2 → **4** — four identical calls in a row is
  still spam.
- `max_total_calls_per_tool`: 10 → **30** — still a ceiling; ten was a
  tripwire on ordinary work.

**What to do**: before tightening a loop guard, ask whether the pattern
it blocks is *not progressing* or *deliberately repeating*. A careful
agent looks like a loop to a naive counter.

## A blocked turn dies silently — and the message blamed the agent

When every tool call in a turn is blocked, the loop breaks and the
agent can only reply with text; nothing tells the user the turn was
cut. The user-facing loop-guard message was also wrong — it said the
agent was **stuck** (it was verifying) and told the user to
**rephrase the request**.

**What to do**: when a guard blocks the whole turn, say so — name the
guard and what tripped it. A guard that reports the wrong cause is
worse than no report: it sends the user to fix a request that was never
broken.

## A silent no-op reported as success

`file-manager`'s `write` was called with no `content` parameter — the
schema never declared one, so the model guessed `source` (the copy
input). It wrote an **empty file and reported success**. It now refuses
and names the parameter to use. Same shape: an empty assistant
completion is now discarded rather than stored as a message.

**What to do**: a write that changes nothing must fail loudly. If a
tool can report success without doing its job, its schema or its guard
is wrong.

## A tool that declared no workspace grant

`FileManagerTool` lacked `needs_workspace = True`, so the execution
service never injected the agent's folder as `base_path` and every
operation failed with *"base_path is required in config"*. Reads
looked fine — `file_info_handler` declares the flag.

**What to do**: when one tool in a family works and a sibling does not,
compare their **capability flags** (`needs_workspace`) before
suspecting config, kits, or the model.

## A clone must not carry the beat

A template used to copy the source agent's workspace files, so a
cloned reporter inherited the original's beat sheet *and* a zero-byte
leftover. A template carries the **character** (soul, skills, tool
surface, face) and no workspace content — `_capture_workspace_files`
now returns `None`. The mechanism stays, so seeding is still possible
when deliberately wanted. Related: the soul must not embed instance
facts (the original's persona said *"Your locus is Omaha, Nebraska"*) —
the soul describes the character and points at `state.json`.

**What to do**: keep character and instance apart. Facts belong in
`state.json`; the soul never names a place, source, or beat.

## `cogitate.sh stop` leaves orphans

`stop` kills the supervisor but not its children. The vite tree
re-parents to PID 1, **keeps port 5173 bound**, and keeps serving the
**old bundle** — so later frontend fixes never reach the browser while
the app looks healthy. Found by chasing a fix that "did not work": the
browser was running weeks-old code.

**What to do**: check the ports, not the launcher's success message.
After a stop/start cycle, verify nothing still listens on the dev
ports — stop the process *group*, not the process.

## Delegation completion messages can be lost

Three background subagents completed (228s / 297s / 218s) and **zero
results were delivered**. The per-task transcripts persist regardless,
on disk at:

```
~/.hermes/cache/delegation/live/<delegation_id>/task-N.log
```

**What to do**: the transcript is the durable artifact — read it
before concluding a result was lost. Do not re-run a delegation just
because its completion notification did not arrive.

## Thinking-mode sessions die

A session containing an assistant turn from a deepseek thinking-mode
model becomes permanently unusable: every later request returns `400 —
The reasoning_content in the thinking mode must be passed back to the
API`, LiteLLM retries 3×, the completion comes back empty, and the
failure is swallowed.

**What to do**: fixed for new turns — the stored reasoning is now replayed
on every assistant turn (the persisted history *and* the in-request turns
inside the tool loop). A session poisoned before the fix may still need a
fresh one; the agent's workspace always survives, because it was never the
session. The empty-completion guard also emits a visible error frame now
instead of discarding the turn in silence.

## Free-text fields with no validation

A collection's `icon` is free text rendered verbatim, so an invented
value renders as literal text and reads as "no icon"; the colour field
has the same problem.

**What to do**: a closed vocabulary gets a picker or a validator. Free
text is fine where the value is data; it fails where the value is an
identifier the UI switches on.

## The backend is double-spaced in places

`backend/app/api/v1/chat/router.py` has a blank line between every
line of code (a whole-file artifact). It parses and runs, but an
anchored edit must match the doubled bytes — the patch tool's fuzzy
matching fails on it.

**What to do**: when an edit to that file will not anchor, read the
raw bytes rather than the rendered view and match the `\n\n` spacing —
or edit a sibling module instead.

## `--reload` only reloads CHANGED files

The dev server reloads the modules whose files changed — it does not
reload the rest of the process. A fix committed to a file that is not
touched again never reaches the running backend, so the app keeps
executing the old code while the disk looks correct.

Seen live: the tool-call limits were raised and committed, and an hour
later the log still reported the OLD maximum, because nothing had changed
that file since.

**What to do**: after changing code, restart before testing — otherwise
the test proves nothing about the change. "I fixed it" is only true once a
restart has loaded it. Same shape as the stale-bundle hazard: the running
system and the disk disagree until something forces them together.

## Editing the chat path while a conversation is live

Every saved edit under the chat path triggers a reload that restarts the
backend mid-request. If a user has a chat open, their turn dies
(`LLM STREAM FAILED TO OPEN` / `STREAMING EXCEPTION`, an empty completion,
no reply) — and it reads as a brand-new bug rather than as the edit.

**What to do**: never edit the chat path during a live conversation. Wait
for a natural stopping point, or say plainly that chat will break until
the work lands. Never tell a user it is safe to chat while those edits are
in flight.

**The same applies to an agent's TOOL SURFACE.** Granting a tool to a
kit, or changing an agent's kit, takes effect on the NEXT request — so a
grant made while the agent is mid-turn is split across that turn: the
opening request carries the old set, the later ones the new. The agent
reports the old set (correctly, it saw it) while the log for the same
turn shows the new one, and an agent whose history contains its own
earlier "nothing has changed" will tend to repeat it.

Grant on a turn boundary, or tell the user to ask again. If an agent
insists a change has not arrived, check the timestamps of
`Agent <name> has N tools enabled` against when the change landed before
believing either side.

## A diagnosis is a hypothesis until it is verified

Two confident and wrong causes were asserted in one session: that an
agent had "died" because its process exited (the processes were healthy —
the session, not the agent, was broken), and that a nonsense elapsed value
was a wall-clock/monotonic mismatch (the production caller was consistent;
a test was passing `start_time=0.0`).

Both were plausible, both were cheap to check, and both sent work in the
wrong direction.

**What to do**: a familiar symptom is not evidence of the same cause.
Check the live state — processes, logs, the actual call sites — before
naming a cause, and call it a hypothesis until something confirms it. An
absurd-looking number is often a real value from a caller passing a
placeholder, not a bug in the code that formats it.

## A tool's schema lives in the DATABASE, not only in its class

The schema an agent's LLM receives is `tools.arguments_schema` — a row
in the database. `tool_to_llm_schema()` reads that row, not the handler
class. The row is refreshed from the class attributes by the startup
seed (`main.py`, which DOES update existing rows).

Consequence: editing a tool handler — adding a parameter, a new
operation, changing the description — changes nothing the agent can see
until the backend restarts and re-seeds the row. The code looks right,
the tests pass against the class, and the agent still gets the old
schema.

**What to do**: after changing a tool's `arguments_schema` or
description, restart before expecting an agent to see it, and verify the
row:

```sql
SELECT arguments_schema FROM tools WHERE slug='<slug>';
```

Agents perceive tools as a LIST OF NAMES in their prompt (name +
description). A capability added as a new *operation* on an existing
tool is invisible in that list — the name is unchanged, and only the
description carries the news. Tell the agent where to look, or the
change will read to it as "nothing happened" (correctly — see
[[dev-notes/agents/agent-cloning|Agent Cloning]] for the same
premise-checking behaviour).

## An agent that owns a kit has GRAS SUPPRESSED — the kit IS the surface

A tool with a GRAS capability (e.g. `file-read`) is default-on for an
agent — **unless the agent owns a kit**. When it does, the GRAS default
is suppressed entirely and the surface is exactly the union of the owned
kits' granted tools (`tool_collection_permissions`). An agent owning an
empty kit gets NO tools, deliberately.

So registering a new tool, giving it a GRAS capability and restarting is
**not enough**. It also has to be granted to the kit the agent owns, or
it exists everywhere except in front of an agent.

**Symptom**: a tool is in the registry, has a DB row, appears in the tool
catalog — and the agent's prompt still lists the old set. The log line
`Agent <name> has N tools enabled: [...]` is the ground truth; the
catalog is not.

**What to do**: grant it to the kit:

```sql
-- the agent's kits, then the grant
SELECT kit_id FROM agent_kits WHERE agent_id = <id>;
INSERT INTO tool_collection_permissions
  (id, tool_id, collection_id, permission_level, created_at, updated_at)
VALUES ('<uuid>', '<tool_id>', '<kit_id>', 'grant', datetime('now'), datetime('now'));
```

Then confirm via the agent's own resolved list, not the catalog. Note
the DB is held by the running backend — a write can hit `database is
locked`; retry briefly rather than blocking on a long busy-timeout.

## A lock created in `__init__` guards nothing if the object is per-call

The agent stores (`state.json`, beat sheets) created their lock in
`__init__` — and the tool handlers build a **fresh store on every call**.
Two concurrent writes therefore held two different locks and nothing was
serialized. The code looked guarded and was not; the class docstring even
claimed thread safety.

**What to do**: key the lock by the RESOURCE (the file path), not the
object instance — see `app/core/path_lock.py`. A lock's scope must match
the scope of the thing it protects. And when a docstring claims safety,
that claim is worth verifying: it is the cheapest place for a bug to hide.

## An unreadable file must refuse — never read as empty

`AgentStateStore.read()` returned an empty store when the file could not
be parsed, logging *"the next write repairs it"*. That was backwards: the
empty read **armed** the next write, which stored only its own key and
thereby **erased every other fact in the document**.

**What to do**: a MISSING file is empty and that is correct. A CORRUPT
one raises (`AgentStateUnreadable`) and no write happens on top of a
broken read. The general rule: a read that cannot know the truth must not
answer. An empty answer that looks like a successful read is how a
document gets destroyed by a repair.

## A FIXED temp filename collides

The "atomic" write used a fixed temp name (`state.json.tmp`). It is atomic
for ONE writer — with two, one's `replace` consumed the other's temp and
it died with `FileNotFoundError`.

**What to do**: `mkstemp` in the SAME directory (same filesystem, so the
replace stays atomic), and unlink on failure. "Atomic" means *no torn
writes*; it does not mean *safe for concurrent writers* — those are
different guarantees and the comment conflated them.

## The write defects were LATENT, not live — say which

All three above are real and none was reachable the day they were found:
one process, one event loop, the store called synchronously with no
`await` inside the read-modify-write, and no other caller. The fix is
insurance against a future threadpool, workflow, or multi-worker caller.

**What to do**: when reporting a defect, state whether it is live or
latent. "Shipped and dangerous" and "shipped and currently unreachable"
call for different urgency, and two confident wrong "this is happening
now" claims in one session cost real time (see the diagnosis entry).
Reproduce it, then say which.

## What is still NOT fixed: a lost update

The path lock serializes writers; it does not stop two readers from both
reading the same base and the second write winning. That needs a
revision / compare-and-swap at the store level, and it is a design
decision, not a patch. Worth settling BEFORE agents accumulate memory
written from many places — see the per-agent-state question in
`local/multi-agent-tabs/`.

## Ids are reused after a delete — a stale client can collide (2026-09-11, OPEN)

**The symptom that found it:** a session vanished from the side panel and
its reply never appeared — while both the session and the reply existed in
the database, correct. The backend was innocent (message 258, 465 tokens,
31.6 s, reasoning intact) and so was the rename: it fired one second AFTER
the reply landed and returned 200.

**The cause:** `chat_sessions.id` and `chat_messages.id` are
`INTEGER NOT NULL PRIMARY KEY` — **no `AUTOINCREMENT`**. In SQLite the next
id is `max(rowid) + 1`, so deleting the highest rows frees their ids for
immediate reuse. Proven in the log:

```
16:42:33  bulkDelete -> {"deleted": [24, 23, 22]}   <- the id-freeing act
16:42:52  the user asked a question
16:42:53  the new session was given id 22 again (its messages 257/258)
```

**Why it recurs:** sessions get tidied by deleting the NEWEST ones — which
is exactly what frees the highest ids. The cleanup causes the bug. "Again"
is not a coincidence.

**The house already answered a NEIGHBOURING question — for `agents`.** It
carries `deleted_at` + `archived_path`, its delete is "BOM + soft-delete +
archive (history KEPT, the row survives)" with restore endpoints. Agent rows
are never removed, so agent ids are never freed.

**But that is NOT the model to copy here — and the first draft of this
entry said it was.** The user pushed back: *"I don't like the idea of rows
that never delete. How does that pan out long term?"* Two problems were
being conflated:

1. **ids must never be reused** — the correctness requirement;
2. **what "delete" means** — a retention decision.

`AUTOINCREMENT` solves (1) directly and leaves (2) alone. Soft-delete solves
(1) *only by* changing (2), paying a permanent retention cost for an id
guarantee — unbounded growth, a `WHERE deleted_at IS NULL` filter on every
query forever (miss one and deleted conversations resurface), and you end up
writing a purge job that IS a hard delete anyway.

**Soft-delete is right for a bounded, identity-bearing entity you would
regret losing (an agent). It is wrong for a high-volume disposable record
(a session).** Right pattern, wrong granularity.

**The fix is `AUTOINCREMENT` on the id columns**, and it is the SMALLER
change: no new column, no filter sweep, no restore endpoint — just a table
rebuild. It also makes a wipe safe: `DELETE FROM` under `AUTOINCREMENT`
keeps the counter, so ids do not repeat; without it, emptying a table
RESETS the sequence to 1 and reintroduces this exact collision.

**A CLASS, not a site:** 28 tables use the pattern, and exactly ONE table in
the whole database uses `AUTOINCREMENT`. Only tables whose ids are known
OUTSIDE the database can collide (the client, a cache, a stored binding) —
config/seed tables cannot. Priority list: `local/roadmaps/session-identity-roadmap.md`.

**Consequence beyond the UI:** once an id is reused, every cached reference
to it — a bookmark, a log line, a link, a stale tab — silently resolves to
a DIFFERENT entity. That is a correctness problem, not only a rendering one.

**The log made it worse:** `resolveLiveSessionId` logged at `info` on every
stream chunk — 812 lines, ~10/sec — for an event that happens ONCE per
stream ("temp swapped"). Churn drowning the signal. Fix the churn by
logging the right thing once, never by silencing it.

**Do not over-claim:** the store state was CORRECT at the end
(`replacedInList: true`, 2 messages, the right title). The render path was
never proven. State what is proven; label the rest as inference.

**FIXED 2026-09-11 (migration `t9u0v1w2x3y4`).** Two halves, both required:
`sqlite_autoincrement: True` in the models' `__table_args__` (so a FRESH
install is born correct — without it SQLAlchemy never emits the keyword) and
a migration rebuilding both existing tables. `chat_messages` must be rebuilt
**after** `chat_sessions`: SQLite (>= 3.25) rewrites REFERENCES clauses in
other tables when a referenced table is renamed, so rebuilding the child
first left its FK pointing at the dropped `chat_sessions_old`. Caught on a
COPY — the migration was verified on a copy before it touched live data, and
that is the habit to keep for anything that rebuilds tables.

**A migration that touches live data belongs on a copy first, and a WAL-mode
database read from a DIFFERENT interpreter can show a stale view.** The
verification of this fix first said "the migration did not apply" — it had.
The app's own write path settled it (`create -> 23`, `delete 23`,
`create -> 24`: the counter advanced past the freed id). **When the file and
the application disagree, believe the application, and verify through its API.**
A stale reader nearly produced a second confident wrong "it did not work"
claim in the same investigation.

**THE 18-DAY GAP — this was a REGRESSION of a documented, never-applied fix.**
`known-issues.md`'s sibling (`fastapi-sqlalchemy-async` §14) described this
exact defect and its durable fix on **2026-08-24**, and §14 predicted this
exact symptom ("the SECOND victim: client-side state keyed by row id").
The user hit it on **2026-09-11**. Why it survived:

- **`git log -S "sqlite_autoincrement"` on `models.py` returned NOTHING
  before the fix** — and no migration had ever added it. The diagnosis was
  written; the schema was never changed. **A fix recorded in a skill is a
  PLAN, not a fix.** Write it up AND apply it, or open a todo — prose alone
  leaves the defect live.
- **The repo had a detector, and it saw this.** `IntegrityAudit.id_reuse_watch`
  (`backend/app/domain/audit/integrity.py`, wired to `/api/v1/system` and the
  system-audit workflow) reported: *"… has NO AUTOINCREMENT (max id N) —
  deleted ids can be reused **(harmless now, watched)**"*.
- **It graded a real risk "harmless" — and was believed.** "Latent" means
  *not reachable today*; it does NOT mean safe. The house rule is to label a
  finding live or latent. This watch went further and attached a verdict, and
  the verdict was wrong inside 18 days.
- **A watch that reassures is worse than no watch**: it converts a finding
  into a reason not to act. **Detector ≠ remedy.** When a watch is written,
  decide its ACTION — fix it, file it, or fail loudly. "Watched" with no
  owner is how a documented defect survives three weeks.

**Action taken:** the fix is applied (models + migration) and verified live.
The wording of the watch still needs a follow-up (still open).

**AND THE FIX ITSELF BROKE THREE MORE TABLES — the same trap, one level
down (later the same day).** Adding AUTOINCREMENT rebuilt `chat_sessions`
via rename -> create -> copy -> drop. SQLite rewrites the `REFERENCES`
clause in every OTHER table that points at a renamed table. Only
`chat_messages` was rebuilt afterwards — so **`usage_logs`,
`runtime_configs` and `chat_attachments` kept `REFERENCES
chat_sessions_old`** after it was dropped. Every chat turn then died at
the usage-log write:

```
(sqlite3.OperationalError) no such table: main.chat_sessions_old
[SQL: INSERT INTO usage_logs (...)]
```

The agent reported failure while the completion had actually succeeded; a
dozen turns were lost.

**This is the sharpest lesson of the day because the migration's OWN
docstring named the trap, and the fix still only repaired one child of
four.** I fixed the SITE (the table I was thinking about) not the CLASS
(every table referencing `chat_sessions`) — the exact failure mode this
file lectures about elsewhere. And `chat_sessions` is referenced by FOUR
tables: `chat_messages`, `usage_logs`, `runtime_configs`,
`chat_attachments`.

**The verification was the gap, not the knowledge.** I ran
`SELECT sql FROM sqlite_master WHERE name='chat_messages'`, saw
`REFERENCES chat_sessions`, and stopped. The check that catches it is
GLOBAL and one line:

```sql
-- expect ZERO rows; a non-empty result means the migration FAILED
SELECT name, sql FROM sqlite_master
WHERE type='table' AND sql LIKE '%\_old%' ESCAPE '\';
```

**Never verify the child you were thinking about. Grep every table's DDL
for the old name.** And before writing any rename-based rebuild, count the
children: `grep -rn 'ForeignKey("<parent>.id"' --include=*.py` — knowing
there are four turns a one-child repair from a silent breakage into an
obvious one.

**Repaired by migration `u0v1w2x3y4z5`, generically**: it reflects each
broken table's own DDL, rewrites only the dead token, rebuilds, and
replays the table's indexes. Verified on a copy (51 `usage_logs` rows
preserved), then live, then **end-to-end** — a real turn completed and its
`usage_logs` row landed (success=1, 2291 tokens).

### MIGRATE — what should move into the lifecycle section (2026-09-12)

The section is built (`wiki/dev-notes/lifecycle/`): index + startup +
background-work + shutdown. The user's model is **migrate gradually** — it is a
place for new information, not a big-bang reorganisation. So building it is done
and this is the standing list.

**Already handled:**
- `architecture/shutdown-contract.md` → `lifecycle/shutdown.md` (it landed in
  architecture by default, not by fit).
- The configuration surface's toggle section was **collapsed to a pointer** into
  `lifecycle/background-work` — it had become a second home for the same facts,
  which is the drift this project keeps meeting.

**Candidates, judged rather than presumed:**

- [ ] **The scheduling half of the workflow triggers.** `dev-notes/workflows/`
      covers the trigger machinery; when the app runs it and how it is stopped is
      lifecycle. Split only if the pages actually overlap — a link may be enough.
- [ ] **The test suite's own lifecycle** (`dev-notes/testing/`): the suite boots
      the app, writes to filesystem paths that are not isolated, and can hang. If
      `testing/` grows into "how the suite runs", that is lifecycle-adjacent —
      judge when it comes up.
- [ ] **Cross-link, do not move, the `--reload` gotchas** — they live in
      `known-issues.md`, which is the gotcha register and should keep them.
      A lifecycle page should point at them, not absorb them.

**The rule for this section, and the reason it will not rot:** each page must
say **how to check it is still true**. Lifecycle facts drift silently — a doc
listing one recurring loop fewer than the code does fails forever and nothing
notices. `background-work.md` carries two greps and the startup-log witness, and
that check has already earned its place: on its first run it found
`notifications.py` scheduling the mute restore, which the table had missed.

**Do NOT turn this into a sweep.** The section exists so new facts have a home.
Migrating for its own sake would move pages that are fine where they are.

### THE ATLAS HAS STALE PAGES FOR SCRUBBED CODE (found 2026-09-12)

**The validator is red on 3 issues, all pre-existing** (they predate this
session's doc pass; the frontmatter issue that shared the report was fixed):

```
[atlas/ui/components/features/configuration/Configuration Index.md]
[atlas/ui/components/features/monitoring/Monitoring Index.md]
[atlas/ui/components/features/agentTools/ToolBrowser/Tool Browser Index.md]
    path segment(s) not found
```

**Cause:** the code scrub (69 frontend files + dead backend code)
removed `frontend/src/components/features/{configuration,monitoring,agentTools/ToolBrowser}`,
and the atlas pages documenting them stayed. They are pages for components that
no longer exist.

**Why it is not a one-liner.** The project-wiki convention is to archive removed
components to `wiki/_archive/`, but these are INDEX pages — their parents link to
them, so archiving breaks those wikilinks and the validator's Wikilink check
(the next gate) goes red instead. The job is: archive the subtrees, then update
or remove every inbound link, then re-validate to green.

- [ ] Archive the three subtrees to `wiki/_archive/` and fix the inbound links.
- [ ] Then confirm the validator is fully green — a red gate that everyone has
      learned to ignore is worse than no gate, which is the same shape as this
      session's other findings.

### THE ATLAS HAS STALE PAGES (found 2026-09-12)

## The trace viewer's token figures are context size, not usage — and the metrics column is empty (OPEN)

**Symptom.** The Cognitive Trace Viewer reports a run's "tokens" and a duration.
The duration is right. The token figure is not what it appears to be, and the
metrics beside it read `0 / 0 / llm_calls=0` on every row.

**Root cause.** `CognitiveTrace.total_tokens` is a property summing the four
components' `tokens_used`. Only `context_builder.tokens_used` is ever populated —
it holds the **size of the assembled context**. `executor.tokens_used` is 0 even
on a 77-second real LLM call, so the figure the viewer shows is the PROMPT SIZE,
labelled as though it were the run's usage. `input_tokens` and `output_tokens`
are 0 on every row.

The empty metrics column has the same origin, one line downstream:

```python
# pipeline.py
metrics.total_tokens = trace.executor.tokens_used      # always 0
```

Metrics are assigned from the executor's tokens — the number that is never
recorded. `trace_json` and `metrics_json` disagree because they read different
things, and the accurate-looking one is the empty one.

**How it was found.** By reading the rows rather than the UI: a real trace
(`skillaware` / `hybrid` / `noop` / `direct_yield`) compared component by
component against a synthetic one.

**Lesson.** A field's NAME is not evidence of its UNIT. `total_tokens` names
neither the context nor the generation, and the sum adds two things that should
not be added.

## The test suite writes into production surfaces (FIXED 2026-09-12)

**Symptom.** Agent workspaces appear in the real `agents/` directory after a test
run; per-agent `cognitive_memory.db` files are touched; and synthetic traces land
in the production trace database, indistinguishable from real runs at a glance.
On a bad day the suite stops mid-run instead of failing.

**Root cause.** `backend/tests/conftest.py` isolates the MAIN database thoroughly
— a temp file, per-test truncation, dependency overrides. Everything the code
resolves from live settings **at call time** is not isolated: the agents root, the
per-agent memory databases, and `pipeline_traces.db`. The trace store is the
clearest case, because it computes its path at call time:

```python
return str(Paths.from_settings(get_settings()).data_dir / "pipeline_traces.db")
```

**How to recognise a leaked trace.** All four components read `default` — a real
run reads `skillaware` / `hybrid` / `noop` / `direct_yield` — the `session_id`
does not exist in `chat_sessions`, `message_id` is NULL, and the duration is
sub-second where real runs take seconds.

**Why the chat path is involved without naming the store.** `save_trace` has two
callers, both application code. One is the main chat stream
(`api/v1/chat/router.py`), which passes a session id and never a message id. So a
test that drives the chat stream persists a real trace into the production
database — no test mentions the trace store, and the store fills up anyway.

**The analogous case.** `reset_agent_memory` reaches out of the sandbox to the
real per-agent `cognitive_memory.db`, opens it without a timeout, and swallows
every failure in a bare `except Exception: pass` — a state-mutating path that
cannot report that it failed.

**The fix, and the root cause of all of it.** `Paths.from_settings` honoured
only `settings.database_url` — every other path kept its `BASE_DIR` default — so
aiming the database at a temp file redirected the database and nothing else. Its
own docstring promised the opposite.

`from_settings` now re-roots every field declared relative to `BASE_DIR`, derived
from the dataclass's own declarations so the two cannot drift. `logging_config`
resolved its path from `settings.log_file` **directly** — a hardcoded path, the
very defect `Paths` exists to remove — and now resolves through `Paths`.
`conftest` aims `DATABASE_URL` at a temp **directory** before importing the app,
because the engine is built at import time.

**Measured before and after:** traces 401→401 · `agents/` 34→34 · log markers
25→25 (was growing ~14.8 KB per run). Production paths verified unchanged.

**Lesson.** Isolation that covers the database and not the filesystem is half an
isolation. The fix is to make the wrong path impossible — *derive every resolver
from one root and move the root* — not to clean up afterwards.

**And the corollary, which is the durable part:** a path resolved from settings
must derive from `Paths`. Reading a raw setting directly (`settings.log_file`) or
computing `BASE_DIR / ...` by hand silently escapes whatever the resolver is
doing, and nothing fails when it does. See
[[dev-notes/testing/test-isolation|Test Isolation]].

## Paths escape the resolver silently — and the app did it too (found 2026-09-12)

**Symptom.** Nothing fails. Macro saves work, tests pass, the app is healthy —
on the machine where the code was written. Somewhere else, a path resolves to
the wrong place, or to nothing, and no error is raised at the point of the
mistake.

**Root cause.** `Paths` is the one resolver for canonical app paths, but nothing
enforces its use. A path re-derived by hand — `BASE_DIR / "x"`,
`Path(__file__).parents[4] / "y"`, `os.path.expanduser("~/Projects/cogitate/z")`,
a bare `"./data/w.db"` — escapes it entirely, and **nothing detects this**,
because the value is still a perfectly valid path. It is only wrong.

**The application, not just the tests.** The worst instance was in shipped code:

```python
# backend/app/api/v1/macros/router.py (x3)
saves_dir = os.path.expanduser("~/Projects/cogitate/data/macro-saves")
```

A hardcoded **home directory in application code**. It worked here. A packaged
fork, another user, or another checkout would have written elsewhere, silently.
Same shape in `database.py`'s cwd-relative `./data/...` fallback — which
resolves against whatever directory the process happened to start in.

**Measured.** ``check_path_arithmetic()` in `scripts/core/sweep/backend.py`` finds **59** sites across
app, tests and scripts (134 raw hits before the noise was classified out). They
are three different things and want three different treatments: a few real
app-code items; ~13 tests that assert on *this installation* rather than the
code, and so only pass where that data exists; and the bulk in operator scripts,
two of which contain outright *wrong* paths in recovery tools.

**The tell.** A grep is the wrong instrument, and this was proven three times in
one session: `grep -rn "BASE_DIR /" backend/app` missed eleven sites (they were
in `backend/tests/`), the whole `expanduser` family (a different shape), and
every parent-walk variant. Use the scanner.

**A gate already existed, and was narrow.** `check_path_arithmetic()` in
`scripts/core/sweep/backend.py` implements this exact check, with a docstring
naming the original phantom-DB incident and the fork-blocker rationale — and it
scans `backend/app/` only, by explicit decision ("the SHIPPED surface"). That is
precisely why the eleven test sites were invisible to it. It had been **red**.

**Lesson.** A path is data, so it follows the installation root — but a
parent-walk that locates the **source** tree to read source files is fine, and
the difference matters when triaging. What makes this class dangerous is that
correctness and silence coincide: the code is right where it runs, so nothing
ever reports. Only a scan that knows every shape can see it.

See [[dev-notes/testing/test-isolation|Test Isolation]].



## Related

- [[dev-notes/agents/agent-cloning|Agent Cloning]]
- [[dev-notes/workflows/product-distribution|Workflow Product Distribution]]
- [[dev-notes/assets/agent-images|Agent Images]]
- [[dev-notes/frontend/modal-dialogs|Modal Dialogs]]
- [[dev-notes/message-center|Message Center]]
- [[dev-notes/messaging-system|The Messaging System]]
