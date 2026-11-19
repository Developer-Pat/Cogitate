---
title: Dev Notes — Deep Dives
type: atlas-index
path: wiki/dev-notes/deep-dives
confidence: stub
updated: 2026-09-24
tags: [type/index, domain/deep-dives]
---

# Deep Dives — Dev Notes

Long-form expository accounts of one ARC: the problem it started from, the decisions taken
and the options weighed, what was built, how it was tested, and what the build learned.
One page per arc.

## Where this sits

Four surfaces, four jobs. A subject that fits two belongs in one, with a link from the
other.

| Surface | What it holds |
|---|---|
| **Deep Dives** (here) | one ARC, long form: the narrative, the decisions, the reasoning, and why the numbers are what they are |
| The rest of Dev Notes (`wiki/dev-notes/`) | the CURRENT STATE of a component or a policy — no history |
| Lessons Learned | the gotcha register: the rule, not the story behind it |
| `wiki/atlas/ui/` (the UI Atlas) | widgets and components |

A deep dive is the one place where a rejected option and a reversed claim are recorded as
such. It is not a change log (git holds that) and not a status report (the session files
hold those) — it is what a reader needs a year later to understand why the system is shaped
this way.

**It carries no development-process artifacts.** No commit SHAs, no session numbers or ids,
no `local/` paths, and no internal citation handles: the reader is a developer who was not
there and does not have this repository's history. Cite what they can open or run — the file,
the endpoint, the page, the log line, the test — and the measured numbers. The test for a
sentence: *would it still be true and useful to someone with no access to this repo's history?*

## Pages

- [[dev-notes/deep-dives/capability-layer|The Capability Layer]] — how the app decides which
  service answers a call: one resolver, a ladder, a chain whose every failure is logged, and no
  service named in code except one whose reason is written where it lives.
- [[dev-notes/deep-dives/token-limit-policy|The Token-Limit Policy]] — how a turn's budget is
  decided, spent and reported: one resolver, one limit model, a vocabulary for what a turn
  crossed, and the plug that keeps the work.
- [[dev-notes/deep-dives/the-workflow-run|The Workflow Run]] — how an execution's outcome is
  decided, graded, reclaimed and observed: a swallowed failure is a disagreement rather than a
  silence, a grade is declared where the catch is, the history reclaims itself on its own clocks,
  and one derivable id names a run's record, its spans and its traces alike.
- [[dev-notes/deep-dives/the-workflow-subsystem|The Workflow Subsystem]] — the layer above the run:
  ten code-defined kinds resolving to thirty-six declared templates through a visible ladder, the
  cast and the chains that answer *which model served this*, the monitor family that proved the
  shape, three ways to start a workflow without a person, and the channels that carry a product out.
