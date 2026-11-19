---
title: LLM Fallback Chains
type: atlas-devnote
category: lessons-learned
order: 4
confidence: high
updated: 2026-09-10
tags: [type/dev-notes, domain/lessons-learned, domain/llm, domain/workflows]
---

# LLM Fallback Chains

When one call can be served by more than one model, the chain is the
feature — and the chain is also where runs quietly lose their meaning.

## The rules

1. **Treat a free route as an availability lottery, never a fixture.**
   Free model slugs change without notice; a model can go paid-only
   between runs and the failure arrives as a 404 at call time. A chain
   may START on a free route; it must not DEPEND on one.
2. **Return the provenance — do not only log it.** Every call reports
   which step answered (`served_by`) plus the attempt history. One run
   can serve batch 1 from a free route and batch 2 from a local model —
   different quality, same manifest — and only the provenance makes that
   auditable after the fact.
3. **All-steps-failed must RAISE.** A silent empty return is
   indistinguishable from a legitimately empty result. The caller owns
   its degraded path (a mechanical fallback, a retry, a human); the
   chain owns the truth. Same class as the worker-verdict bug: the
   manifest looked perfect while the LLM never fired.
4. **"A client was built" is not "the model answered".** A readiness
   flag derived from constructing a client proves nothing; only the
   call's own result does. Derive the flag from the answer.
5. **Bound every attempt with a timeout.** A flaky route can hang rather
   than fail; an unbounded attempt stalls the whole batch. Time out,
   then move to the next step.
6. **Do not prejudge the fallback's quality.** A heavily quantized local
   model extracted structured tags correctly, at usable speed, on the
   same task where a free route returned 404. Test the fallback; never
   assume it is the weak link.

## Why it matters

A chain exists for resilience. Without provenance and a loud all-failed
path it delivers the opposite: runs that silently mix models of
different quality, or that emit empty results indistinguishable from
real ones — precisely the failure the chain was built to prevent. The
pseudo-agent spec (`app/domain/pseudo_agents/`) is the implementation of
these rules.

## Related

- [[dev-notes/known-issues|Known Issues]] — the worker-verdict class
  (a manifest that looked perfect while no model ever answered)
- [[atlas/workflows/tag-survey-fanout|The Tag-Survey Fan-Out]] — the
  first consumer: the worker + boss specs
