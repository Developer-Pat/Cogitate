---
title: PromptHistoryList
type: atlas-component
path: frontend/src/components/features/agentInteraction/PromptHistoryList.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# PromptHistoryList

**Path**: `frontend/src/components/features/agentInteraction/PromptHistoryList.tsx`
**Last Updated**: 2026-09-17

## Purpose

The **History** tab's body: the user's own past prompts — **alphabetical and deduplicated** —
with copy-to-clipboard and copy-to-the-message-box per entry, an **inline per-entry delete**,
and a footer carrying the count and *Clear history*.

## Where the data comes from

The list reads [[atlas/ui/stores/promptHistoryStore]], which is **written on send**. It
deliberately does **not** derive from the active session's messages:

1. **A derived list cannot survive a tossed session.** `handleTossSession` calls
   `deleteSession` and `chat_messages.session_id` is `ondelete="CASCADE"` — the prompts
   are deleted from the database, not hidden, so no scope could show them again.
2. **A derived list is empty for any session not yet opened** — messages are lazily
   loaded and are not even present in the titles-only list payload.
3. **A derived list gives you nothing to delete.** Only something to hide, which is why
   it needs a dismissed-set that a real record does not.

## The three display tiers

A prompt has no natural length, so the display is tiered deliberately:

| Tier | Limit | Why |
|---|---|---|
| Row | `ROW_CHARS` = 60 | enough to recognise which prompt it is |
| Tooltip | `TIP_CHARS` = 500 | a few lines of the real text, via [[atlas/ui/components/ui/PortalTooltip]] |
| Beyond | the buttons | copy / copy-to-input is the escape hatch |

The third tier is the point: a tooltip holding a 4,000-character prompt is not readable
and cannot be kept in the viewport, so the tip stops at a sane length and **says how much
it is holding back**.

## Props Interface

```typescript
interface PromptHistoryListProps {
  /** Put the prompt INTO the composer — never sends it. Optional: with no handler the
      button is hidden rather than rendered dead. */
  onUsePrompt?: (text: string) => void
}
```

There are no data props — the list reads the store directly.

## Per-row controls

| Control | Tooltip | Action |
|---|---|---|
| Copy | `Copy to clipboard` | `navigator.clipboard` with an `execCommand` fallback |
| Copy to input | `Copy to user input` | `onUsePrompt(entry.text)` |
| Trash | `Remove from history` | removes that entry from this list |

**The delete is INLINE, not behind a ⋮.** The row used to hide it in a menu holding that one
item, on the argument that a destructive action should not sit one mis-click from Copy. It
is inline now because the menu charged a click for the row's only hidden action while the
delete is not in fact dangerous — it takes the entry from **this list** and leaves the
conversation alone, so nothing irreversible was ever one mis-click away. The real cost was a
hidden control, and a hidden control is the thing a reader cannot find.

## Delete semantics

Deleting removes the entry **from this list only**. Because the history is its own
record rather than a view of the conversation, this is now a real delete with no shadow
state — but the copy still states it, because a user tidying a sidebar should not have
to wonder whether the conversation changed underneath them.

## Empty states

- No prompts recorded: *"No prompts in the history yet."* + *"Prompts are recorded as you
  send them."* — the second line matters, because the history does not reach back into
  sessions, so someone looking for last week's prompts should learn that here.
- Everything deleted: *"Nothing left in this history."* — a different statement, because
  saying "no prompts yet" about a list the user just emptied would be false.

## Footer

`N prompts` plus **Clear history** behind a confirmation
(`<dialog className="modal">`, the project's DaisyUI v5 convention). The label is *Clear
history*, not *Clear all*: the message center has a *Clear all* and the collision caused
real confusion — see [[dev-notes/message-center|Message Center]] .

## Related

- [[atlas/ui/stores/promptHistoryStore]] — the data
- [[atlas/ui/components/features/agentInteraction/SessionManager]] — the tab strip and the host
- [[atlas/ui/components/ui/PortalTooltip]] — the tips
