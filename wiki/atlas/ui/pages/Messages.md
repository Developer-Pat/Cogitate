---
title: Messages
type: atlas-page
path: frontend/src/pages/Messages.tsx
confidence: high
updated: 2026-09-15
tags: [type/page, domain/atlas-ui]
---
# Messages

**Component**: `frontend/src/pages/Messages.tsx`
**Route**: `/messages` (registered in `frontend/src/config/routes.ts` — title "Message Center", the System nav group)
**Last Updated**: 2026-09-15

## Purpose

The **Message Center** — the system messaging queue rendered as a
collections-style table. The bus's `notify:*` payloads land in the
`messageStore` (the bridge); this page is where they are VIEWED,
filtered, and managed. The Exa surface lives on its own page
(`/exa`); this page is the queue alone.

## Key Features

- **The table** — the sortable columns (time / source / type /
  title / read; the header clicks toggle), the read-state dimming,
  the "new" badge on the unread rows.
- **The filter row** — the search (title/message), the type filter
  (info/success/warning/error), the source filter (the distinct
  sources).
- **The bulk operations** — the checkbox select-all + the per-row
  boxes, "Delete N selected", the Mark-all-read + the Clear-all.
- **The view modal** — the row's View opens the full message: the
  record id (`msg-…`) and the bus event id (`event: eN`) in mono;
  the Copy carries both ids (the unambiguous message reference).
- The unread count in the header ("N unread · M total").
- **The header button group** — the `PageBanner` + the **Exa pill**
  (`ExaPromptFlyout`) + the `HelpButton` (context `messages`), on one
  `justify-between` row. The page passes `hideCommand` and seats the pill
  itself: inside that row the banner shrinks to its content, so a
  banner-seated pill would land beside the TITLE at the page's left edge,
  where its leftward-opening 440px panel runs under the nav panel.

## Components Used

- `useMessageStore` (the queue), the `selectUnreadCount` selector.
- The route/nav: `frontend/src/config/routes.ts` + the App's System group.

## The Entry Points

- The **dashboard card** (`MessagePreviewCard`) — the recent 5 +
  the unread count + "View all" → the page.
- The **chat top-row indicator** — the bell + the count badge
  (ChatInterface) → the page.
- The **nav** — the System group's Messages item.

## Related

- The message store: `frontend/src/stores/messageStore.ts` (persisted).
- The bridge: `frontend/src/hooks/useNotifyBridge.ts` (the bus → the store).
- The roadmap: `local/message-center/` (the study + the phases).
