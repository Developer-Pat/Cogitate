---
title: System History
type: atlas-page
path: frontend/src/pages/SystemHistory.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# System History

**Component**: `frontend/src/pages/SystemHistory.tsx`
**Route**: `/history`
**Last Updated**: 2026-07-31

## Purpose
Log analysis and historical insights page (3 tabs). Philosophy: history is derived from logs (single source of truth) — no Zustand dependency, computed on demand.

## Key Features
- **Log Analysis tab**: issue alerts, summary stats cards (total/error/warning), histogram table of frequent log messages, refresh
- **Message Analysis tab**: performance cards (tokens/duration/tps/fastest provider-model), message distribution chart, provider comparison table, refresh
- **Session Analysis tab**: controls (limit selector + generate), summary cards, session cards
- Shared **DateRangeSelector** (default: last 24h) for log + message tabs

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| PageBanner | `components/ui/PageBanner.tsx` | Page header |
| PageContainer | `components/ui/PageContainer.tsx` | Layout wrapper |
| DateRangeSelector | `components/history/DateRangeSelector.tsx` | Time range picker |
| StatsCards | `components/history/StatsCards.tsx` | Log summary stats |
| HistogramTable | `components/history/HistogramTable.tsx` | Frequent-message table |
| IssueAlerts | `components/history/IssueAlerts.tsx` | Detected issue alerts |
| MessagePerformanceCards | `components/history/MessagePerformanceCards.tsx` | Token/duration stats |
| MessageDistributionChart | `components/history/MessageDistributionChart.tsx` | Distribution chart |
| ProviderComparisonTable | `components/history/ProviderComparisonTable.tsx` | Provider/model stats |
| SessionSummaryCards | `components/history/SessionSummaryCards.tsx` | Session summary |
| SessionCards | `components/history/SessionCards.tsx` | Session list cards |
| SessionAnalysisControls | `components/history/SessionAnalysisControls.tsx` | Limit + generate |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| useLogsHistogram | `hooks/useHistory.ts` | Histogram via React Query |
| useHistoryStats | `hooks/useHistory.ts` | Summary stats |
| useHistoryIssues | `hooks/useHistory.ts` | Issue detection |
| useMessageAnalysis | `hooks/useHistory.ts` | Message performance/distribution/provider stats |
| useSessionAnalysis | `hooks/useHistory.ts` | Session analysis |
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Logs**: `historyService` fetches via `logsService.getLogs()` -> `GET /api/v1/logs` (paginated, 100/page) and analyzes client-side (grouping by message, stats, issue detection)
- **Messages**: `getMessageAnalysis` fetches session message data via `sessionsService`, computes performance/distribution/provider stats client-side
- **Sessions**: `getLastSessionsAnalysis(limit)` via sessions service
- All analysis is client-side pure functions over fetched data (per HistoryService philosophy)

## State Management
- React Query (useHistory hooks)
- Local state: activeTab, timeRange, sessionLimit

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/logs` | Log data (paginated, filtered by time range) |
| GET | `/api/v1/sessions` | Session data (via sessionsService) |

## Related Pages
- Logs — raw log viewing/filtering
- Sessions — session management
- Analytics — usage/cost metrics