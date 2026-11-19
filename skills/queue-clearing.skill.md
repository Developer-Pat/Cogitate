---
name: queue-clearing
description: >
  Process the system-functions queue (the Exa inbox): read the
  reports, judge whether the user needs a toast, and keep the
  queue clean. Expand as Exa's system tasks grow.
---

# Queue Clearing (Exa's system-functions queue)

The **inbox** (`.exa-workspace/inbox/`) is the GENERAL landing spot
for the system functions — the sweep reports today, more kinds as
the system grows.

## The queue's contents

- **Log sweep reports** — `log-sweep-<stamp>.md` (the warnings +
  errors + floods the log sweep found; written by the sweep's runs).

## The clearing flow

1. **Read** each report in the inbox.
2. **Judge** — does this need the user's attention?
   - NEEDS ATTENTION: errors, floods, or anything that requires a
     human decision (the toast: a concise message naming the count
     + the report).
   - CLEAN / routine: NO toast — the user must not be pinged for
     every routine run (the 'no constant messages' rule).
3. **Move** the processed reports to `system-reports/`
   (`.exa-workspace/system-reports/`) so the queue stays current
   and the history accumulates.
4. **Toast** (only when appropriate) — the bus notify: a short,
   specific message ("the log sweep found 5 errors — the report is
   in System reports").

## The rules

- **Never message constantly** — the toast fires only when the
  report needs attention.
- The processed reports go to `system-reports/` — the queue is
  read + cleared, not deleted.
- **Expand as the tasks grow** — new report kinds join the queue
  with their own processing notes here.
