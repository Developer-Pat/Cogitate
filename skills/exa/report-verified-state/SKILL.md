---
name: report-verified-state
description: "The claimed/verified discipline: always report the CHECKED state, not intent. Use in EVERY operation report — say what was claimed, then what was verified."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, honesty, verification, reporting]
---

# Report Verified State

Every operation report carries BOTH sides: the claim and the
checked truth. This is the honesty loop made behavioral.

## The pattern

```
Claimed: <what the operation intended / what you believed>
Verified: <what the system actually shows — read back, checked>
```

## The rules

1. **Never report "done" without a check.** The check is a read-
   back (the API, the DB, the health endpoint) — not your
   assumption.
2. **Never paper over a mismatch.** If the verified state differs
   from the claim, say so LOUDLY — a mismatch is a finding, not
   an embarrassment.
3. **Distinguish the two senses.** "The backend is up" means the
   health check returned 200 — not "the process exists" and not
   "I believe it's up."
4. **When you don't know, say you don't know.** A confident guess
   is worse than an honest unknown.

## Common pitfalls

- Reporting intent as fact ("I restarted it" without the health
  check — the 2026-08-18 failure).
- Reporting a belief as the system state.
- Hiding a verification failure to look successful.
