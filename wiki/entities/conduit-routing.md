---
title: Conduit Routing
type: atlas-entity
path: wiki/entities/conduit-routing.md
confidence: stub
updated: 2026-11-27
tags: [type/entity, domain/entities]
---

# Conduit Routing

How each message is processed: the conduit decides the processing
path per message — SHALLOW by default, HYBRID only when the
first pass is genuinely insufficient (short content or a
deep-keyword query). **No automatic delegation** — the user
explicitly picks when to hand off (chat_delegate).

## The conduit decision flow

`conduit_route()` (`backend/app/services/cognitive_pipeline/
conduit.py`) decides per message:

1. **SHALLOW (default)** — the tool loop's result IS the answer
   (the streaming tool loop runs until the model writes its final
   text; no second pass). This is the route for the vast majority
   of turns, including tool-using turns.
2. **HYBRID** — only when the agent's cognitive profile has
   `executor=hybrid` AND either the query matches deep keywords
   (analyze/explain/compare/why/how/…) or the first pass was cut
   at the output budget. Answer length is not a trigger: a short
   answer that answers is a complete answer.
   The deep pass then REPLACES the first-pass content (canonical
   executor semantics — the deep pass is prompted as "the
   previous answer was insufficient — provide a thorough
   response").
3. **No auto-delegation** — the user explicitly picks when to
   hand off (chat_delegate).

## The tools trigger

`tools_were_used` does not force HYBRID: in the streaming router the
tool loop already synthesizes the final answer, so a second pass
would duplicate the whole report (the DOUBLE-glitch, known-issues).
The deep pass fires only on short content or deep-keyword queries.

## Relationship to chat_delegate

- `chat_delegate` (chat router) = the explicit handoff endpoint
  (agent-to-agent message).
- The conduit is the *policy* layer: SHALLOW default, HYBRID
  only on genuine insufficiency, delegation only when the user
  invokes it.