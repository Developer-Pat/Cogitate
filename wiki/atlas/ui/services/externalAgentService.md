---
title: externalAgentService
type: atlas-service
path: frontend/src/services/externalAgentService.ts
confidence: high
updated: 2026-08-12
tags: [type/service, domain/agents, status/active]
---

# externalAgentService

**Path**: `frontend/src/services/externalAgentService.ts`

API client for the external agent (Hermes/OpenClaw) integration — the backend that backs the Agent Panel.

## Methods

| Method | Endpoint | Returns |
|---|---|---|
| `getExternalAgentConfig()` | `GET /api/v1/external-agent/config` | `ExternalAgentConfig {command, cwd}` |
| `updateExternalAgentConfig(patch)` | `PUT /api/v1/external-agent/config` | updated `ExternalAgentConfig` |
| `getExternalAgentStatus()` | `GET /api/v1/external-agent/status` | `ExternalAgentStatus {connected, session_id, command, cwd, error}` |
| `restartExternalAgent()` | `POST /api/v1/external-agent/restart` | `{status: "restarted"}` |

## Types

```ts
interface ExternalAgentConfig {
  command: string;  // ACP backend command, default "hermes acp"
  cwd: string;      // working dir; "" = backend cwd
}

interface ExternalAgentStatus {
  connected: boolean;
  session_id?: string | null;
  command: string;
  cwd: string;
  error?: string | null;
}
```

## Notes

- Used by `AgentIntegration.tsx` (the config page) only — the Agent Panel itself talks over a WebSocket, not this service.
- `updateExternalAgentConfig` closes the running subprocess server-side so the next panel open spawns with the new config.
