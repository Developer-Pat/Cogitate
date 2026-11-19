---
title: The Research-Framework Identity
type: devnote
path: wiki/dev-notes/design/research-framework.md
confidence: high
updated: 2026-08-17
tags: [type/dev-notes, domain/design]
---

# The Research-Framework Identity

Cogitate's purpose is as a RESEARCH FRAMEWORK for a specific
question: **how do we combine LLMs of different capabilities into
coherent, dependable workflows?**

The working hypothesis (the factoring hypothesis): smaller/local
LLMs appear incompetent at "trivial" tasks because the tasks are
actually multi-step with hidden state and no verification — and a
workflow can supply the missing machinery. Skills provide the
"how"; workflows provide the "when/if/verify." The testable claim:
a workflow turns a small model's failures into bounded, verifiable
outcomes.

The demo direction this points at: a LOCAL model doing the grunt work while a
cloud model orchestrates — the arrangement the hypothesis says should beat either
alone. The release documentation states this as Cogitate's purpose.

**Deferred**: the agent-shipping decision (QA Phase A) is informed
by this — ship the harness + proven demos, not a test roster.
