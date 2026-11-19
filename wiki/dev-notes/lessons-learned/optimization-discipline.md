---
title: Optimization Discipline
type: atlas-devnote
category: lessons-learned
order: 11
confidence: high
updated: 2026-09-17
tags: [type/dev-notes, domain/lessons]
---

# Optimization Discipline

## The rules

1. **Measure the cost before choosing what to change.** Name the actual expense and its
   share, or the work is aimed at a guess. In one investigation the suspects were the SSE
   pipeline, the CSS, the message chrome and the message-history size; measured, they came
   to roughly **32 ms total, 1.1%, 3% and ~1%**. The cost was re-rendering a growing
   document — about **97%** of the problem.

2. **A library's default configuration is often the slow one — check the build and the
   options before optimising your own code.** The same work on the framework's production
   build cost a fraction: blocked main-thread time **3480 ms → 233 ms**, long tasks
   **41 → 2**, on a *longer* answer doing *more* updates. `jsxDEV` alone was **39.6%** of
   non-idle time, and the development build double-renders. Our own components accounted
   for ~2.8%. **Hand-optimising what the toolchain already provides is the expensive
   path.** A development build is not a neutral baseline — it is a deliberately
   instrumented one, and it makes the toolchain's overhead look like the application's.

3. **Before inventing a technique, check whether the problem is already solved.** A common
   library is a solved problem before it is yours. The block-wise memoized markdown
   renderer built here is described verbatim in the ecosystem's own cookbook and measured
   at "typically 2-10x faster" elsewhere — independent confirmation, a design to compare
   against, and something to cite.

4. **Optimise the render, not the delivery.** A stream arrives in hundreds of small events.
   The transport is cheap; re-rendering the accumulated result is not. What makes the
   difference is a memo keyed on a stable per-block string, so finished work is skipped.

5. **State what a change bought in the same unit you measured before.** A claim without a
   before-and-after in one unit is not a result.

## Why it matters

The failure this prevents is spending the effort in the wrong place and then concluding the
problem was hard. With a wrong target every fix looks reasonable and none of them move the
number — and the natural next step is to believe the system is inherently slow, when the
lever was one setting away.

The two traps compound, because a development build is the default for local work and so
becomes the yardstick. **Measure the shipped configuration — or say plainly that you
measured a development one.**

## Related

- [[dev-notes/lessons-learned/checkable-claims|Checkable Claims]] — name the check that would falsify it, and derive the numbers you feed it
- [[dev-notes/frontend/streaming-render|The Streaming Render]] — the technique these rules produced
- [[dev-notes/lessons-learned/Lessons Learned|Lessons Learned]] — the index
