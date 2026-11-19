---
title: System Info
type: atlas-page
path: frontend/src/pages/RagIndex.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# System Info

**Component**: `frontend/src/pages/SystemInfo.tsx`
**Route**: `/system-info`
**Last Updated**: 2026-07-31

## Purpose
Deep-dive system diagnostics page (947 lines) with 5 tabs: Overview, Detailed Metrics, System Details, Health Checks, and RAG Ingest. The RAG tab is the only place with real ingestion controls.

## Key Features
- **Overview tab**: SystemHealthCard, system status (backend API, uptime, environment), quick metrics (CPU/memory/disk)
- **Detailed Metrics tab**: CPU cores/load, memory breakdown, disk, network
- **System Details tab**: application/build info
- **Health Checks tab**: per-service status, uptime, manual health-check button
- **RAG Ingest tab**: RAG index health + ingestion controls (trigger incremental/full/force re-ingest, job polling)

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| PageBanner | `components/ui/PageBanner.tsx` | Page header |
| PageContainer | `components/ui/PageContainer.tsx` | Layout wrapper |
| SystemHealthCard | `components/dashboard/SystemHealthCard.tsx` | Health status card |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| useSystemStatus | `hooks/useSystemInfo.ts` | System status (30s refetch) |
| useSystemInfo | `hooks/useSystemInfo.ts` | System info (5min refetch) |
| useSystemMetrics | `hooks/useSystemHealth.ts` | Live metrics via SSE |
| useSystemHealth | `hooks/useSystemHealth.ts` | Health state |
| useServiceStatus | `hooks/useSystemHealth.ts` | Per-service status |
| useUptime | `hooks/useSystemHealth.ts` | Uptime |
| useHealthCheck | `hooks/useSystemHealth.ts` | Manual health check |
| useNotifications | `hooks/useNotifications.ts` | Toast notifications |

## Data Flow
- **Status/Info**: React Query via `healthService` -> `GET /api/v1/health` + `GET /api/v1/system`
- **Metrics**: SSE `GET /api/v1/system/metrics`
- **RAG**: `ragService` -> `GET /api/v1/rag/status`, `POST /api/v1/rag/ingest`, `GET /api/v1/rag/ingest/status`

## State Management
- React Query caches (system-status, system-info keys)
- `notificationStore` via useNotifications
- Local tab state

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/health` | Health status |
| GET | `/api/v1/system` | System info |
| GET | `/api/v1/system/metrics` (SSE) | Live metrics |
| GET | `/api/v1/rag/status` | RAG index health |
| POST | `/api/v1/rag/ingest` | Trigger ingestion |
| GET | `/api/v1/rag/ingest/status` | Ingestion job status |

## Related Pages
- Dashboard — summary strip of the same health/metrics data
- Analytics — usage stats (different data source)
- Logs — detailed log viewing
## Overview consolidation (2026-08-16, pre-push Phase C)

The Overview tab is the at-a-glance landing: the SystemHealthCard +
four quick-link cards (Metrics, Details, Health Checks, RAG) that
switch tabs. The System Status + Quick Metrics cards were REMOVED
from the Overview — they duplicated the Dashboard's QuickStats
tiles (which link here for detail) and the Detailed Metrics tab.
The dead useSystemStatus/useSystemInfo hooks were removed.

## The System Info removal (2026-08-16, pre-push Phase C)

The System Information page (monitoring: status, CPU/memory/disk,
health checks) was REMOVED — system monitoring isn't the product's
concern. The RAG Ingest tab (the product-relevant part) became
this standalone page: index health, trigger ingestion, job status,
configuration. The Dashboard's QuickStats tiles are now summary-
only (no link into the removed page). The backend health/metrics
endpoints stay (the dashboard + status indicator consume them).

> This page documents the RAG Index page that REPLACED the System
> Information page. The old page's monitoring content is gone.
