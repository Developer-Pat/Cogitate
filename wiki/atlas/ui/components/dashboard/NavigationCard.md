---
title: NavigationCard
type: atlas-component
path: frontend/src/components/dashboard/NavigationCard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# NavigationCard

**Path**: `frontend/src/components/dashboard/NavigationCard.tsx`
**Last Updated**: 2026-08-01

## Purpose
Dashboard quick-navigation card — icon badge, title, description, and 'Open' action; whole card is a router Link with hover lift effect.

## Props Interface
```typescript
interface NavigationCardProps {
  icon: React.ReactNode
  title: string
  description: string
  to: string   // react-router path
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| Link | react-router-dom | Card navigation |

## Usage Example
```tsx
<NavigationCard icon={<Icon />} title="Logs" description="View logs" to="/logs" />
```

## State Used
None — stateless.

## Related Components
- dashboard/NavigationCards.tsx — grid of these cards