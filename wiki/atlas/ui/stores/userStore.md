---
title: userStore
type: atlas-store
path: frontend/src/stores/userStore.ts
confidence: high
updated: 2026-08-01
tags: [type/store, domain/atlas-ui]
---
# userStore

**Path**: `frontend/src/stores/userStore.ts`
**Type**: store (Zustand, multi-export)

## Purpose
User state — current user, permissions, login/logout actions.

## State Shape
```typescript
interface UserState {
  user: User | null;
  permissions: string[];
  setUser(u): void; clearUser(): void; login(...): void; logout(): void;
}
```

## Actions
- setUser, clearUser, login, logout

## Selectors / Exports
```typescript
export const useUserStore = create<UserState>(...)
export const useUser = () => useUserStore(s => s.user)
export const usePermissions = () => useUserStore(s => s.permissions)
export const useUserActions = () => useUserStore(s => ({ ... }))
```

## Dependencies
None (state only).

## Usage Example
```tsx
const user = useUser()
useUserStore.getState().clearUser()
```

## Data Flow / Notes
- clearUser called by apiClient on 401

## Related
- services/apiClient.ts (the ONE client) — clearUser on 401
- Route permission checks

## Deprecation / Obsolete Notes
Active (auth flows). No deprecation markers.