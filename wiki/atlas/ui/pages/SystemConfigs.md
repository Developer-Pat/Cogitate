---
title: System Configs
type: atlas-page
path: frontend/src/pages/SystemConfigsPage.tsx
confidence: high
updated: 2026-08-31
tags: [type/page, domain/atlas-ui]
---

# System Configs

**Component**: `frontend/src/pages/SystemConfigsPage.tsx`
**Route**: `/system-configs` (icon `server`, breadcrumb "System
Configs") — registered in `frontend/src/config/routes.ts`; the
sidebar's **Configuration** section (the alphabetical order's last
entry — the _28 Phase-5 build).
**Last Updated**: 2026-08-31

## Purpose

The **system status + the config surfaces** — the Configuration
section's roundup page (the _28 Phase 5; the "System (coming)"
placeholder's replacement).

- **The system status** card — the `/system/status` (health,
  uptime, version, environment, python).
- **The system info** card — the `/system/info` (application,
  host, platform, architecture, python impl).
- **The config surfaces** card — the pointers to the
  Configuration section's pages (Configuration, Settings,
  Provider Dashboard, Pipeline Config, Speech, Notifications).
- The **Refresh** button re-pulls both endpoints.
