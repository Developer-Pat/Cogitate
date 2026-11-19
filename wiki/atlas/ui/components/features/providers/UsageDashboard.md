---
title: UsageDashboard
type: atlas-component
path: frontend/src/components/features/providers/UsageDashboard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# UsageDashboard

**Path**: `frontend/src/components/features/providers/UsageDashboard.tsx`
**Last Updated**: 2026-08-01

## Purpose

Phase 4 provider-usage dashboard. Renders usage summary cards (token counts with prompt/completion split, total cost in USD, request counts with success/failure split, average response time), a daily usage trend bar chart, a cost-by-provider breakdown with percentage bars, and a usage-by-model table. A Daily / Weekly / Monthly / All Time period selector drives the displayed range.

The component is **presentational and controlled** — it does not fetch data itself. The parent page (`ProviderDashboard`) supplies all data via props and owns refetching; when the user switches period, the component updates its internal selector state and notifies the parent through `onPeriodChange`, which triggers a refetch via the `useUsage` hook. Shows a spinner while `loading` and an empty-state message when no data is available for the period.

## Props Interface

```typescript
interface UsageDashboardProps {
  usage?: UsageSummaryResponse | null;
  usageByModel?: ModelUsageResponse[];
  usageTrend?: UsageTrendResponse[];
  costBreakdown?: CostBreakdownResponse | null;
  loading?: boolean;
  onPeriodChange?: (period: UsagePeriod) => void;
}
```

All data types are defined in `frontend/src/types/providers.ts`:

- `UsageSummaryResponse` — `period`, `total_tokens`, `total_cost_usd`, `total_requests`, `prompt_tokens`, `completion_tokens`, `success_count`, `error_count`, `avg_response_time_ms`, `period_start`, `period_end`
- `ModelUsageResponse` — `model`, `total_tokens`, `total_cost_usd`, `total_requests`, `prompt_tokens`, `completion_tokens`
- `UsageTrendResponse` — `date`, `total_tokens`, `total_cost_usd`, `total_requests`
- `CostBreakdownResponse` — `period`, `by_provider` (`Record<string, number>`), `total_cost_usd`
- `UsagePeriod` — `'daily' | 'weekly' | 'monthly' | 'all_time'`

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `React.useState` | React hook | Local `period` state backing the selector buttons |
| `Tooltip` (`../../ui/Tooltip`) | UI component | Tooltip overlays on period buttons and summary cards |
| Usage types (`../../../types/providers`) | Type-only import | Prop shapes (`UsageSummaryResponse`, `ModelUsageResponse`, `UsageTrendResponse`, `CostBreakdownResponse`, `UsagePeriod`) |
| `useUsage` hook (`frontend/src/hooks/useUsage.ts`) | Upstream hook | Fetches and holds all usage state; invoked by the parent page, not by this component |
| `usageService` (`frontend/src/services/domains/providers/usageService.ts`) | Service | Backend API calls consumed by `useUsage` via `apiClient` |

### API Endpoints

Data backing this dashboard is fetched from `usageService` (base path `/api/v1/providers/usage`), called by the `useUsage` hook:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/providers/usage?period={period}` | Usage summary for the selected period |
| `GET /api/v1/providers/usage/by-provider?period={period}` | Per-provider usage |
| `GET /api/v1/providers/usage/by-model?period={period}` | Usage by model (fills the table) |
| `GET /api/v1/providers/usage/trend?days={days}` | Daily token/cost trend (fills the chart) |
| `GET /api/v1/providers/usage/cost-breakdown?period={period}` | Cost breakdown by provider |

## Usage Example

```tsx
// Parent page: frontend/src/pages/ProviderDashboard.tsx (Usage tab)
const {
  usage, usageByModel, usageTrend, costBreakdown,
  loading: usageLoading, refreshUsage,
} = useUsage({ period: 'monthly', trendDays: 30 });

const handlePeriodChange = (_period: UsagePeriod) => {
  refreshUsage(); // re-fetch all usage data for the new period
};

// ...
{activeTab === 'usage' && (
  <UsageDashboard
    usage={usage}
    usageByModel={usageByModel}
    usageTrend={usageTrend}
    costBreakdown={costBreakdown}
    loading={usageLoading}
    onPeriodChange={handlePeriodChange}
  />
)}
```

## State Used

- Local state: `period: UsagePeriod` (default `'monthly'`) — drives selector highlighting; changed by `handlePeriodChange`, which also invokes the optional `onPeriodChange` prop (parent then refetches).
- No other component-level state — all displayed data arrives via props.
- Local helpers: `formatTokens()` (M/K abbreviations), `formatCurrency()` (`$` with 4 decimals), `getMaxTrendValue()` (scales the trend chart bars).

## Related Components

- Parent page: `frontend/src/pages/ProviderDashboard.tsx`
- Sibling dashboards on the same page: `frontend/src/components/features/providers/ProviderHealthModal.tsx`, `frontend/src/components/features/providers/ProviderConfigModal.tsx`, `frontend/src/components/features/providers/ModelSyncScheduler.tsx`, `frontend/src/components/features/providers/DefaultProviderConfig.tsx`
- `Tooltip`: `frontend/src/components/ui/Tooltip`
- `useUsage` hook: `frontend/src/hooks/useUsage.ts`
- `usageService`: `frontend/src/services/domains/providers/usageService.ts`
- Types: `frontend/src/types/providers.ts`
