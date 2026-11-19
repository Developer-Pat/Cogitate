---
title: External Agent
type: atlas-api
path: wiki/atlas/api/routers/external-agent.md
category: api-atlas
order: 13
confidence: high
updated: 2026-09-08
tags: [type/api, domain/agents, status/active, feature/external-agent]
---

# External Agent — API

> Router: `backend/app/api/v1/external_agent_router.py` — the Agent Panel's backend: configuration, status, and the WebSocket bridge to the ACP subprocess.
> Domain: `backend/app/domain/external_agent/` (`services.py` AcpClient, `schemas.py`, `__init__.py`).

## Config

### `GET /api/v1/external-agent/config`
Returns the persisted connection config.

```json
{"command": "hermes acp", "cwd": "", "permission_tier": "chat", "max_turn_seconds": 900, "max_tool_calls_per_turn": 75, "tool_call_checkin_every": 15, "image": ""}
```

- `permission_tier` (str, 2026-08-21) — THE 3-WAY WRITE GRANT:
  `"chat"` (default) = per-edit approval in the chat (the
  Approve/Deny card); `"fix"` = auto-approve inside the ACP cwd
  (workspace_session); `"yolo"` = auto-approve everything (the
  adapter's `session` policy — the secret-file guard still asks
  for .env/.ssh/.git). The tier maps to the ACP
  edit_approval_policy at spawn: chat→ask, fix→workspace_session,
  yolo→session. The OLD `fix_mode` bool is the DEPRECATED compat
  view (True == the fix tier; persisted configs map automatically).
- `max_turn_seconds` (int, 2026-08-14) — whole-turn duration cap:
  a run that exceeds it is auto-halted (same two-stage path as
  Stop) and reports a distinct `time_limit` status. **0 = no
  limit.** Default 900.
- `max_tool_calls_per_turn` (int) — the tool-call cap: a turn
  that reaches it is auto-halted (same two-stage path as Stop)
  and reports a distinct `tool_call_limit` status — the runaway-
  turn guard (a silent 50+-call rabbit-hole used to crash or hang
  before anyone saw it). **0 = no limit.** Default 75.
- `tool_call_checkin_every` (int) — the check-in cadence: every N
  tool calls the stream emits a `working` status beacon (the
  runaway is visible while it builds). **0 = no beacons.**
  Default 15.
- `image` (str, 2026-08-21) — Exa's chat face: an asset path
  (e.g. `/static/alien-rocky.png`). Configurable on the Exa Agent
  page; the chat participant renders it. No emojis — the face is
  an image.

### `PUT /api/v1/external-agent/config`
Body: `{command?, cwd?, fix_mode?, max_turn_seconds?, max_tool_calls_per_turn?, tool_call_checkin_every?}` (partial). Persists via the `user_settings` JSON blob under key `external_agent`; closes the running subprocess so the next connection spawns with the new config. Returns the full updated config.

## Status

### `GET /api/v1/external-agent/status`
Live connection state:

```json
{"connected": false, "session_id": null, "command": "hermes acp", "cwd": "", "permission_tier": "chat", "max_turn_seconds": 900, "max_tool_calls_per_turn": 75, "tool_call_checkin_every": 15, "image": "", "model": null, "provider": null, "error": null}
```

### `POST /api/v1/external-agent/restart`
Closes the current subprocess; the next panel open spawns fresh. Returns `{"status": "restarted", "command": ..., "cwd": ...}`.

## WebSocket

### `WS /api/v1/external-agent/ws`
The Agent Panel's streaming bridge.

**Client → server**:
| type | payload | notes |
|---|---|---|
| `prompt` | `{text}` | send one at a time — a second prompt while one is in flight is queued by Hermes (see the prompt-queue dev note) |
| `cancel` | `{}` | **gentle stop** — `session/cancel` interrupt, auto-escalates to kill after the grace window (2026-08-13) |
| `nuke` | `{}` | **force kill** — process-group SIGKILL, immediate, no grace (2026-08-13) |
| `approval_response` | `{request_id, option_id}` | the user's decision on a pending permission request — `option_id` = the chosen option (`allow_once`, `deny`, ...). Unknown ids are DROPPED (the request-bound security property, 2026-08-21) |

