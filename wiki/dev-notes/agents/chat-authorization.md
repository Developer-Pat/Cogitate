---
title: Chat Authorization — the permission bridge
type: atlas-devnote
category: agents
order: 4
confidence: high
updated: 2026-08-21
tags: []
---

# Chat Authorization — the permission bridge (2026-08-21)

> The third tier of the external agent's permission model. This
> page is the DESIGN — why the model is shaped this way, how the
> wire path works, and the properties that make it safe. It is
> NOT a patch note: the mechanism composes with the existing gate
> layers and uses the upstream protocol's native approval seam.

## The permission model (the design, complete)

The external agent (Exa) has exactly three permission tiers. They
are not ad-hoc toggles — each tier is a distinct value of the
ACP `edit_approval_policy` config option, and the tiers form a
ladder of increasing trust:

| Tier | `edit_approval_policy` | What Exa can write | When it applies |
|---|---|---|---|
| **Chat authorization** (default) | `ask` + the permission bridge | one edit at a time, user-approved in the chat | the granular tier — per-edit, in-context |
| **Fix mode** | `workspace_session` | everything inside the ACP cwd | the scoped grant — the selector's middle tier |
| **YOLO** (2026-08-21) | `session` | everything — the secret-path guard (.env/.ssh/.git) still asks | the broad grant — the selector's top tier; the chat Stop bounds the runaway risk |

The old **read-only** tier (no handler → every `ask` edit timed out
→ denied) is GONE as a spawn state: since 2026-08-21 the write
tools are AVAILABLE in every tier (the per-edit card, the cwd
auto-approve, or the everything auto-approve is the gate — never a
tool-layer block). Read-only-ness for the consult surface is the
directive + the 60s-denial of an unapproved edit.

The tiers are deliberate: **granularity is the feature**. Before
2026-08-21 the model was binary (read-only vs fix-mode-everything)
— there was no way to say "yes to THIS file, nothing else." The
chat tier fills that gap without weakening either neighbor.

## Why it is NOT a kludge (the design argument)

The feature looks wired-on because the interactive seam already
existed *upstream* — the ACP protocol has a native
`session/request_permission` method, and Hermes' adapter
(`edit_approval.py:make_acp_edit_approval_requester`) uses it
whenever an edit is proposed under the `ask` policy: it builds a
`ToolCallUpdate` carrying the DIFF (`old_text`/`new_text`) plus
options (`allow_once` / `deny`) and waits up to 60s for the
client's decision.

Cogitate's `AcpClient` simply never answered — the `_read_loop`
handled `session/update` events but had no
`session/request_permission` handler, so every `ask` edit
timed out → denied. **The missing piece was the client half of
an existing protocol contract, not a new mechanism.**

That is the architectural argument: this is an *integration
point*, filled correctly, not a bolt-on. The diff-visible
approval UX is the protocol's design; Cogitate supplies the
user-facing half (the chat card) and the request-bound resolution.

## The wire path

```
Exa proposes an edit
  → Hermes adapter: session/request_permission
      (params: session_id, tool_call{title, content[diff]}, options[allow_once, deny])
  → AcpClient._read_loop: _handle_permission_request
      1. register the request future (BEFORE emitting — no race)
      2. emit the "approval" AcpEvent (diff + options) to the stream queue
      3. await the future (60s — matches the adapter's requester timeout)
  → WS router: forwards as {type: "approval_request", request: {...}}
  → CHAT: the Approve/Deny card renders (the diff visible)
  → user clicks Allow / Deny
  → WS: {type: "approval_response", request_id, option_id}
  → router: client.resolve_permission(request_id, option_id)
  → the future completes → the read loop replies over ACP
      (outcome: selected+option_id  |  cancelled)
  → the adapter's requester resolves → the edit applies (or not)
```

## The security properties (non-negotiable)

1. **Request-bound** — the response carries the request id; only
   the matching pending future resolves. Unknown/stale ids are
   dropped (`resolve_permission` returns False). A replayed or
   forged response cannot resolve a different request.
