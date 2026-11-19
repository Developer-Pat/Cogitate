---
title: useUsage
type: atlas-hook
path: frontend/src/hooks/useUsage.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useUsage

**Path**: `frontend/src/hooks/useUsage.ts`
**Type**: hook

## Purpose
Provider usage analytics — aggregate usage, per-provider/per-model breakdowns, trend, and cost breakdown.

## Exported API
```typescript
export const useUsage = () => ({
  usage, usageByProvider, usageByModel, usageTrend, costBreakdown,
  loading, error, refreshUsage,
})
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| usageService | domains/providers/usageService.ts | Usage endpoints (usage_logs backed) |

## Usage Example
```tsx
const { usageByProvider, costBreakdown, refreshUsage } = useUsage()
```

## State / Data Flow
- Fetches aggregates; refreshUsage re-queries

## Related
- features/providers/UsageDashboard.tsx — consumer
- pages/ProviderDashboard.tsx — usage tab