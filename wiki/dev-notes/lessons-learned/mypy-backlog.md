---
title: Mypy Backlog (70 → 0)
type: atlas-devnote
category: lessons-learned
order: 1
confidence: high
updated: 2026-08-06
tags: [type/dev-notes, domain/lessons-learned]
---

# Mypy Backlog: 70 → 0

The 66-error mypy backlog (issues.md, pre-existing for months) was
closed 2026-08-06. The cleanup surfaced **4 real runtime bugs** that
tests had not caught, and exposed the codebase's habits. Roadmap:
`local/roadmaps/mypy-fix-roadmap.md`.

## What the errors revealed

### 1. Bare `except Exception: pass` is a bug factory

The most damaging pattern. Three real bugs were invisible for months
because of it:

- **`memory_manager.py` `extract_facts`** — undefined `facts_key`
  → `NameError` → swallowed → fact extraction silently never worked
  (the KV-store override was correct; the base-class variant was broken
  for Default/Noop managers)
- **`pipeline.py` vector recall** — `self.vector_stores` never
  initialized → `AttributeError` → swallowed → vector memory was
  always a no-op
- **`dispatcher.py`** — `time` not imported → `NameError` → swallowed
  in a try block

> Rule: "optional / best-effort" code wrapped in `try/except: pass`
> turns real bugs into silent feature loss. The system appears to work;
> features quietly don't. Log the exception at minimum (or use
> `except Exception as e: logger.warning(...)`).

### 2. ABC contracts must be honest

`MemoryManager` (base class) declared `extract_facts`/`recall_facts`
that call `self._get_conn()` — but `_get_conn` only exists on
`KVStoreMemoryManager`. Default/Noop managers inherited broken
implementations. An abstract class must define its full contract
(declare the methods it calls, even as `NotImplementedError` stubs),
or concrete internals leak up.

### 3. Concrete-class leakage into callers

The chat router monkey-patched `_db_path`, `_is_deep`, `_init_db()`
onto whatever manager the registry returned — it *knows* the concrete
class. The router should work against the base contract, or the
registry should hand back the right type. (Fixed by adding base-class
attrs + a Noop fallback; a cleaner fix would be an explicit factory.)

### 4. Liskov violations in overrides

`response_formatter.py`: the base declared `-> str`; two overrides
returned `tuple[str, ComponentTrace]` with narrowed required params.
The runner expected `str`. If that tuple had been consumed as-is,
structured output would have broken at runtime. The interface was
never enforced — mypy caught it.

### 5. Service-boundary confusion

`run_post` called `ProviderConfigService.get_default_provider` — but
that method lives on `DefaultProviderService` (two similar-named
services in one file). And `ProviderConfig` has no `model` field, yet
callers assumed one. Overlapping service names/responsibilities → wrong
guesses.

## Habits the errors exposed

| Habit | Evidence | Fix |
|---|---|---|
| Optional flows too far | `str \| None` passed where `str` demanded (~25 errors) | Narrow at boundaries with guards/asserts |
| Variable reuse across types | `stmt`/`result`/`profile` reassigned to different query types | Distinct names (also more readable) |
| Dead scaffolding survives deprecation | `system_modes` phantom — 2 tools referenced a `modes.py` that never existed | Zero-refs sweep after removal; type checkers catch what grep misses |
| Lazy imports never written | "Lazy import to avoid circular deps" comments with no import behind them | Write the import or delete the comment |
| SQLAlchemy API misuse | `Result.rowcount` on generic `Result` (it's on `CursorResult`) | Check the actual return type |

## What held up

The layering (API → domain → infra), the registry pattern
(ABC → Registry → factory), and the pydantic/ORM boundaries were all
**sound** — errors clustered in hand-written service logic and glue
code, not the architecture.

## Meta-lesson

mypy is a *bug finder*, not a style checker — 4 real runtime bugs
that tests didn't catch. The sweep's mypy gate is the right
investment; keep it green.