**Server → client**:
| type | payload |
|---|---|
| `status` | `{status: "connecting" \| "ready" \| "cancelled" \| "time_limit" \| "tool_call_limit" \| "working" \| "error", sessionId?, message?}` — `cancelled` sent ONCE per stop (dedup flag shared by the stream loop + halt/nuke tasks); `time_limit` = the whole-turn duration cap auto-halted the run; `tool_call_limit` = the tool-call cap auto-halted it (both distinct from a user stop); `working` = the check-in beacon (repeated every `tool_call_checkin_every` calls, mid-turn — NOT a terminal status) |
| `message` | `{text: "<chunk>"}` — streamed reply chunks |
| `thought` | `{text: "<chunk>"}` — streamed thinking chunks |
| `tool_call` | `{update: {kind, locations, title, toolCallId}}` — the consultant's tool use, forwarded live (the watchable keyboard-takeover workspace; 2026-08-12) |
| `approval_request` | `{request: {request_id, session_id, title, tool_call_id, options, content}}` — a permission request (an edit proposal with the diff); the chat renders the Approve/Deny card (2026-08-21) |
| `approval_result` | `{request_id, resolved: bool}` — the resolution ack (the request was found + resolved, or dropped as stale) |
| `done` | `{reply: "<full text>"}` |

On connect the server spawns the subprocess with the persisted config (command/cwd) and waits for the session-ready signal before accepting prompts (a prompt sent too early is silently lost — see domain services).

**Halt semantics (2026-08-13)**: `cancel` is two-stage — `session/cancel` (the ACP-standard gentle interrupt, Ctrl+C-equivalent) first, then kill-by-PID if the agent ignores it past the grace window. `nuke` skips straight to `killpg` (the process group is the spawn tag — `start_new_session`), killing Exa AND its tool children, never the backend/CLI. Both report exactly one `cancelled` status. The stream loop ALSO auto-halts a turn that exceeds `max_turn_seconds` (0 = unlimited) or reaches `max_tool_calls_per_turn` (0 = unlimited) via the same two-stage path, reporting `time_limit` / `tool_call_limit` instead of `cancelled` — the panel explains it as a limit, not a user stop. A subprocess death mid-turn now ENDS the stream (the process-exit alarm — the backend logs `EXITED unexpectedly (returncode=N)` and wakes the stream with the closed sentinel) instead of hanging it. The receiver fully consumes `cancel`/`nuke` (never re-queued — the double-'⏹ Stopped.' bug); a queued Hermes prompt survives a gentle stop but NOT a nuke (fresh session = empty queue).

## Report persistence (2026-08-13, Option B)

### `POST /api/v1/external-agent/report`
Persist an Exa conversation report into the workflow-product flow.
Body `{title, body}` (body = markdown report, typically the panel's
last assistant reply). The report is wrapped in a `WorkflowProduct`
(`product_type="exa_report"`, `source_template="exa-panel"`) and
delivered through the STANDARD distributors (file + display +
toast) — so it appears on the Workflow Products page with the
existing report-viewer modal, survives page reloads, and is cleared
by the same Clear action. Returns the product + delivery results.

## Skills

### `GET /api/v1/external-agent/skills/{name}`
Returns a Cogitate skill's `SKILL.md` body — the **consult-tool-injected delivery**: WE read the skill and include it in the prompt, because the external agent's own skill loader cannot see repo skills (verified live 2026-08-12).

```json
{"name": "cogitate-orientation", "body": "---\nname: cogitate-orientation..."}
```

404 when the skill doesn't exist. Accepts the directory name (`orientation`) or the frontmatter name (`cogitate-orientation`).

## Domain notes

- `AcpClient` owns ONE subprocess for the app lifetime (singleton via `get_acp_client()`), speaks JSON-RPC 2.0 over stdio
- **State isolation** (Phase 1, hardened): whatever the configured command resolves to, a hermes-shaped command (basename `hermes`) spawns with `HERMES_HOME` = the project `.hermes` — Exa's own memories/skills/config, never the operator's `~/.hermes`. The engine is the AGENT's (the ACP-agnostic boundary); the command config is the seam. Non-hermes commands (test fakes, other ACP agents) keep their env
- `session/new` requires `cwd` + `mcpServers` as a **list**; `session/prompt` takes content blocks directly; completion = the id:N result (`stopReason`) not a status event
- Events stream as `session/update` with `agent_message_chunk` / `agent_thought_chunk` / `tool_call` (`{kind, locations, title, toolCallId}`)
- Fix-mode gate: `session/set_config_option(edit_approval_policy=workspace_session|ask)` — the tool-level enforcement; see [[dev-notes/agents/hermes|Hermes vendor note]]
- **Chat authorization** (2026-08-21): the AcpClient's `_read_loop` handles `session/request_permission` → the WS `approval_request` → the chat's Approve/Deny card → `approval_response` → `resolve_permission` completes the ACP future. See [[dev-notes/agents/chat-authorization|Chat Authorization]] — the design + the security properties
- **Process-exit alarm** (2026-09-08): a pipe EOF raises `_on_pipe_eof` — logs the exit, ends the in-flight stream, fails the pending futures. See [[dev-notes/external-agent/known-issues|Exa Known Issues]]
