---
title: usageService
type: atlas-service
path: frontend/src/services/domains/providers/usageService.ts
confidence: high
updated: 2026-08-03
tags: [type/service, domain/atlas-ui]
---
# usageService

**Path**: `frontend/src/services/domains/providers/usageService.ts`
**Type**: service (object singleton)

## Purpose
Provider usage analytics — aggregates, per-provider/model breakdowns, trend, cost.

## Exported API
```typescript
export const usageService = {
  getUsage(), getUsageByProvider(), getUsageByModel(),
  getUsageTrend(), getCostBreakdown(),
}
```

## Endpoints
- `/api/v1/providers/usage`

## Backend note — model display normalization (2026-08-03)
`backend/app/domain/providers/usage_tracker.py` gained
`_normalize_model_display()`: old chat-path rows stored
`{provider_id}/{provider}/{model}` (e.g. `3/deepseek/deepseek-v4-flash`);
a leading numeric segment is stripped at aggregation time so the UI
shows a clean `{provider}/{model}`. Pure display normalization — data
is not modified.

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |

## Usage Example
```tsx
const trend = await usageService.getUsageTrend()
```

## Data Flow / Notes
- Backs useUsage hook; usage_logs backed

## Related
- hooks/useUsage.ts — consumer
- features/providers/UsageDashboard.tsx — UI

## Deprecation / Obsolete Notes
Active (1 hook consumer). No deprecation markers.