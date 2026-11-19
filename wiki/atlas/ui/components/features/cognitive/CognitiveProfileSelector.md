---
title: CognitiveProfileSelector
type: atlas-component
path: frontend/src/components/features/cognitive/CognitiveProfileSelector.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CognitiveProfileSelector

**Path**: `frontend/src/components/features/cognitive/CognitiveProfileSelector.tsx`
**Last Updated**: 2026-08-01

## Purpose
Table/card-based cognitive profile picker — each profile renders as a radio row with name, part-code (`ctx-exe-fmt-mem`), description tooltip, and pipeline dims (Context/Reasoning/Memory). Includes a '--- None ---' option for plain LLM chat. Used in agent create/edit forms (user prefers table selectors over dropdowns for this).

## Props Interface
```typescript
interface CognitiveProfileSelectorProps {
  value: number | null | undefined
  onChange: (profileId: number | null) => void
  disabled?: boolean
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| cognitiveProfileService.list() | Service | Fetches profiles |
| CognitiveProfile | Service type | Profile shape (context_builder, executor, response_formatter, memory_profile_name) |
| frontendLoggingService | Service | Error logging |

## Usage Example
```tsx
<CognitiveProfileSelector value={agent.cognitive_profile_id} onChange={(id) => updateAgent({ cognitive_profile_id: id })} />
```

## State Used
- profiles (list), loading (fetch state) — local useState

## Related Components
- features/cognitive/CognitiveProfilesTab.tsx — profile CRUD tab
- pages/AgentProfiles.tsx — page using this selector in forms