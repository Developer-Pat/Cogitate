---
title: Exa Known Issues
type: devnote
path: wiki/dev-notes/external-agent/known-issues.md
confidence: high
updated: 2026-09-08
tags: [type/dev-notes, domain/external-agent]
---

# Exa Known Issues

The Exa-reliability issue register: every known failure class, its
guard, and its current state. CURRENT STATE only — an issue is
FIXED when the guard ships, OPEN when it does not.

## The dead-model-request hang — FIXED

A model request that never returns used to wedge Exa in
"generating but not responding" indefinitely: requests ran on the
OpenAI SDK default (~10 min), a frozen stream never recovered, and
the whole-turn cap could not fire because it is checked BETWEEN
events — a hung request emits none.

**Guard**: the provider request timeout. The Exa home's config
(`.hermes/config.yaml`) sets
`providers.deepseek.request_timeout_seconds: 300`; the hermes
machinery (`get_provider_request_timeout`) applies it to every
request. A dead API call now ERRORS at 300s and the turn ends
with the error instead of hanging. (The config is gitignored —
the provisioning/reprovision path must carry the setting.)

**Still open**: a no-activity watchdog in the router's stream loop
for wedges the request timeout cannot see (a hung subprocess that
keeps its pipes open while emitting nothing). The stream's 120s
per-event wait covers queue silence only.

## The silent subprocess exit — FIXED

When the ACP subprocess died, both drain loops broke on EOF with
no log — the backend learned of Exa's death only on the next
prompt, and an in-flight stream hung on the dead process.

**Guard**: the process-exit alarm (`_on_pipe_eof` in
`app/domain/external_agent/services.py`). A pipe EOF logs
`EXITED unexpectedly (returncode=N)`, wakes the in-flight stream
with the closed sentinel (the turn ENDS, it does not hang), fails
the pending request futures, and nulls the process. The
intentional close() and the clean `session/closed` end stay quiet
(no false alarms).

## The runaway-turn class — FIXED

A silent turn of 50+ model calls (the rabbit-hole — endless
SUCCESSFUL exploration, not failures) crashes or hangs before
anyone sees it. The hermes loop guardrails are failure-based and
cannot see a successful runaway.

**Guard**: the tool-call budget. The router counts the tool calls
per turn: every `tool_call_checkin_every` (default 15) it sends a
`working` status beacon — the runaway is visible while it builds —
and at `max_tool_calls_per_turn` (default 75) it halts via the
same two-stage path as Stop, reporting `tool_call_limit`. Both are
config (0 = off), adjustable on the Exa Agent page.

## The state-isolation guard gap — FIXED

The data isolation (HERMES_HOME = the project `.hermes` — Exa's own
memories/skills/config/session state, never the operator's `~/.hermes`)
was conditional on ONE exact-match guard (`command[0] == "hermes"`):
a command-shape change (an absolute path to the binary, a different
agent name) would have silently fallen through to the operator's
home — memories, skills, keys.

**Guard**: the spawn guard fires on the command's BASENAME
(`hermes` / `hermes.exe`), so any hermes-shaped command gets the
isolated home whatever its path. The fake ACP scripts in the tests
(python3) keep their env. The spawn logs the effective HERMES_HOME;
the isolation probe reads the spawned process's real env from
`/proc/<pid>/environ` (ground truth, not a self-report).

**The design boundary**: the isolation is STATE-based by design —
engines live outside Cogitate (the external-agent layer is an ACP
client; any ACP-speaking agent can back it), and the command config
is the seam. Engine-version independence is an agent-level choice
(install hermes separately, point the command at it), not a
Cogitate-owned install.

## The edit-approval scope trap — FIXED

The "write_file was ACP-denied" quirk: the fix tier's auto-approve
(workspace_session) covers ONLY the session's cwd, and the session
cwd defaulted to `backend/` (the config's `cwd` = "" falls back to
the spawn process's working dir). Exa's legitimate writes to the
project root (`.exa-workspace/`, `frontend/`, `wiki/`) were OUTSIDE
the auto-approve scope → the ask-path → an unanswered permission
request → 60s → denied → the terminal-heredoc fallback (terminal
is the execution class, always allowed). The write tools are never
tool-layer-blocked (strictTools is not set in any tier); the tier
is the gate.

**Guard**: the Exa session's `cwd` = the project root (the
fix-tier's intended scope) — write_file/patch auto-approve across
the whole repo; edits outside the repo still hit the ask-path.

## Related

- [[dev-notes/external-agent/capabilities|Exa Capabilities]]
- [[atlas/api/routers/external-agent|External Agent — API]]
- [[dev-notes/known-issues|Known Issues]]
