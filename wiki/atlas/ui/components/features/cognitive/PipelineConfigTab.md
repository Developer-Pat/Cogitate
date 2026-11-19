---
title: PipelineConfigTab
type: atlas-component
path: frontend/src/components/features/cognitive/PipelineConfigTab.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# PipelineConfigTab

**Path**: `frontend/src/components/features/cognitive/PipelineConfigTab.tsx`
**Last Updated**: 2026-08-01

## Purpose
Strategy selectors for the cognitive pipeline — per-component dropdowns (context_builder, executor, memory_manager, response_formatter) with a Cognitive Profile selector at top. Selecting a profile populates the strategy values from the profile; manual overrides allowed.

## Props Interface
```typescript
export interface PipelineConfig {
  context_builder: string
  executor: string
  memory_manager: string
  response_formatter: string
}

interface PipelineConfigTabProps {
  config: PipelineConfig
  onConfigChange: (config: PipelineConfig) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| cognitiveProfileService | Service | Profile list for the selector |
| CognitiveProfile | Service type | Profile shape |
| useSettingsStore | Store | Persisted settings |
| frontendLoggingService | Service | Error logging |

## Usage Example
```tsx
<PipelineConfigTab config={pipeline} onConfigChange={setPipeline} />
```

## State Used
- local strategy selections; profile selection populates component values

## Related Components
- features/cognitive/CognitiveProfileSelector.tsx — profile picker at top
- features/configuration/CognitivePresetSelector.tsx — preset variant (659 lines)