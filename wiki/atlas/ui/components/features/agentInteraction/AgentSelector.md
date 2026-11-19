---
title: AgentSelector
type: atlas-component
path: frontend/src/components/features/agentInteraction/AgentSelector.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# AgentSelector

**Path**: `frontend/src/components/features/agentInteraction/AgentSelector.tsx`
**Last Updated**: 2026-09-17

## Purpose
Chat header agent dropdown — shows the selected agent (avatar from `agent.profileImageUrl` with an initials fallback, context-formatted name, a **provider badge**, and an **availability ✓/✗ badge**); opens a scrollable list with per-agent avatars + status; closes on outside click/Escape; footer shows agent count + Esc hint.

Both badges carry a tooltip, since neither explains itself on sight:

- **The provider badge** gives the provider **and the model the agent is configured with** — the one place to read an agent's model without leaving chat for Agent Profiles.
- **The availability badge** reports whether the agent is active, in words.

`Agent.health` is **not** used here. Provider health lives on the Agent Profiles surface, which reads the field through `ProfileService`.

## Props Interface
```typescript
// from types/agentInteraction
export interface AgentSelectorProps {
  agents: Agent[]
  selectedAgent: Agent | null
  onAgentSelect: (agent: Agent) => void
  loading?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| getShortAgentName, formatAgentNameForContext | utils/agentNameUtils | Name formatting |
| AvatarWithFallback | Component (local) | Agent avatar with initials fallback |
| lucide-react (`Check`, `X`) | icons | The availability badge |

## Usage Example
```tsx
<AgentSelector agents={agents} selectedAgent={current} onAgentSelect={setCurrent} loading={loading} />
```

## State Used
- isOpen (dropdown), dropdownRef (outside-click detection)
- lastGoodAvatarsRef (per-agent "last good avatar" map — an image, once seen for an agent, stays until a DIFFERENT url replaces it; the initials show only when the agent never had an image)

## Related Components
- features/agentInteraction/AvatarWithFallback.tsx — avatars
- features/agentInteraction/AgentListSelector.tsx — side-panel list variant
- pages/AgentInteraction.tsx — owner (the page renders this selector directly)