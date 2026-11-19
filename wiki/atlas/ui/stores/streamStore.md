---
title: streamStore
type: atlas-store
path: frontend/src/stores/streamStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# streamStore

**Path**: `frontend/src/stores/streamStore.ts`
**Type**: store slice (Zustand StateCreator)

## Purpose
Stream state slice — isStreaming, streamingMessage, error + actions, composed INTO cognitiveHubStore.

## State Shape
```typescript
export const createStreamSlice: StateCreator<...> = (set, get, store) => ({
  // isStreaming / streamingMessage / error + actions
})
```

## Actions
- Start/stop stream state, error set/clear (exact signatures from source)

## Selectors / Exports
```typescript
export { createStreamSlice }
export type { StreamSlice }
```

## Dependencies
None (state only).

## Usage Example
```tsx
// Used via cognitiveHubStore composition
```

## Data Flow / Notes
- Slice pattern composed into cognitiveHubStore

## Related
- stores/cognitiveHubStore.ts — composite root
- hooks/useChatStreaming.ts — stream state consumer (may dual-track)

## Deprecation / Obsolete Notes
Active (composed into cognitiveHubStore). No deprecation markers.