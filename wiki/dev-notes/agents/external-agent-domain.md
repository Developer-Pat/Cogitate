---
title: External Agent Domain (ACP Client)
type: atlas-note
path: backend/app/domain/external_agent
confidence: high
updated: 2026-09-10
tags: [type/note, domain/agents, status/active, feature/external-agent]
---

# External Agent Domain

**Path**: `backend/app/domain/external_agent/`

The thin ACP client backing the Agent Panel — anti-reimplementation by construction: Cogitate manages a subprocess and relays text; the external agent (Hermes/OpenClaw) does all its own thinking, tools, and memory.

## Files

- `services.py` — `AcpClient` (subprocess lifecycle, JSON-RPC 2.0 protocol, event streaming), `AcpEvent`, `get_acp_client()` singleton, `get_config`/`save_config` (UserSettings JSON blob, key `external_agent`), `command_parts` (shlex)
- `schemas.py` — `ExternalAgentConfig {command, cwd, permission_tier, max_turn_seconds, image, max_tool_calls_per_turn, tool_call_checkin_every}`, `ExternalAgentConfigUpdate`, `ExternalAgentStatus`. `permission_tier` (`chat | fix | yolo`, 2026-08-21) is the field of truth; `fix_mode` is now a computed `@property` compat view (`permission_tier == "fix"`), not a field
- `__init__.py` — re-exports

## Protocol facts (pydantic-gated — the spike's discoveries)

1. `session/new` **requires `cwd`** — missing → `Invalid params`
2. `mcpServers` must be a **LIST `[]`** — dict rejected
3. `session/prompt` takes **content blocks directly** in the prompt list — `{role, content}` wrapper rejected
4. Completion = the **id:N session/prompt RESULT** (`stopReason: end_turn`) — NOT a `status=completed` event
5. Reply streams as `session/update` with `agent_message_chunk` / `agent_thought_chunk`
6. Tool use streams as `session/update` with `sessionUpdate: "tool_call"` (`{kind, locations, title, toolCallId}`) — forwarded to the panel as the watchable workspace

## Queue rework (2026-08-12) — per-prompt consumers

ACP allows ONE active prompt per session. `stream_prompt` is an async generator: it holds `_prompt_lock` for the whole turn, routes THIS prompt's events to its own queue (`_active_queue`); concurrent callers wait on the lock and each receives only its own events. No interleaving, no stolen chunks. Two panel tabs or a consult-tool call alongside the panel serialize cleanly. Tested with concurrent prompts against the echo fake.

## The startup race (live-caught)

Hermes emits `available_commands` + a startup `usage_update` AFTER `session/new`'s result. A prompt sent before those finish is **silently lost** — `start()` waits for the startup usage event as the session-ready signal. **The same rule applies to any early protocol call** — `_set_edit_approval_policy` must run AFTER the ready-wait or Hermes never answers it (observed 10s timeout, 2026-08-13).

## FIX-MODE GATE (2026-08-13) — the tool-level enforcement

The explicit user grant, enforced three ways (defense in depth):

1. **Tool-level (the real gate)**: `session/set_config_option`
   (`config_id: "edit_approval_policy"`) — `workspace_session` when
   fix granted, `ask` when read-only. Hermes itself denies edits in
   `ask` (this app never answers approval prompts). See
   [[dev-notes/agents/hermes|Hermes vendor note]] for the full matrix.
2. **`capabilities.strictTools: true`** on `session/new` when
   read-only — blocks the dedicated write tools at the tool layer.
3. **Server-side prompt directive** — the WS router injects
   `[MODE: FIX GRANTED]` / `[MODE: READ-ONLY]` into every prompt;
   the client cannot spoof the grant.

Sensitive paths (`.env`, `.ssh`, `.git`) are always guarded by Hermes regardless of policy. Terminal-based writes bypass the edit gate — the prompt directive covers that layer.

## HALT PATH — the WS protocol (INCIDENT 2026-08-13)

The panel can stop a running agent two ways (client→server WS
messages):

