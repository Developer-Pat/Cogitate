---
title: TagBadge
type: atlas-component
path: frontend/src/components/Tools/TagBadge.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# TagBadge

**Path**: `frontend/src/components/Tools/TagBadge.tsx`
**Last Updated**: 2026-08-01

## Purpose
Tool tag chip — optional tooltip, sized variants, optional click handler.

## Props Interface
```typescript
interface TagBadgeProps {
  tag: string
  showTooltip?: boolean  // default true
  size?: 'sm' | 'md' | 'lg'  // default 'sm'
  clickable?: boolean   // default false
  onClick?: (tag: string) => void
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| KNOWN_TAGS | types/toolTags.ts | Known tag metadata (colors) |

## Usage Example
```tsx
<TagBadge tag={t} clickable onClick={filterByTag} />
```

## State Used
None — stateless.

## Related Components
- Tools/ToolsTableFilters.tsx — active tag chips
- Tools/ToolsTableRow.tsx — row tags