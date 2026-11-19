---
title: Exa Agent
type: atlas-page
path: frontend/src/pages/AgentIntegration.tsx
confidence: high
updated: 2026-08-12
tags: [type/page, domain/agents, status/active, feature/external-agent]
---

# Exa Agent

**Path**: `frontend/src/pages/AgentIntegration.tsx` — route `/agent-integration` (Agents nav group, after Chat). User-facing name: **Exa Agent**.

Configures **Exa** — the external consulting agent connection that powers the Agent Panel (the chat drawer on `/agent-interaction`). Exa is short for Exa-Agent (external agent); Hermes/OpenClaw runs as a local subprocess. This page is where its connection is configured and inspected.

## Layout

Two cards side by side (1-col on narrow screens):

### Connection card
- **Status badge** — `connected` / `offline` (the panel spawns lazily, so this may read offline until the panel has been opened at least once)
- **Session id** — truncated (first 13 chars) with full id in a tooltip
- **Restart agent** — closes the running subprocess; the next panel open spawns fresh with the saved config

### Configuration card
- **Agent command** — the ACP backend command (default `hermes acp`). The seam for pluralizing to other ACP-speaking agents later
- **Working directory** — where the agent runs; empty = backend cwd (project root)
- **Fix mode** — the explicit grant toggle (default OFF): when ON the consultant may write files/patch/run modifying commands. The grant applies on the next agent start (saving restarts the connection). Enforcement is tool-level (Hermes' edit-approval policy) — see [[dev-notes/agents/hermes|Hermes vendor note]]
- **Save** — disabled until a field changes (dirty gating); persists via `PUT /api/v1/external-agent/config` and closes the running subprocess so the new config takes effect on next spawn

## State

- `config` / `status` — loaded in parallel on mount (`getExternalAgentConfig` + `getExternalAgentStatus`)
- `command` / `cwd` — form fields, initialized from config
- `dirty` — `command !== config.command || cwd !== config.cwd`; drives Save enablement
- `saving` / `restarting` — in-flight flags
- Errors/success surface as notification-store toasts

## Related

- [[atlas/ui/components/features/agentInteraction/AgentPanel|AgentPanel]] — the chat drawer this configures (Diagnose hand-off, tool-call streaming)
- `externalAgentService` (API calls)
- `app/domain/external_agent` (backend domain: `services.py` AcpClient, `schemas.py`)
- [[dev-notes/agents/consulting-agent|Consulting Agent (dev-notes)]] — the keyboard-takeover design
