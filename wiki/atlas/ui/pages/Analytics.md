---
title: Analytics
type: atlas-page
path: frontend/src/pages/Analytics.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Analytics

**Component**: `frontend/src/pages/Analytics.tsx`
**Route**: `/analytics`
**Last Updated**: 2026-07-31

## Purpose
Usage analytics dashboard — real metrics from the `usage_logs` table: request/token/cost summaries, trends, per-agent and per-provider breakdowns, cost analysis, and performance stats.

**The local volumes are visible**: the cognitive-pipeline workers
(the tag-survey fan-out on local Ollama models) log every call to
`usage_logs` (session_id NULL, agent_id = the worker) — the cost
page shows the local token volumes + enables per-run cost
estimates.

## Key Features
- Period selector: 7d / 30d / 90d (reloads all data)
- **Usage Summary** cards: total requests, tokens, cost, success rate
- **Usage Trends** line chart (tokens + requests, dual axis, recharts)
- **Cost Breakdown** pie chart by model + projected monthly cost
- **Usage by Agent** table with % of total progress bars
- **Provider Comparison** bar chart
- Performance section (response time percentiles, token stats, error rate)
- **Export CSV** (client-side, daily usage)

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| SummaryCard | inline in page | Stat card with trend indicator |
| recharts charts | `recharts` (library) | LineChart, PieChart, BarChart |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Load**: `Promise.all` of 3 apiClient calls on mount + period change:
  - `GET /api/v1/analytics/usage?period={period}` -> UsageStats
  - `GET /api/v1/analytics/costs?period=30d` -> CostBreakdown (always 30d)
  - `GET /api/v1/analytics/performance?period={period}` -> PerformanceMetrics
- **Export**: builds CSV from `usageStats.daily_usage`, Blob download

## State Management
- `notificationStore` — toasts for load errors / export success
- Local state: period, loading, usageStats, costBreakdown, performance

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/analytics/usage?period=` | Usage stats + daily series |
| GET | `/api/v1/analytics/costs?period=30d` | Cost breakdown by model |
| GET | `/api/v1/analytics/performance?period=` | Response time/token stats |

> Note: SummaryCard trend percentages (12.5/8.3/5.2/-0.5) are hardcoded, not computed from data.

## Related Pages
- Dashboard — shows recent activity count (same usage_logs source)
- SystemInfo — health/metrics (different: live system metrics, not usage)