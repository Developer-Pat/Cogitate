---
title: BuildModeSwitch
type: atlas-component
path: frontend/src/components/BuildModeSwitch.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# BuildModeSwitch

**Path**: `frontend/src/components/BuildModeSwitch.tsx`
**Last Updated**: 2026-09-17

## Purpose

The dashboard control that moves the frontend between its two builds. It **requests** the switch; the launcher performs it (`POST /api/v1/system/mode` → `cogitate.sh mode <mode>`), preserving the app-requests / launcher-acts contract the restart path already uses.

The switch keeps the **same port**. The auth token, the persisted stores and the cross-tab channel are all origin-scoped, so a second port would sign the user out and sever tab coordination — the comparison would then be measuring the wrong thing.

A switch **to** production builds first and swaps the server only if that build succeeds, so a failed build leaves the running app untouched.

## Props Interface

**No props.** The current mode comes from the service; everything else is driven by the local `phase`.

## The four phases

| Phase | UI |
|---|---|
| `idle` | just the button — `btn btn-xs btn-outline` |
| `confirming` | `Switch to production?` / `Switch to development?` |
| `switching` | `Switching to <target>…` |
| `timeout` | `Still not back` — after `SWITCH_TIMEOUT_MS` |

The dialog is a DaisyUI `<dialog className="modal" open={…}>`, kept mounted and toggled by `open` rather than conditionally rendered.

## How the switch is detected as landed

**Not by polling the mode record.** The launcher writes the mode file **before** the new server binds, so a client that trusted it would reload straight into the OLD build.

Instead the component watches the **entry module the server actually serves** — `/src/main.tsx` on the dev server, `/assets/index.HASH.js` in production. It captures the current page's entry **before** requesting, then polls the served `index.html` until that entry changes, and only then reloads.

| Export | Type | Purpose |
|---|---|---|
| `BuildModeSwitch` | Component | The button + modal (also the default export) |
| `entryFromHtml(html)` | Pure function | The module entry an `index.html` points at |
| `entryFromDocument(doc)` | Pure function | The entry the **currently loaded** page was served with |
| `SWITCH_TIMEOUT_MS` | Constant | `300_000` — how long to wait before showing "Still not back" |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `modeService` (`@/services/domains/system/modeService`) | Service | `GET` the current mode; `POST` the switch |
| `useNotificationStore` (`@/stores/notificationStore`) | Store | Success / failure toasts |
| `Tooltip` (`./ui/Tooltip`) | Component | Names the button |

## Usage Example

```tsx
// In the dashboard header, right after the badge (see frontend/src/pages/Dashboard.tsx)
import BuildModeSwitch from '../components/BuildModeSwitch'

<BuildModeBadge />
<BuildModeSwitch />
```

## Related Components

- `frontend/src/components/BuildModeBadge.tsx` — reports the mode this control changes
- `frontend/src/services/domains/system/modeService.ts` — the request itself
- `frontend/src/pages/Dashboard.tsx` — the only consumer
