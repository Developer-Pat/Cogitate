---
title: IssueAlerts
type: atlas-component
path: frontend/src/components/history/IssueAlerts.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# IssueAlerts

**Path**: `frontend/src/components/history/IssueAlerts.tsx`
**Last Updated**: 2026-08-01

## Purpose
Collapsible alerts panel for detected issues — frequent errors and spikes from an IssueReport. Returns null when the report has neither.

## Props Interface
```typescript
interface IssueAlertsProps {
  issueReport?: IssueReport | null
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| IssueReport | types | Frequent errors + spikes data |

## Usage Example
```tsx
<IssueAlerts issueReport={report} />
```

## State Used
- expanded (collapsible panel)

## Related Components
- pages/SystemHistory.tsx — owner (uses HistoryService issue analysis)
- history/StatsCards.tsx — sibling stats