| Message | Meaning | Mechanism |
|---|---|---|
| `{"type":"cancel"}` | gentle stop | `session/cancel` (ACP-standard notification → Hermes `agent.interrupt()` = CLI Ctrl+C); if the stream doesn't end within CANCEL_GRACE_SECONDS (5s), escalate to `close()` (PID kill) |
| `{"type":"nuke"}` | force kill | `AcpClient.nuke()` = `os.killpg(pid, SIGKILL)` — the subprocess spawns with `start_new_session=True`, making it its own process-group leader; the nuke hits Exa + its tool children ONLY. Targeted by ownership, never by name |

Server→client: `{"type":"status","status":"cancelled"}` after either.

**Architecture notes (the bugs the incident exposed):**
- The WS **receiver task** sets the cancel event IMMEDIATELY and
  schedules the halt as its OWN task — the main loop is blocked in
  `async for stream_prompt` mid-stream, so a queued message would
  never be seen until the turn ended. The receiver is the only actor
  alive mid-stream.
- The stream loop does NOT break on cancel — breaking fired
  `stream_ended`, making the grace conclude "gentle worked" when it
  hadn't. It keeps consuming; the grace measures the agent's NATURAL
  end.
- **Disconnect halt**: the WS going away mid-turn used to only
  DETACH the stream (the subprocess ran on — the actual runaway).
  Now the handler halts on disconnect: `session/cancel` then kill.
  Next panel open respawns fresh.
- After a kill, `nuke()`/`close()` push a "closed" sentinel into the
  active queue so a stream blocked on `queue.get()` wakes and exits
  promptly.

## Panel-side UX lessons (2026-08-13, from dialog captures)

The user's `local/Exa/Exa_dialog_0*.md` captures (Copy-button output)
caught three real bugs that backend-only testing missed — the dialog
review ritual (read the capture, trace what Exa did, check the
stop/queue interaction) is worth repeating:

