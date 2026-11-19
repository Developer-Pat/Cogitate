---
title: LoadingIndicator
type: atlas-component
path: frontend/src/components/features/agentInteraction/LoadingIndicator.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# LoadingIndicator

**Path**: `frontend/src/components/features/agentInteraction/LoadingIndicator.tsx`
**Last Updated**: 2026-08-01

## Purpose
Animated 3-dot typing indicator — dots cycle active state every 300ms. Sized sm/md/lg with custom color.

## Props Interface
```typescript
interface LoadingIndicatorProps {
  size?: 'sm' | 'md' | 'lg'   // default 'md'
  color?: string              // default 'currentColor'
}
```

## Dependencies
None (pure JSX + setInterval).

## Usage Example
```tsx
{isStreaming && <LoadingIndicator size="sm" />}
```

## State Used
- activeDot (0..2) — cycling dot index via 300ms interval

## Related Components
- features/agentInteraction/ChatInterface.tsx — used during streaming