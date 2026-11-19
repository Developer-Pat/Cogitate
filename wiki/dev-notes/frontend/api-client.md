---
title: The ONE apiClient (the _34 consolidation)
type: dev-note
category: dev-notes
order: 99
confidence: high
created: 2026-09-04
updated: 2026-09-04
tags: [type/dev-notes, domain/frontend]
---

# The ONE apiClient (the _34 consolidation, 2026-09-04)

> WHAT IS (current-state): there is ONE api client —
> `frontend/src/services/apiClient.ts` — the file ~51 consumers +
> the domains services import. The duplicate
> `domains/shared/apiClient.ts` was DELETED (its machinery ported
> in). Verified live: the outage probe (backend kill -> the
> message-center entry at the 3rd consecutive failure -> the
> recovery toast on the restart).

## The client's machinery (all in apiClient.ts)

- THE CLEAN JOIN (the 2026-08-29 '//'-bug fix) — no relative-base
  pitfalls; the params builder appends onto the joined URL with
  the right '?'/'&' separator.
- Retries (3, exp backoff) + the 10s timeout + the 401
  clearAuth/redirect + the 429 Retry-After wait.
- THE RETURN CONTRACT: `{data}|{error}` — failures are RETURNED,
  never thrown (the 51 callers were written against that shape).
- THE OUTAGE TRACKER (ported 2026-09-04): consecutive-failure
  counting — the toast fires at the 3rd CONSECUTIVE failure (the
  flood threshold; the first two track silently) or every 5th,
  rate-limited to one per 10s; the RECOVERY toast fires on the
  first success after a 3+ streak (same rate limit — a recovery
  seconds after the down-toast is redundant).
- THE PARAMS SUPPORT (the real one): `params: { hard: true }`
  finally reaches the URL — ProfileService's hard-delete flag
  used to be silently dropped (hard deletes were soft deletes).
- THE FINAL-ERROR LOG: the all-retries-failed path logs through
  the funnel. The per-attempt debug lines were NOT ported (the
  92MB-log flood source).
- THE STREAM'S SIGNAL COMBINING: `stream()` merges the internal
  timeout controller with the caller's signal via `AbortSignal.any`
  (the listener fallback when unsupported). The old Proxy-over-
  EventTarget fake failed the browser's WebIDL brand check
  ('signal member of RequestInit does not implement interface
  AbortSignal') — every abortable chat stream crashed at fetch()
  time. A fetch() signal must be a GENUINE AbortSignal.
- THE ABORT POLICY: an external AbortError — the caller's own
  signal (page navigation, unmount) — returns EARLY: no streak
  increment, no error log. Only a genuine self-timeout (the
  client's own 10s abort) counts once and logs once. Navigation
  churn can never trip the tracker into a false 'Backend
  Unavailable'.
- THE TELEMETRY OPT-OUT: `RequestOptions.excludeFromOutageTracking`
  — the frontend log flush (logsService, 2s→5s timeout) opts out
  entirely: a dropped log can never count as a backend-down
  signal. Telemetry stays out of the outage math.
- THE OUTAGE-EPISODE GATE (2026-09-04): the client's
  down/recovery announcements consult `services/outageGate.ts` —
  the FIRST down-detector of an outage episode announces, the
  first recovery-detector closes it, and the other notifiers (the
  BackendStatusIndicator + the useSystemHealth hook — both gated
  too) stay silent until the next episode. The center stays the
  RECORD (no store-level dedupe — the Bob-errors dig); the
  collapse is at the notifier edge. One announcement per page
  context per episode (live-proven: 3-4 entries collapsed to 1).

## THE BUS EDGE (the cycle doctrine)

The client sits at the BOTTOM of the logging + notification
stacks (frontendLoggingService -> logsService -> apiClient;
notificationStore -> notificationConfigStore ->
notificationConfigService -> apiClient). It can NEVER import
either stack:
- a STATIC import closes a cycle (the 2026-09-03 app-killer);
- a DYNAMIC import raced the vitest module registry across
  test-file transitions (the full-suite hang, 2026-09-04).
THE FIX: `services/notifyBus.ts` — a leaf module (imports
NOTHING) that the client imports statically; the real handlers
(the notification store + the logging funnel) register ONCE at
the boot (`main.tsx`), after the module graph is loaded. Before
registration (and in tests) the bus no-ops — a failure is never
amplified.

## The test seam

`src/services/__tests__/apiClient.test.ts` — fresh
`EnhancedApiClient` instances per test (the singleton's streak +
rate-limit state must not leak) + spy handlers registered on the
bus: the 3rd-failure threshold, the streak reset, the recovery +
shared rate limit (fake clock), the params URL/merge/skip cases,
the final-error log (fake timers over the retry backoff).
