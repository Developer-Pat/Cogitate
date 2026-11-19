---
title: Test Tiers
type: atlas-devnote
category: testing
order: 3
confidence: high
updated: 2026-09-13
tags: [type/dev-notes, domain/testing]
---

# Test Tiers

Tests are partitioned by **what they depend on**, order least-dependent first.
The order is also the diagnosis: a `pure` failure means the code is wrong; a
`external` failure says nothing about the code and can never mask a `db` breakage.

## The tiers

| Tier | Depends on | A failure means |
|---|---|---|
| `pure` | nothing — no DB, no filesystem, no network | the code is broken |
| `db` | the database | the DB layer or its fixtures |
| `fs` | the filesystem / a temp root | path resolution or fixtures |
| `app` | the app in-process (registry, services) | wiring |
| `external` | **anything outside the project's control** — its availability, config and version belong to someone else (an LLM, a local or cloud provider, a third-party API) | **nothing** — it is not our code |
| `quarantine` | — (the parked problem children) | nothing until unparked |

**THE NAMING RULE.** The class is defined by a QUESTION, not by a member:
*whose availability is it?* — and the answer must be "not ours". **Never define
the class by its first example.** It was called `live` and meant "Ollama",
because that was the first instance; a tier named after an instance stops being
a tier. **The class is now `external`, and the specific dependency is DATA — an
argument on the marker:**

```python
@pytest.mark.external("ollama")       # needs THAT daemon
@pytest.mark.external("embeddings")   # needs the CAPABILITY (a different question)
```

**A `external` test can never catch a regression in a code change**, because it
tests someone else's service and our credentials. It must not sit in a sweep
where its failure reads like a defect.

## Markers and the skip gate

Two markers carry a skip gate, both with the identical contract — **probe once,
skip VISIBLY with a reason, never a silent pass**:

| Marker | Probe | Meaning |
|---|---|---|
| `backend` | `GET /api/v1/health` (~2s) | needs a running server |
| `external(name)` | `EXTERNAL_PROBES[name]` | needs the NAMED dependency |

One gate serves every external service — the marker names the dependency, so
adding one is a line in `EXTERNAL_PROBES`, not a new fixture and a new gate:

```python
# conftest.py — the shape
@pytest.fixture(autouse=True)
def _skip_without_external(request):
    marker = request.node.get_closest_marker("external")
    if marker is None:
        return
    for dep in (marker.args or ("llm",)):
        if dep not in EXTERNAL_PROBES:
            pytest.fail(f"Unknown external dependency {dep!r} — register a probe")
        if not EXTERNAL_PROBES[dep]():
            pytest.skip(f"{DEPENDENCY_LABELS[dep]} is not reachable — needs {dep}")
```

**An unregistered dependency name FAILS the test, it does not pass it.** A
misspelled name would otherwise be a test that always runs — and if the external
call is caught downstream, always passes, proving nothing. The gate refuses to
guess.

**There is deliberately NO generic "any LLM provider" key.** One was written and
removed: a test whose fixture pins `provider="ollama"` needs THAT daemon, so a
broad probe answers a question the test did not ask — llama.cpp running while
Ollama is down would report "available" for a test that then failed.

The skip is visible in the report (`-rs` prints the reasons). A skip with a
reason is evidence; **a pass by accident is a lie.**

### Probe the SPECIFIC dependency

A probe must answer for the service the test actually calls — never "some
provider exists". The distinction is silent when wrong:

```python
# WRONG — answers for a service the test does not use
return bool(settings.openrouter_api_key or settings.deepseek_api_key)

# RIGHT — answers for what the handler calls
return _probe(f"{ollama_host}/api/tags")
```

A test whose handler needs Ollama **embeddings** will run and fail when only a
remote **chat** key is configured — a DeepSeek key cannot embed. The probe
answered "available", so the failure read as a code defect. **A probe that
answers for the wrong service is worse than no probe.**

When a test needs a different external service, add a probe to `EXTERNAL_PROBES`
rather than widening an existing one.

## What a test must not need

**A running server, unless it makes an HTTP request.** `init_default_registry()`
is in-process and returns in **0.49s**; a file marked `backend` on the grounds
that it "needs the backend" skips for no reason.

The dependency decides the tier, and the three are distinct:

| Test needs | Tier |
|---|---|
| a registry / a service object | `app` — no server |
| a seeded row in the database | `db` — no server |
| an HTTP request to the API | `backend` |
| an external service | `external("<name>")` |

## A test that needs a row should make the row

`auto_clean_tables` (autouse, function-scoped) deletes from **every ORM-managed
table** after each test. Seeded migration content listed to survive:

```
workflow_execution_history, workflow_approvals, tool_usage_logs,
_sqlite_manager_audit_log
```

**Any migration-seeded table NOT on that list is wiped after the first test.**
`workflow_triggers` is one: a test reading the seeded `monitor-rss-hourly`
passed **alone** and failed **in a file run**, because an earlier test had
already cleared the table. The seed is not a fixture.

**The fix is a fixture, not a longer survive-list.** Have the test create what it
needs:

```python
TriggerService().create_trigger(WorkflowTriggerCreate(
    id="test-verify-trigger", workflow_id="wf-test-verify",
    trigger_type="schedule", config={"cron": "0 * * * *"},
))
r = await registry.execute_tool("verify-trigger-config", {}, {"trigger_id": "test-verify-trigger"})
```

This is the general shape of the ordering class: **a test that depends on state
another test owns will pass alone and fail in a run.** Self-containment is the
repair; extending the survive-list only moves the dependency.

## Flags

| Wrong | Right | Why |
|---|---|---|
| `-p no:logging` | `--log-level=WARNING`, or `-q` | Disables pytest's logging plugin, so `caplog` — its fixture — disappears. Tests requesting it fail with `fixture 'caplog' not found`. The runner does not pass it: **match the runner.** |
| `pytest ... \| tail -N` | `pytest ... > file 2>&1` | Piping discards failure NAMES. Redirect, then `grep -cE '^FAILED'` gives the count and the names. |
| `-x` in a sweep | no `-x`; `-rf` for a greppable list | `-x` stops at the first failure and hides the rest. |
| a raw `pytest` call from the sweep | `run_tests.py --group <g>` | The runner writes a run folder, honours the quarantine, and partitions by group. |

**When a triage run's numbers disagree with the runner's, suspect the FLAGS
before the code.** A quieting flag can silently remove plugin-provided fixtures.

## Measured costs

| Measurement | Value |
|---|---|
| the full backend suite | **1850s (30m50s)** |
| `unit` + `workflows` together, parallel | **105s** |
| the `components` group | 29s |
| the `api` group | 31s |
| the sweep with `--test-group components` | 51s |
| mypy over `app/` | 2.3s (382 files) |
| the two path checks | 0.8s |
| the pre-commit hook, total | 3.5s |

Test-tree sizes: `unit` 117 files · `workflows` 28 · `api` 14 · `components` 4 ·
`integration` 1 · `e2e` 1. **`unit` is large enough to need subdividing.**

## Markers declared but unused

`slow`, `integration`, `performance` are declared in `backend/pyproject.toml`
and **carried by zero tests**, so they exclude nothing. The runner's behaviour
comes from the groups and its `QUARANTINE_FILES` list, not from markers.

`--reload` and the `backend` gate: editing any file restarts the app, and for
roughly two seconds after that every `backend`-marked test skips. A sweep that
edits code and reruns immediately can read as "all skipped".
