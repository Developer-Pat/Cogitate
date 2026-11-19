---
title: Messages
category: messages
subtopic: Overview
order: 1
confidence: high
created: 2026-08-25
tags: [domain/help]
---

# Message Center

The **Message Center** is where the system's messages land — the
notifications from the sweeps, the Exa queue clearing, and the
other system events. The toasts are the instant nudge; this page
is the record you can return to.

## What you'll see

- **The table** — each message: the title, the type (info /
  success / warning / error), the time it arrived, the source
  (who sent it — e.g. `exa` or `system`), and a **View** badge
  that opens the full message. Read rows are dimmed; unread rows
  are bright — the read state also drives the header's unread
  count.
- **The header** — the banner and the Help button only. Below it:
  the **Messaging Test Center** expander (the test tools, collapsed
  by default) and the **table-controls row** — the search, the
  type filter, the source filter, the time-range filter, the count
  badges ("N unread" + the total), and the table actions: **Mark
  all read** and **Clear all**.

## Filtering and sorting

- Click a column header to sort (Title, Type, Time, Source, Read —
  click again to reverse).
- Use the search box to find text in the titles or messages.
- Use the **Type** and **Source** dropdowns to narrow the list.
- Use the **time-range** dropdown (5 minutes / 20 minutes /
  hour / 6 hours / day) to narrow the list to recent messages —
  the table only shows messages inside the selected window.
- Use the **read-state** dropdown (All states / Unread / Read) to
  narrow to the messages you haven't read yet — the catch-up
  view.

## Managing the messages

- Tick the checkboxes to select rows (or the top checkbox to
  select all the filtered rows), then **Delete N selected**.
- The messages persist across page reloads (stored in your
  browser).

## Testing the message center

The **Messaging Test Center** expander under the header carries
the test affordances:

- **Full Test** — the thorough verification: it sends a *Starting
  message center test* warning, then one message of each type
  (info / success / warning / error) about 1.5s apart, and checks
  that every one actually ARRIVES in the center. If all arrive it
  reports a green **PASSED**; otherwise a red **FAILED** naming
  the missing types. Every step is logged to the Logs page (source
  `message-center-test`) with its round-trip time. The result
  panel inside the expander shows a ✓/✗ chip per type as they
  land.
- **Single message** (its type picker sits after the button) — one
  message of the type you pick; the picker defaults to *warning*
  after every page reload. The little echo next to it confirms the
  round-trip.

**Which one?** — the **Single message** button is the quick smoke
check: send one message, watch it land, done. Use the **Full Test**
when you suspect the center is missing messages or after anything
in the messaging pipeline changes — it verifies every type with an
arrival check and gives you a verdict.

Notes:

- **Keep the tab visible while a test runs.** A hidden/background
  tab's event stream is throttled by the browser and deliveries
  can stall — the test would report misses that aren't real. The
  arrival windows now count only visible time, and the test warns
  you if it starts hidden.
- **The chips verify the store, not the table.** A message can be
  delivered (green chip) while the table's type/search filters
  hide it from view — the panel says so when that happens. If a
  test run looks empty, clear the type filter and the search.
- **After a page reload the event stream takes a moment to
  re-establish.** Starting the test immediately after a reload can
  miss the first messages; wait a second or two, or just re-run.
- Each test message carries a short run tag (e.g. `fkt2u`) so the
  center records stay unique and correlate with the Logs-page
  entries. The same event delivered twice (e.g. by several open
  tabs) records only once — the center dedupes by the event id.

## Getting here

- The **Messages** item in the System menu.
- The **bell + count** icon on the chat page (the number is the
  unread count).
- The **Messages card** on the dashboard ("View all").
