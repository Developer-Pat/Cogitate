---
title: PageBanner
type: atlas-component
path: frontend/src/components/ui/PageBanner.tsx
confidence: high
updated: 2026-09-15
tags: [type/component, domain/atlas-ui]
---
# PageBanner

**Path**: `frontend/src/components/ui/PageBanner.tsx`
**Last Updated**: 2026-09-15

## Purpose
Reusable page banner for consistent page headers across the app (matches sidebar styling). Exports `PageBanner` (left-aligned) and `CenteredPageBanner` (centered layout). Supports icon, title, description, optional info tooltip, children slot, an `action` slot (puts a control on the title row itself instead of wasting a row below), and `hideCommand`.

## Props Interface
```typescript
interface PageBannerProps {
  title: string
  description?: string
  icon?: string        // emoji/char rendered at 3xl
  className?: string
  children?: React.ReactNode   // extra content below description
  tooltip?: string    // PageBanner only — info button with data-tip
  action?: React.ReactNode  // title-row right side (e.g. <HelpButton/>) — avoids a wasted row
  hideCommand?: boolean  // suppress the app-wide ask-Exa widget on this banner
}
```

## The ask-Exa widget (`hideCommand`)

`PageBanner` seats the app-wide ask-Exa widget (`ExaPromptFlyout`, the "Exa"
pill) at the right end of its own title row — app chrome belongs to the shell,
and passing it in from ~26 pages would be 26 places to forget. `hideCommand`
suppresses it for a banner that seats the widget itself.

**When to use `hideCommand`.** The banner shrinks to its content, so a page that
wraps it in a `justify-between` header row alongside its own buttons pushes the
banner (and the pill) to the page's LEFT edge. The flyout panel opens leftward
(`absolute right-0`, 440 px), so from there it runs under the nav panel and is
clipped. A page with its own right-hand button group should pass `hideCommand`
and render `<ExaPromptFlyout />` as the first control in that group — the pill
then sits with its neighbours and the panel opens into the page.

## Dependencies
- `components/features/agentInteraction/ExaPromptFlyout` — the ask-Exa widget
  on the title row, unless `hideCommand`.

## Usage Example
```tsx
<PageBanner title="Logs" description="System and application logs" icon="📋" tooltip="Shows backend + browser logs" />

{/* Help button on the same line as the header (Workflow Automation pattern) */}
<PageBanner
  title="Workflow Automation"
  action={<HelpButton context="workflows" tooltipPosition="bottom" />}
/>

{/* A page with its own right-hand button group seats the widget itself */}
<div className="flex items-center justify-between mb-4">
  <PageBanner title="Logs" tooltip="…" hideCommand />
  <div className="flex items-center gap-2">
    <ExaPromptFlyout />
    <HelpButton context="logs" tooltipPosition="bottom" />
  </div>
</div>

<CenteredPageBanner title="Welcome" description="..." />
```

## State Used
None — stateless presentational.

## Related Components
- ui/PageContainer.tsx — layout wrapper these banners head
- ui/Tooltip.tsx — dedicated tooltip primitive
- features/agentInteraction/ExaPromptFlyout.tsx — the widget the banner seats
