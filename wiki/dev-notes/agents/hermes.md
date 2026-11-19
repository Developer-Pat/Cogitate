---
title: Hermes (external agent vendor note)
type: atlas-devnote
category: agents
order: 8
confidence: high
updated: 2026-08-13
tags: [type/dev-notes, domain/agents, status/active, feature/external-agent]
---

# Hermes — external agent vendor note

Agent-specific quirks and features discovered while integrating Hermes
as the consulting agent via ACP. OpenClaw (and any future ACP-speaking
agent) gets its own note here when it joins — **the feature is generic,
these are the vendor differences**.

## Protocol quirks (verified 2026-08-11/12)

1. `session/new` **requires `cwd`** — missing → `Invalid params`
2. `mcpServers` must be a **LIST `[]`** — dict rejected
3. `session/prompt` takes **content blocks directly** — `[{type: text,
   text: ...}]`; a `{role, content}` wrapper is REJECTED
4. Completion = the **id:N session/prompt RESULT** (`stopReason:
   end_turn`) — NOT a `status=completed` event
5. Reply streams as `session/update` with `agent_message_chunk` /
   `agent_thought_chunk`
6. **Tool use** streams as `session/update` with `sessionUpdate:
   "tool_call"` — payload `{kind, locations, title, toolCallId}`
   (the watchable workspace; the app forwards these to the panel)

## The startup race (live-caught 2026-08-11)

Hermes emits `available_commands` + a startup `usage_update` AFTER
`session/new`'s result. A prompt sent before those finish is
**silently lost** — `start()` waits for the startup usage event as
the session-ready signal. Same for ANY early protocol call: a
`session/set_config_option` sent before the ready signal **times out
unanswered** (observed 2026-08-13 — fixed by ordering policy set
after the ready-wait).

## EDIT-APPROVAL GATE (the big discovery, 2026-08-13)

Hermes' ACP adapter has a **per-session edit-approval policy** —
the real tool-level enforcement point for the fix-mode grant:

| Policy | Effect |
|---|---|
| `ask` (default) | EVERY write_file/patch prompts; a client that never answers = **denied** |
| `workspace_session` | auto-approves edits **inside cwd**; asks outside/sensitive |
| `session` | auto-approves all except sensitive paths |

- Set via `session/set_config_option` with `config_id:
  "edit_approval_policy"`, `value: "<policy>"` — verified live
- **Sensitive paths are ALWAYS guarded** by Hermes regardless of
  policy: `.env`, `.env.local`, `.env.production`, `id_rsa`,
  `id_ed25519`, anything under `.git`/`.ssh`
- `mode` param on `session/new` (default/accept_edits/dont_ask)
  exists but is NOT honored for direct ACP sessions — use
  `session/set_config_option`, not the mode param
- `--yes` / `--accept-hooks` CLI flags do NOT bypass edit approval
- **Terminal-based writes bypass the edit gate** (`printf > file`
  succeeds even in `ask`) — the read-only prompt directive is the
  layer covering that; strictTools (`capabilities.strictTools: true`
  on session/new) blocks the dedicated write tools as an extra layer

## HALT PATH — session/cancel (the gentle stop, 2026-08-13)

ACP has a **standard cancel**: `AGENT_METHODS["session_cancel"] =
"session/cancel"` (acp/meta.py) — a NOTIFICATION (no id, no
response), params `{"sessionId": "<id>"}`. Any ACP agent implements
it; Hermes maps it to `state.agent.interrupt()` — the SAME
mechanism Ctrl+C uses in the CLI: the turn stops, the session stays
alive, the next prompt continues normally.

Cogitate's halt ladder (see external-agent-domain.md for the router
wiring):

1. **Stop** → `session/cancel` (gentle) → if the stream doesn't end
   within CANCEL_GRACE_SECONDS (5s), escalate to the kill
2. **Force Kill (nuke)** → process-group SIGKILL, immediate — the
   app spawns the subprocess with `start_new_session=True`, so
   `os.killpg(pid, SIGKILL)` hits Exa + its tool children ONLY
   (the backend / VS Code extension / CLI are in other groups).
   Targeted by ownership, not by name — NEVER `pkill -f
   "hermes acp"` (substring match = suicide bomb; it kills every
   hermes acp including the transport doing the stopping).
3. **WS disconnect** → auto-halt (a mid-turn disconnect used to
   only DETACH the stream while the subprocess ran on — the actual
   runaway; now it cancels too)

## THE PROMPT QUEUE — "Queued for the next turn." (2026-08-13)

Hermes' ACP adapter maintains `state.queued_prompts` per session
(acp_adapter/server.py ~line 1376). When a `session/prompt` arrives
while a turn is already running, Hermes APPENDS it to the queue and
replies **"Queued for the next turn. (N queued)"** — then, when the
current turn ends, it **auto-runs every queued prompt** in order
(server.py ~1668: `while True: next_prompt = queued_prompts.pop(0)`).

Critical implications for the stop-runaway architecture:

- **Stop (gentle `session/cancel`) does NOT clear the queue.** It
  interrupts the RUNNING turn; queued prompts survive and fire
  anyway the moment the turn ends. A user who hit Stop on a queued
  prompt sees it "restart with my prompt and die anyway"
  (Exa_dialog_04).
- **There is NO ACP method to clear or decline the queue.** The only
  queue command is `queue` (add). `reset` clears history but NOT
  `queued_prompts`.
- **The queue is per-SessionState** (session.py:169). Killing the
  subprocess (Force Kill / escalation) respawns a NEW session on the
  next prompt → empty queue. That is the ONLY reliable queue-clear.
- **The queue can only fill via double-send.** The panel's busyRef
  guard (2026-08-13) prevents two prompts in the same tick; a typed
  prompt auto-discards a pending hand-off. With those in place the
  queue stays empty in practice — but any future client that sends
  two prompts back-to-back will re-introduce the gap.

Rule: never send a second prompt while one is in flight; if a
"Queued for the next turn" reply ever appears, the queue is a
stop-runaway gap — escalate to Force Kill to clear it.

## Full toolset exposed

The ACP session exposes Hermes' complete tool registry: terminal,
read_file, write_file, search_files, patch, process, execute_code,
web_search, web_extract, browser_*, skill_view, skill_manage,
skills_list, memory, todo, delegate_task, session_search. The
consultant manages its OWN diagnostic loop with these (keyboard-
takeover model) — no per-tool whitelist needed for read-only.

## Config knobs

- Command: `hermes acp` (the pluralization seam — other ACP agents
  later); cwd: project root (reads wiki/code/logs directly)
- Hermes' own skills do NOT see repo `skills/cogitate/*` — the app
  EMBEDS the skill text in the prompt (consult-tool-injected
  delivery; `GET /api/v1/external-agent/skills/{name}`)

## Related

- [[dev-notes/agents/external-agent-domain|External Agent Domain]] — the client + protocol
- [[dev-notes/agents/consulting-agent|Consulting Agent]] — the feature/design
- [[atlas/api/routers/external-agent|External Agent API]]
- [[atlas/ui/components/features/agentInteraction/AgentPanel|AgentPanel]]
