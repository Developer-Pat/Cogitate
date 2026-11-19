---
title: PageContainer
type: atlas-component
path: frontend/src/components/ui/PageContainer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# PageContainer

**Path**: `frontend/src/components/ui/PageContainer.tsx`
**Last Updated**: 2026-08-01

## Purpose
Standard page layout wrapper — padding + optional centered max-width constraint. Used as the outer container for page content.

## Props Interface
```typescript
interface PageContainerProps {
  children: React.ReactNode
  className?: string
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | '6xl' | '7xl' | 'full'  // default '7xl'
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<PageContainer maxWidth="xl">
  <PageBanner title="..." />
  ...
</PageContainer>
```

## State Used
None — stateless.

## Related Components
- ui/PageBanner.tsx — banner component typically inside this container