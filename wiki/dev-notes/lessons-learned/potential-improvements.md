---
title: Potential Improvements
type: atlas-devnote
category: lessons-learned
order: 2
confidence: medium
updated: 2026-08-06
tags: [type/dev-notes, domain/lessons-learned]
---

# Potential Improvements

Design / architectural gaps surfaced during the mypy cleanup and the
docs migration. Not an action plan — a "if we ever touch this, here's
what to fix" list. Each item notes the symptom that revealed it.

## 1. Memory manager factory should be explicit

**Symptom:** the chat router monkey-patches `_db_path`/`_is_deep`/
`_init_db()` on whatever manager the registry returns; the base class
had to grow stubs to match.

**Gap:** the registry returns the *base* type, but callers need
*concrete* behavior (per-agent DB path, deep-agent flag, summarization
settings). The base class is forced to either declare attrs it can't
fulfill (current fix) or lie.

**Ideal:** a `create_memory_manager(name, *, db_path, is_deep,
summarization...)` factory that constructs the right concrete manager
with its settings, so callers never touch internals. The registry
pattern works; the *construction* is the weak spot.

## 2. `ProviderConfig` now carries the model dimension

**Where it stands:** `ProviderConfig.default_model` is a property over the row's own
`config["default_model"]` — the same key `capabilities._model_from_config` reads off the ORM row, so
"the model this row serves" has ONE spelling. `Settings.default_llm_provider` /
`Settings.default_llm_model` are empty and nothing reads them: the split this section used to
describe (provider rows vs settings) is closed, and `run_post`'s checks read the model off the row
they already read rather than off settings.

**Still open, and worth reading before the next surface assumes otherwise:** `run_post`'s two checks
report under a `SystemManagerConfig` label while actually reading the DEFAULT PROVIDER ROW — the
label is wrong, not the read. The capability read-out that would replace those checks is the
service-capability arc's register item #8.

## 3. Two services, one file, similar names

**Symptom:** `config_service.py` holds both `ProviderConfigService`
(provider CRUD + keys) and `DefaultProviderService` (default provider).
Callers confused them (`get_default_provider` was called on the wrong
one).

**Gap:** service boundaries blur when two services share a file with
overlapping names. The default-provider logic is small enough to be a
method on the config service, or the default service should be in its
own module with a distinct name (e.g. `default_provider_service.py`).

## 4. Base-class methods that assume concrete internals

**Symptom:** base `MemoryManager.extract_facts`/`recall_facts` called
`self._get_conn()` which only concrete managers had; Default/Noop
inherited broken behavior silently.

**Gap:** the base class defines *data-access* methods (as defaults)
while the interface contract (ABC) doesn't declare them. Either:
- make them abstract so implementors must provide them, or
- make the base truly in-memory (no DB calls) and let DB-backed
  managers override the whole path.

The current fix (base stubs raising NotImplementedError) is the
minimal honest version; making them abstract would be stronger.

## 5. Optional propagation through the stack

**Symptom:** ~25 errors were `str | None` passed where `str` was
demanded — API-key lookups, dict `.get()` results, attribute access
on ORM objects.

**Gap:** no consistent boundary-narrowing convention. Some places
guard, some assert, some pass Optional through until a type-check
fails. The codebase would benefit from a stated convention:
narrow at the edge (API layer / fetch point), never propagate
Optional into domain logic.

## 6. Bare-except swallowing (behavioral, not typing)

**Symptom:** 3 real bugs invisible for months (see mypy page).

**Gap:** the codebase's "best-effort" blocks eat exceptions silently.
A code-wide convention: every `except: pass` should either log or be
justified in a comment. A grep gate for `except Exception:\s*pass`
(without logging) would catch regressions. **This is the highest-value
improvement on this list** — the others are architecture; this one is
prevention.

## 7. Deprecation needs a zero-refs gate (already adopted)

**Symptom:** `system_modes` phantom survived the modes
removal (both were REMOVED in the 2026-08 deprecation cleanup) because
removal sweeps were grep-based and missed undefined names.

**Gap:** the team already adopted the "zero refs" policy for removed
systems (verified). The additional lesson: *type checkers catch
what grep misses* (undefined names, dead imports). Deprecations
should end with a mypy run, not just a grep.

## 8. RAG ingestion paths were stale until the docs removal

**Symptom:** `rag/schemas.py` ingestion_dirs pointed at
`docs/atlas`, `docs/dev_notes` — both removed this session; now
re-pointed at `wiki/entities` + `wiki/dev-notes`.

**Gap:** config lists of file paths drift silently (no validation that
dirs exist). A startup check (warn if an ingestion dir is missing)
would surface the next time a path goes stale. The
`generate_factsheet_metrics.py` script has the same class of issue
(stale metric rows).

## Non-goals (explicitly NOT in scope)

- Rewriting the registry pattern — it held up (see mypy page).
- Rewriting the cognitive pipeline — layered well; errors were in
  glue code.
- Frontend typing — separate concern (tsc clean); not examined here.
