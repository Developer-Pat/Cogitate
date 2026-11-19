---
title: Agent Orchestration
type: atlas-entity
path: wiki/entities/agent-orchestration.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Agent Orchestration

## Overview

Agents are the core actors: provider+model pairing, capability
profile, enabled tools, health state. Domain: AgentService
(backend/app/domain/agents/services.py).

## Key concepts

- **Profiles** — capability-based (conversational, research-std,
  code-gen, system-admin...). cognitive_profile_id FK → cognitive
  profiles.
- **Provisioning** — POST /api/v1/agents/{name}/provision +
  status/archive (provisioning_router.py).
- **Templates** — system-prompt + agent templates
  (save-as-template/apply).
- **Health** — per-agent ok/warn/fail from consecutive failures;
  dismissal acknowledges past failures (F1–F6). Scan:
  scripts/core/check_agent_health.py.
- **Multi-agent** — chat_delegate (read-only agent-to-agent);
  teams (agent groups); agent_lists; delegation logging.

See [[dev-notes/agents/agent-lifecycle]] and
[[dev-notes/agents/multi-agent-chat]].
