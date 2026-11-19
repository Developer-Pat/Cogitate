---
name: verify-trigger-config
description: "Read back a workflow trigger's config from the DB — the verification half of any schedule change. Use after setting a cron to confirm the persisted value."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, triggers, verify, read-back]
---

# Verify a Trigger's Config

The verification half of schedule changes: read the DB truth back
and compare against what was claimed.

## The read-back

`GET /api/v1/triggers/{trigger_id}` — the response's `config.cron`
is the persisted value. Or call the tool `verify-trigger-config`
with `{trigger_id}`.

## The discipline

1. After ANY schedule change, read back + compare.
2. Report BOTH sides: what was claimed, what the DB shows.
3. If they differ, the change FAILED — say so loudly (the
   claimed/verified pattern; never paper over a mismatch).

## Common pitfalls

- Reporting the cron you INTENDED instead of the cron that
  PERSISTED.
- Confusing the trigger id with the workflow id (the trigger id
  is the `monitor-*` handle; the workflow id is `rss-monitor`).