2. **User-only** — the approval card renders in the chat (the
   human's surface). There is no programmatic auto-approve path
   from the agent side; the resolution originates from a UI click.
3. **Diff-visible** — the user sees the exact old/new text before
   deciding. No blind "Exa wants to edit a file."
4. **Time-bounded** — 60s window, matching the adapter's
   requester timeout; an unanswered request resolves to
   `cancelled` (denied), never silently approved.
5. **Recorded** — every decision is written to the verification
   store (the honesty loop: operate → verify → record).

## Composition with the existing gate layers

Chat authorization is ONE layer of a defense-in-depth stack,
never the only guard:

| Layer | What it stops | Where |
|---|---|---|
| `strictTools` spawn gate | the dedicated write tools when read-only | `services.py:_session_new_params` |
| `edit_approval_policy` | write_file/patch per policy | the ACP `session/set_config_option` |
| **The permission bridge** (this) | per-edit, user-approved | the chat card |
| The prompt directive | behavioral steer | the WS router's mode directive |
| The watchable tool stream | post-hoc audit | the panel's tool_call events |

The bridge sits between "policy" (the config value) and "audit"
(the stream): it is the interactive decision point that the
policy defers to.

## The tier selector + the live-test findings (2026-08-21)

- **The 3-way selector** (`permission_tier: chat | fix | yolo`) on
  the Exa Agent page replaced the binary fix_mode bool. The tier is
  the field of truth; `fix_mode` is the DEPRECATED compat view
  (persisted JSON maps `fix_mode: true` → `fix`).
- **The stale-client trap** (live-found): `get_acp_client` is a
  singleton — a config PUT closed the subprocess but the singleton
  survived with the OLD tier, so the next spawn reused it (chat →
  `ask` policy even though the config said yolo — the card appeared
  under yolo). Fixed: a tier that differs from the live client's
  REBUILDS the client.
- **The missing import** (live-found): the stop-button build added
  `useState(false)` to useAgentInteraction.ts without importing
  `useState` — a ReferenceError that crashed the chat page at mount
  (masked by the error boundary). Fixed.
- **YOLO live-proven**: set yolo → Exa edited access_evidence.py
  with NO card (auto-approved, `session` policy) → reverted.
- The **grant bridge** issues the session grants for BOTH fix and
  yolo (the granularity is the ACP policy, not the grants).

## The Ox Alpha exercise findings (2026-08-21)

The live exercise (adding a curated provider + a shallow agent on
`stealth/ox-alpha`) surfaced FOUR defects, three of them in this
domain:

1. **The turn-2 greeting bug** (chat): the fast-executor filter
   kept the FIRST user message — turn 2 answered the session's
   opening message. Fixed: keep system + the LAST user message.
2. **The reasoning-model budget trap**: a small max_tokens is
   eaten by the model's THINKING phase → zero content → the
   'no_content' toaster. Generic fix: `reasoning_support.py`
   (16000 floor) across ALL executors + the streaming SSE path
   reads delta.reasoning too.
3. **The missing stop button**: the page never consumed
   exaStreaming/stopExaStream — no Stop rendered while Exa ran.
   The page now routes the stop Exa-aware.
4. **The crash-on-cancel freeze**: a cancel racing a
   naturally-ending turn crashed the ACP supervisor's background
   task; the stream ended with an exception but the halt logic
   kept the broken subprocess. The stream now flags
   `stream_crashed` and the halt closes (kills) the subprocess.

The lesson is GENERIC (Ox leaves Monday): reasoning-model support
is name-pattern + budget-floor + reasoning-field extraction, not
a curated list. See the program record
(`local/exa-expertise-implementation/16-ox-alpha-exercise.md`).

## Design decisions (recorded)

- **The 60s match** — the adapter's requester defaults to 60s; the
  bridge waits the same so the reply never lands after the adapter
  gave up. An unanswered card = denied, not stuck.
- **Single-flight** — one edit at a time per session; the adapter
  serializes, so the bridge is naturally one pending request.
- **The `image` config field** (2026-08-21, same arc) — Exa's
  chat face is a configurable asset path on the Exa Agent page;
  the chat participant renders it. No emojis — the face is an image.
- **Fix mode stays** — the broad grant is not weakened; chat
  authorization is the fine-grained alternative, not a replacement.

## Related

- [[dev-notes/agents/external-agent-domain|External Agent Domain]] — the ACP client + the fix-mode gate
- [[dev-notes/agents/agent-lifecycle|Agent Lifecycle]] — the recoverable-delete model (same no-surprises philosophy)
- [[dev-notes/design/honesty-loop|The Honesty Loop]] — the verification store every decision lands in
- [[atlas/api/routers/external-agent|External Agent API]] — the WS events
- [[help/chat|Chat help]] — the user-facing approval UX