- **Double-send race → the Hermes queue**: `send()` and
  `confirmPending()` both guarded on the React `busy` STATE, which
  updates asynchronously — two sends in the same tick both read
  `busy=false` and both fired, so Hermes queued the second ("Queued
  for the next turn. (1 queued)") and auto-ran it after Stop. Fixed
  with a SYNCHRONOUS `busyRef` (set before the WS write) + a typed
  prompt / Diagnose supersedes any pending hand-off. Rule: never
  send a second prompt while one is in flight.
- **Single 'cancelled' status**: the receiver used to handle
  cancel/nuke AND re-queue them, so the main loop sent a duplicate
  status (double "⏹ Stopped."). Receiver now fully consumes them; a
  shared `cancelled_reported` flag dedupes the stream loop + halt +
  nuke tasks.
- **close()/start() race**: `close()` referenced `self._proc` in its
  tail while a concurrent `start()` had overwritten it — the NEW
  subprocess got killed (empty-error respawn). `close()` captures
  proc + session_id in locals and nulls them immediately.
- **Situation-aware header**: the Diagnose button is the
  CHAT-situation feature (hand the active session to Exa). It
  renders only on a plain (no-context) open — hidden when a context
  hand-off is active, so users never see a button meant for a
  situation they don't know about.
- **Whole-turn time limit (2026-08-14; default raised to 900 on
  2026-08-22)**: a configurable `max_turn_seconds` cap (0 = unlimited,
  default 900) auto-halts a
  run via the EXISTING two-stage stop and reports a DISTINCT
  `time_limit` status — the panel must say "time limit reached",
  not "stopped", because the user didn't stop it. Live-testing
  this exposed a latent double-send: the escalation path in
  `_halt_agent` had an UNCONDITIONAL `send_json('cancelled')` after
  `_report_cancelled()` — the dedup flag (2026-08-13) never gated
  it, so a time-limit halt showed BOTH "⏱ Time limit reached" and
  "⏹ Stopped.". Removed: `_report_cancelled()` is the single
  sender. Lesson: the dedup flag must gate EVERY status send, not
  just the first one discovered.

## THE LOCAL HOME (Phase 1, 2026-08-18) — HERMES_HOME

The external agent gets its OWN Hermes home — `cogitate/.hermes/`
(`Paths.exa_home`) — via the spawn env's `HERMES_HOME`. The
operator's `~/.hermes/` is NEVER touched: the local home boots
its own memories/skills/sessions/cron tree, knowing NOTHING of
the operator (the isolation probe proved it). Hermes home
resolution: context → env → platform default.

**Provisioning** (scripts/core/provision_exa_home.py, first boot):
the home structure + config.yaml (the working model config) +
.env (the provider keys, never echoed) + the SEED SKILLS.

**The seed skills** (skills/exa/, tracked → the home's
skills/cogitate/): cogitate-system-map (derived — points at the
live API/DB), cogitate-api-surface, cogitate-monitor-operations,
set-trigger-schedule (API path + 5-field validation + NEVER-
rename), verify-backend-health, verify-trigger-config,
report-verified-state, ask-before-destructive, audit-consistency,
cogitate-workspace (the desk). The skill probes verified: a fresh
home lists all + picks the right tool for a task.

**THE DESKTOP** (2026-08-20): the home is the brain;
`.exa-workspace/` (Paths.exa_workspace) is the desk — inbox
(workflow products land), reports, drafts, scratch. The exa-inbox
delivery files products there. See
[[dev-notes/agents/exa-desktop|the Exa desktop]].

## THE TOOL FAMILY (Phase 2, 2026-08-18/19) — Exa's lifecycle tools

The registry tools Exa uses (all keyed = fix-mode grant, verified
after, recorded to the verification store — the claimed/verified
pattern):

| Tool | Tier | What it does |
|---|---|---|
| `list-archived-agents` | gras | the soft-deleted agents (id, name, archive folder) |
| `delete-agent` | keyed | DEACTIVATE (soft + archive, recoverable via restore-agent) or PERMANENT scrub (hard=true, irreversible) |
| `restore-agent` | keyed | the UNDO — the archived workspace moves back, verified |
| `set-trigger-schedule` | keyed | a workflow trigger's cron (validated, verified by read-back) |
| `verify-backend-health` | gras | the backend's ACTUAL state (the health check) |
| `verify-trigger-config` | gras | a trigger's config read-back |
| `audit-consistency` | gras | the system consistency audit (see the audit arc) |
| `verify-http-evidence` | gras | the access-journal evidence for a claim |
| `search-knowledge` / `graph-query` | gras | the RAG lookup + the topology graph |

**The panel directive** points Exa at the TYPED HTTP API (its
proven capability — the Cogitate registry is NOT injectable into
Exa's Hermes session). Prompts are advisory; gates + verification
are real. See [[dev-notes/agents/system-audit-arc|the audit arc]]
for the full claimed/verified story.

## Known limits

- One long-lived session; **backend reload resets it** (uvicorn `--reload` recreates the singleton)
- Subprocess runs with full user tool access; enforcement is the policy gate + prompt directive + watchable tool stream (not a per-tool whitelist)
- stderr is captured + drained into the backend log (`external-agent stderr: <line>`) — deaths leave evidence
- Whole-turn caps EXIST (2026-08-14; raised + extended 2026-08-22/09-08): `max_turn_seconds` (default 900, 0 = unlimited) auto-halts a long turn and reports `time_limit`; `max_tool_calls_per_turn` (default 75, 0 = unlimited) caps a runaway tool loop and reports `tool_call_limit`; `tool_call_checkin_every` (default 15) emits a `working` beacon. The 120s per-event wait is unchanged

## Related (cross-surface)

- **Frontend**: [[atlas/ui/components/features/agentInteraction/AgentPanel|AgentPanel]] (the drawer), [[atlas/ui/pages/AgentIntegration|Exa Agent]] (config page), `externalAgentService`
- **API**: [[atlas/api/routers/external-agent|External Agent API]]
- **Feature/design**: [[dev-notes/agents/consulting-agent|Consulting Agent]]
- **Vendor specifics**: [[dev-notes/agents/hermes|Hermes vendor note]]
- Report: `local/roadmaps/agent-panel-implementation.md`
- **scripts/diagnostics/**: internal legacy tooling —
  historical, not user-facing, left as-is.
- **Backup**: backups/20260814_120224/ taken pre-change.

## Chat authorization — see the dedicated page

The per-edit Approve/Deny bridge (the third permission tier,
2026-08-21) has its OWN design page: [[dev-notes/agents/chat-authorization|Chat Authorization]].
