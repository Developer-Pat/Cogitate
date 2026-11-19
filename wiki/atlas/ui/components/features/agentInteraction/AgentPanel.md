---
title: AgentPanel
type: atlas-component
path: frontend/src/components/agentPanel/AgentPanel.tsx
confidence: high
updated: 2026-09-18
tags: [type/component, domain/agents, status/active, feature/external-agent]
---

# AgentPanel

**Path**: `frontend/src/components/agentPanel/AgentPanel.tsx` — the external agent (Exa) chat drawer, mounted app-wide in `App.tsx`.

Help-style right-drawer (fixed overlay, slides from the right, does NOT shrink the layout, no mask — the page stays interactive). Own chat area talking directly to the ACP subprocess (Hermes/OpenClaw) — NOT the agent-chat backend (the thin-client rule: the external agent does the thinking, Cogitate only relays text).

Opens via `window.dispatchEvent(new CustomEvent('open-agent-panel'))` (with optional `detail.context` for situation-aware hand-offs) or the **Agent** button in the `AgentInteraction` header.

## Header

- Title + connected/offline badge + fix-mode badge (read-only vs fix granted)
- **Diagnose** (primary button) — **situation-aware (2026-08-13)**: renders ONLY on a plain (no-context) open, i.e. from the Chat page — it is the Chat-situation button (hands the ACTIVE session to Exa). Hidden when the panel opens with a context hand-off (Macros/Setup/Execution) so no one presses a button meant for a situation they don't know about. The keyboard-takeover hand-off: reads the ACTIVE session + agent from `cognitiveHubStore`, fetches the Cogitate skills (`cogitate-orientation` + `analyze-logs`) and **embeds their full text in the prompt** (consult-tool-injected delivery), then streams the consultant's investigation live
- **Copy** — copies the FULL transcript (user messages, assistant text, AND every tool-activity line, including scrolled-off ones; activity is captured in full, not truncated). Clipboard write with ✓ feedback + textarea fallback
- **Save** (2026-08-13, Option B) — persists the LAST assistant report into the workflow-product flow (`POST /external-agent/report`): it shows on the Workflow Products page with the report-viewer modal and survives the ephemeral panel chat. Deliberately saves the deliverable (the report), not the whole transcript; skips the "⏹ Stopped." marker
- **Clear** — clears the panel thread
- **✕** — closes

## Messages

- User bubbles (primary, right) / assistant bubbles (left)
- **Markdown rendering** — assistant text renders via the shared `MarkdownText` (`components/ui/`), so tables/headings/code display properly (Exa's status reports used to show raw pipes). It splits the text at block boundaries with each block memoized, so a growing reply does not re-parse its finished half.
- **The message row is memoized** — `MessageRow` is a `memo` component taking `(m, onConfirm, onDiscard)`. This panel re-renders per stream chunk *and* once a second (the elapsed timer), so an unmemoized row would re-render on every tick; untouched messages keep their object identity through the `prev` spread, so the memo bails on them. The two handlers must stay `useCallback`, or a fresh function prop each render defeats the memo.
- **Tool activity** — live `tool_call` events render inside the assistant bubble as plain text lines (e.g. `terminal: grep -nE "ERROR|WARNING" backend/logs/app.log`); **static ▸ markers** after the turn ends. NO per-line spinners (the single "thinking…" indicator conveys activity — user, 2026-08-13)
- Single "thinking…" indicator while the consultant works

## Halt path (2026-08-13, incident exa-runaway)

- **Stop** (red, replaces Send while busy) — gentle `session/cancel` interrupt (ACP-standard Ctrl+C-equivalent); auto-escalates to kill-by-PID after the grace window if the agent ignores it. Never disabled by busy/input-freeze
- **⚠ Force Kill** (nuke, bottom-right danger row, always available while connected) — process-group SIGKILL (kills Exa AND its tool children, never the backend/CLI), two-click confirm. The only reliable way to clear a queued Hermes prompt (fresh session = empty queue)
- Both report exactly one "⏹ Stopped." (dedup flag) — the double-stop bug was a receiver re-queue, fixed 2026-08-13

## Behavior

- Lazily connects on open (`/api/v1/external-agent/ws`); the server spawns the subprocess with the persisted config from the Agent Integration page
- **Auto-reconnect (2026-08-13)** — WS death (backend reload, network blip) no longer leaves the panel offline; reconnects with exponential backoff (1s→2s→4s…15s cap), timer cleared on close/unmount
- **No auto-fire** — pending hand-offs surface with Send/Discard, never execute on their own (incident fix)
- **No double-send (2026-08-13)** — a synchronous `busyRef` guard (set before the WS write) blocks a second prompt in the same tick; a typed prompt or Diagnose supersedes/discards any pending hand-off. Without this, two prompts reach Hermes and one gets queued ("Queued for the next turn.") — see the prompt-queue dev note
- **Context hand-offs** — `macros` embeds the `cogitate-macro-management` skill (fetched via `/skills/{name}` and appended to the pending prompt); the panel thread is ephemeral (cleared on page reload); Hermes' session memory persists

## Related

- [[atlas/ui/pages/AgentIntegration|Exa Agent]] — the config page (command/cwd/restart/fix-mode grant)
- [[atlas/ui/pages/Macros|Macros]] — the Ask Exa builder hand-off (macro generation)
- `externalAgentService` (REST config/status)
- `app/domain/external_agent` (backend: AcpClient, WS bridge)
- [[dev-notes/agents/consulting-agent|Consulting Agent (dev-notes)]] — the keyboard-takeover design
- [[dev-notes/agents/hermes|Hermes (vendor note)]] — protocol quirks + edit-approval gate + HALT PATH + the prompt queue
- [[atlas/api/routers/external-agent|External Agent API]] — the WS protocol (prompt/cancel/nuke) + skills endpoint
