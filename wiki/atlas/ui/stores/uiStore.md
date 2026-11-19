---
title: uiStore
type: atlas-store
path: frontend/src/stores/uiStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# uiStore

**Path**: `frontend/src/stores/uiStore.ts`
**Type**: store (Zustand)

## Purpose
UI state — sidebar collapsed flag + toggle (useSidebarCollapsed selector).

## State Shape
```typescript
interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar(): void; setSidebarCollapsed(v: boolean): void;
}
```

## Actions
- toggleSidebar, setSidebarCollapsed

## Selectors / Exports
```typescript
export const useUIStore = create<UIState>(...)
export const useSidebarCollapsed = () => useUIStore(s => s.sidebarCollapsed)
```

## Dependencies
None (state only).

## Usage Example
```tsx
const collapsed = useSidebarCollapsed()
```

## Data Flow / Notes
- Backs sidebar collapse; syncs via uiStateBridge

## Related
- App.tsx, ChatInterface.tsx — consumers
- hooks/useUIStateBridge.ts — persistence bridge
- services/uiStateBridge.ts — persistence

## Deprecation / Obsolete Notes
Active (3 consumers). No deprecation markers.