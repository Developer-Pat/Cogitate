---
title: BuildModeBadge
type: atlas-component
path: frontend/src/components/BuildModeBadge.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# BuildModeBadge

**Path**: `frontend/src/components/BuildModeBadge.tsx`
**Last Updated**: 2026-09-17

## Purpose

A one-word badge in the dashboard header naming which build is being served — `DEV` or `PROD`. It earns its place because the two builds are otherwise behaviourally identical, so without it a stale bundle and a correct one look the same.

**It reports the BUILD, not the host.** `import.meta.env.DEV` is baked in by Vite at build time, so the badge cannot drift from what was actually compiled: a scratch server and a deployed one both read `PROD`, and both are right. A badge derived from the port or the hostname would be wrong in exactly the case it is needed.

`DEV` is the warning-coloured one deliberately — it is the slower build (unbundled, unminified, StrictMode double-rendering), so it reads as the anomaly and `PROD` as the expected state.

## Props Interface

**No props.** The component reads the build flag itself.

## Exports

| Export | Type | Purpose |
|---|---|---|
| `BuildModeBadge` | Component | The badge (also the default export) |
| `buildModeInfo(isDev)` | Pure function | Returns `{ label, tip }` for a given build flag — split out so **both** branches are testable without stubbing `import.meta.env` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `Tooltip` (`./ui/Tooltip`) | Component | The one-line explanation of the difference between the builds |
| `import.meta.env.DEV` | Build-time constant | Substituted by Vite at build time; the badge's only input |

## Usage Example

```tsx
// In the dashboard header (see frontend/src/pages/Dashboard.tsx)
import BuildModeBadge from '../components/BuildModeBadge'

<BuildModeBadge />
```

## Related Components

- `frontend/src/components/BuildModeSwitch.tsx` — the control that changes the mode this badge reports
- `frontend/src/pages/Dashboard.tsx` — the only consumer
