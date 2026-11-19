---
title: usePageTitle
type: atlas-hook
path: frontend/src/hooks/usePageTitle.tsx
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# usePageTitle

**Path**: `frontend/src/hooks/usePageTitle.tsx`
**Type**: hook (multi-export)

## Purpose
Page title management via react-helmet-async — static titles (formatPageTitle) and dynamic titles (getDynamicPageTitle).

## Exported API
```typescript
export function usePageTitle(title: string)
export function useDynamicPageTitle(page: string, entityName?: string)
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| react-helmet-async | Library | <Helmet> title injection |
| formatPageTitle, getDynamicPageTitle | config/pageTitles | Title formatting |

## Usage Example
```tsx
usePageTitle('Dashboard')
useDynamicPageTitle('agents', selectedAgent?.name)
```

## State / Data Flow
- Sets document title through Helmet on mount/title change

## Related
- All pages — title hooks
- config/pageTitles.ts — title format config