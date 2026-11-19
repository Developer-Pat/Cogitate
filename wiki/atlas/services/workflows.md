---
title: Services — Workflows
type: atlas-api
path: wiki/atlas/services/workflows.md
category: api-atlas
order: 5
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/services, status/active]
---

# Workflows Services

The workflows domain owns workflow design + experimentation —
Cogitate's core purpose. Execution, routing, triggers, approvals,
compositions, multi-agent orchestration, versioning, and ab-testing.

## Services

| Service | Responsibility | Status |
|---------|---------------|--------|
| `MultiAgentOrchestrationService` | Multi-agent workflow execution | ACTIVE |
| `RoutingService` | Dynamic agent routing (classification → agent) | ACTIVE |
| `TriggerService` | Workflow triggers (schedules, webhooks, DB events) | ACTIVE |
| `ApprovalService` | Human-in-the-loop approvals | ACTIVE |
| `CompositionService` | Workflow compositions | ACTIVE |
| `VersionService` | Versioned workflow configs | **DORMANT** |
| `ABTestService` | A/B experimentation | **DORMANT** |

## Dependencies (mermaid)

```mermaid
flowchart LR
    API[Workflow API routers] --> Orch[MultiAgentOrchestrationService]
    API --> Route[RoutingService]
    API --> Trig[TriggerService]
    API --> Appr[ApprovalService]
    API --> Comp[CompositionService]
    API --> Ver[VersionService — DORMANT]
    API --> AB[ABTestService — DORMANT]
    Orch --> Route
    Orch --> AgentS[AgentService]
    Orch --> ToolS[ToolExecutionService]
    Orch --> PComp[ProviderCompletionService]
    Trig --> Orch
    Appr --> Orch
```

## Cross-service calls

- **Workflows → Agents**: orchestration delegates to agents
- **Workflows → Tools**: workflow steps execute tools
- **Workflows → Providers**: LLM calls (classification, content gen)
- **Versioning/ab-testing**: DORMANT — core purpose, un-expanded;
  demo data kept as test material (user decision 2026-08-07)

## Status

**ACTIVE** (execution/routing/triggers/approvals) with a
**DORMANT** sub-family (versioning/ab-testing) — the state map's
clearest verdict, documented for the pruning picture.

## Related

- [[atlas/api/routers/workflows|Workflows API]]
- [[atlas/api/routers/ab-tests|A/B Tests API]]
- [[dev-notes/workflows/workflow-architecture|Workflow Architecture]]
