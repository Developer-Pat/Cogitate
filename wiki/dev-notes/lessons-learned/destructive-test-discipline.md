---
title: Destructive-Test Discipline
type: atlas-devnote
category: lessons-learned
order: 3
confidence: high
updated: 2026-08-14
tags: [type/dev-notes, domain/lessons-learned, domain/testing]
---

# Destructive-Test Discipline

**The incident (2026-08-05, keys-tab live test):** verifying a
throwaway provider key wrote the throwaway value BACK into `.env`
instead of restoring the original. The restore step did a
READ-AFTER-WRITE — it read the file after the test had already
overwritten it, so "restore" saved the test value. The original key
was gone; recovery required a backup.

## The rules

1. **Capture BEFORE, restore the capture.** Read the original value
   into memory FIRST, run the test, then write the CAPTURED value
   back. Never read the file as part of the restore — by then it
   holds the test value.
2. **Prefer non-destructive verification.** A temp env file (the
   way the unit tests do it) or a test endpoint beats touching the
   real `.env` at all. If an endpoint exists that tests a key
   without persisting it, use it.
3. **Destructive tests need a backup anyway.** DB backups are
   routine here (backup_db.py); env-file mutations deserve the
   same reflex — take the snapshot before, not after.
4. **Verify the restore.** After writing back, read the file and
   confirm the ORIGINAL value is present (the read-back is the
   check, not the source).

## Why it matters

`.env` is the one file whose corruption is silent and total: no
error at write time, just a broken provider at the next launch.
These rules are the live-test equivalent of "back up DBs
pre-change" — the cost is seconds, the failure mode is
credentials-lost-forever.

## Related

- [[dev-notes/known-issues|Known Issues]] — where the bug-fix
  records live (this is a process lesson, not a bug)
- [[dev-notes/configuration/configuration-surface|Configuration
  Surface]] — how config/keys are stored
