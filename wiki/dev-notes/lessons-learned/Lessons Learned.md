---
title: Lessons Learned
type: atlas-index
path: wiki/dev-notes/lessons-learned
confidence: medium
updated: 2026-09-17
tags: [type/index, domain/lessons-learned]
---

# Lessons Learned

Hard-won lessons from real incidents and cleanup work — patterns to
avoid, habits that bite, and how the team keeps this codebase honest.

## Pages

- [[dev-notes/lessons-learned/llm-fallback-chains|LLM Fallback Chains]] —
  availability lotteries, provenance, and why a silent empty result is
  the worst failure mode
- [[dev-notes/lessons-learned/verify-before-removing|Verify Before
  Removing]] — the audits that stop a wrong deletion (names are not
  references; grep by basename; churn is history, not liveness)
- [[dev-notes/lessons-learned/running-a-workflow|Running a Workflow]] —
  the operational rules: the two-shape state, merging the outputs
  channel, error paths that must not raise, and why the first run is
  bounded
- [[dev-notes/lessons-learned/mypy-backlog|Mypy Backlog: 70→0]] —
  what the type-checking cleanup revealed about codebase habits
- [[dev-notes/lessons-learned/potential-improvements|Potential
  Improvements]] — design/architectural gaps found along the way
- [[dev-notes/lessons-learned/destructive-test-discipline|Destructive-
  Test Discipline]] — capture-before-restore, prefer non-destructive
  verification (the keys-tab incident)
- [[dev-notes/lessons-learned/checkable-claims|Checkable Claims]] —
  a claim that nothing checks drifts, and looks correct while it does
- [[dev-notes/lessons-learned/optimization-discipline|Optimization
  Discipline]] — measure before changing anything, a library's default
  configuration is often the slow one, and check whether the problem is
  already solved elsewhere before inventing a technique

## Reading order

The rule pages first — they are the current, enforceable
conventions. The mypy page is concrete and the improvements page is the
"if we ever touch this, here's what to fix" list.
