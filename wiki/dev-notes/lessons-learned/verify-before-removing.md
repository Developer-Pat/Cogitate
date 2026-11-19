---
title: Verify Before Removing
type: atlas-devnote
category: lessons-learned
order: 5
confidence: high
updated: 2026-09-10
tags: [type/dev-notes, domain/lessons-learned, domain/refactoring]
---

# Verify Before Removing

Deletion is cheap and irreversible; the audit that prevents a bad one
costs minutes of reading. Every rule below is a case where the cheap
audit found the premise false.

## The rules

1. **A name in the code is not a reference.** A workflow that named an
   agent in its headers and comments was in fact model-based — the agent
   row it "needed" was a vestige owning nothing but an empty workspace.
   Trace the actual call before believing the name.
2. **Grep by BASENAME, never by the canonical path.** Importers reference
   a file relatively (`./x`, `../dir/x`), so grepping its full
   repository path can return zero and read as "dead". Confirm with the
   basename before concluding anything has no consumers.
3. **Churn counts history, not liveness.** The busiest file in the git
   log can be a feature that no longer exists. Cross-read churn against
   the current tree before treating a file as a hot spot — or as
   evidence of a duplicate.
4. **Same-purpose stems across packages are not duplicates.** A stem
   match can be two different modules in two different packages. Read
   both before merging, renaming, or deleting either.
5. **A deletion's own report is not verification.** A hard-delete that
   returns `{"deleted": true}` proves the row went; it does not prove the
   premise held. Verify the premise first, the outcome second.

## Why it matters

Removals are the highest-leverage edits and the least forgiving: a wrong
one fails silently in a place nobody is looking. The audit is always
reading — cheap, fast, and it is the only thing standing between a tidy
cleanup and an instability nobody can trace.

## Related

- [[dev-notes/lessons-learned/llm-fallback-chains|LLM Fallback Chains]]
  — the model-vs-agent distinction, from the consumer side
- [[dev-notes/known-issues|Known Issues]] — where the bug-fix records live
