---
name: self-state-maintenance
description: "How to maintain your own stored state — the workspace state.json (facts + sources) is the ONE copy; keep it current with the update-state and update-sources tools."
version: 1.0.0
tags: [self-state, workspace, maintenance]
---

# Self-State Maintenance

You keep a personal state file in your workspace (`state.json`). It is
the ONE copy of your facts + sources — the system prompt reflects it
every turn. There is no other store.

## The rules

1. **User tells you a fact (your location, timezone, …)** → STORE it
   with the `update-state` tool (key: `location`, value: what they
   said, source: `user`). Confirm the read-back matches.
2. **You discover a fact yourself** (an online IP check shows where
   you are) → STORE it with `update-state`, source: `ip-geolocation`
   (or whatever method you used). The source-of-truth note is what
   makes the fact trustworthy later.
3. **Never claim a stored fact you did not write** — if the YOUR
   STORED STATE block does not show it, you do not have it stored.
4. **Your curated sources change** (a beat outlet dies, a new one
   matters) → `update-sources` add/remove. URLs only (`scheme://host`).
   Always verify the returned list.
5. **Your locus**: your location determines your local time and what
   counts as local news — keep it accurate.

## The check-IP flow (self-updating your location)

- When the user asks you to update your location (or you suspect it
  changed): SEARCH the web for your current public IP + its
  geolocation (your search tools are the read path — no new grant
  needed). Then store what you found:
  `update-state key=location value=<city, state from the lookup> source=ip-geolocation`
- If the search is thin or the geolocation is unclear, say so plainly
  and keep the last stored value — never guess a location.

## Why it matters

- The state block in your prompt is built FROM this file — updating
  it changes how you present yourself next turn.
- It lives in YOUR folder: it travels with you (export/backup), never
  in the central database.
