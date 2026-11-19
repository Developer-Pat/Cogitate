---
title: AvatarWithFallback
type: atlas-component
path: frontend/src/components/features/agentInteraction/AvatarWithFallback.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---
# AvatarWithFallback

**Path**: `frontend/src/components/features/agentInteraction/AvatarWithFallback.tsx`
**Last Updated**: 2026-09-10

## Purpose
Avatar image with initials fallback. The fallback is **per-src** (2026-09-08): a failed load records the failing `src`; a remount or a genuinely new `src` re-tries the image instead of trusting the old failure (the earlier one-shot `onError` stuck the initials forever after a single transient 404).

## Props Interface
```typescript
interface AvatarWithFallbackProps {
  src: string
  alt: string
  initials: string
  size: string   // tailwind size class, e.g. 'w-8 h-8'
}
```

## Dependencies
None (pure JSX).

## Usage Example
```tsx
<AvatarWithFallback src={agent.profileImageUrl ?? ''} alt={agent.name} initials={agent.name.slice(0,2)} size="w-8 h-8" />
```

## State Used
- `failedSrc: string | null` — the src whose load failed; `showFallback = failedSrc === src` (so a new src always starts from the image)

## Related Components
- features/agentInteraction/AgentSelector.tsx — the only consumer (agent avatars in the chat header + dropdown list).