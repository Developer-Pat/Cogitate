---
tags: [type/dev-notes]
updated: 2026-09-20
---

# Testing (the test suite)

## The two areas

| Area | Tool | Purpose |
|---|---|---|
| The **test sweep** | `scripts/testing/run_tests.py` | Code + UI health — the unit and integration tests |
| The **system sweep** | `scripts/core/sweep.py` | The RUNNING system — startup, shutdown, zombies, ghosts, errors, logs, messages, services |

They are DIFFERENT tools with DIFFERENT purposes — never conflated. "The sweep"
alone is ambiguous; say which one.

## Run ONE module, not the suite — the fastest feedback loop

**Not every test has to run every time.** While you are working on something,
run the module you are working on and nothing else:

```
python3 scripts/testing/run_tests.py --file tests/unit/tools/test_execution_service.py
python3 scripts/testing/run_tests.py --file tests/unit/test_page_map_sync.py::test_the_enum_has_no_duplicates
python3 scripts/testing/run_tests.py --file tests/a.py --file tests/b.py      # repeatable
```

`--file` takes a module (`path.py`), a single test (`path.py::test_name`), or
several of either. It bypasses `--group` entirely — only what you name runs,
including a quarantined file if you name it deliberately.

| To check | Run | Approx |
|---|---|---|
| one module | `--file tests/…/foo.py` | **~12 s** |
| one test | `--file tests/…/foo.py::test_bar` | **~12 s** |
| a whole group | `--group unit` | ~2 min |

The same file takes ~12s on its own and contributes to a ~2 min group run, so
running the module you touched is roughly **10x cheaper than running the group
it lives in** — and it is the difference between a 12-second loop and a
two-minute one.

**A targeted run is serial automatically.** `--file` does not use xdist, because
spreading one or two files across cores costs more in worker startup than it
saves (measured: 14s serial vs 29s parallel for two modules). `--group` is
parallel for the opposite reason — it is minutes of work. Pass `--parallel` or
`--sequential` to force either, if you have measured a reason to.

**A targeted run finishes in seconds, so the loop stays tight:** change
something, run the module, see the result. Escalate to the group only at the
end, when you want to know whether you broke a neighbour.

## The best way to run the tests

```
python3 scripts/testing/run_tests.py --group <name> [--runs-dir PATH]
        [--parallel|--sequential] [--timeout N]
        [--require-backend] [--include-quarantine] [--live|--no-live]
```

**Leave it parallel — that is the default, and it is the whole point of the
runner.** Parallel runs the files across cores; sequential runs them one after
another in a single process. Same tests, same result, wildly different cost:

| Invocation | Covers | Approx |
|---|---|---|
| `--group all` | the whole backend — 175 files | **~2 min** |
| `--group unit` | the bulk of it — 126 files | **~2 min** |
| `--group ui` | the frontend (vitest, 67 files) | **~15 s** |
| any of the above `--sequential` | the same files, serialized | **~25-30 min** |

Reach for `--sequential` only to reproduce an **ordering-dependent** failure,
where the serial order is the thing under test. Otherwise drop the flag. The
runner prints a warning on the slow path saying exactly this.

### Never run the tests with a bare `pytest` against the tree

`uv run pytest …` or `python -m pytest backend/tests/` on the whole tree is
**serial** and does **not** exclude the quarantine. It produces a wall of
failures that the runner never shows — the parked problem-children plus the
ordering-cascade — and it takes tens of minutes to do it. That is not a
redder picture of the suite; it is a *different, wrong* one. Use the runner.

To check one thing, name it — `--file <module>` (see the section above), which
still writes the report and still respects the runner's setup. Reach for a bare
`pytest` only if the runner itself is what you are debugging.

## The groups

The functional partitions, which are the directory layout:
`unit / workflows / api / components / integration / e2e / all / ui`
(`ui` is the frontend's vitest; the others run pytest/xdist).

Defaults: `group=unit`, parallel, and the run lands in its own folder under the
runs dir — `data/test-runs/<ts>/`, resolved by the app's path locator.

## What a run RECORDS about its selection (the fingerprint)

Every run's envelope carries `selection_count` and a `selection_fingerprint` — a
short hash of the SORTED selection (`_fingerprint`), written into both
`run_start` and the `report.md` header.

**WHY IT EXISTS.** The envelope already carried `selection[:50]`, so a 53-file run
could not prove which selection it was — and "compare against the last run of the
same selection" was a guess that a changed selection would quietly invalidate. The
count and the hash make it a fact, which is what the page's **what changed**
comparison rests on (`app/domain/testing/diffing.py`: the baseline must be GREEN,
of the SAME fingerprint, and older than the run being explained).

**ONE SHAPE, NO COMPATIBILITY BRANCH.** A run from before the field simply lacks
it, and the reader answers "this run recorded no selection fingerprint, so it cannot
be matched to a comparable run" — which is a fact about that run, not a parse
failure.

**The `ui` group's fingerprint is its LABEL**, because that group declares an empty
selection (vitest picks its own files). It identifies the group and claims nothing
about which files ran.

## The page's OWN exercise — `backend/selftest/` (deliberately red)

`backend/selftest/test_page_exercise.py` is a suite that **is meant to fail**: one
pass, one failure, one skip with a reason, one setup error, and one test that waits
25 seconds so Cancel has something to kill. The user-testing page runs it **by
name** from its Self-test tab, and the file declares its own pass condition
(`EXPECTED_SHAPE`), which the catalog reads so the page can say what a correct run
looks like.

**Why it sits OUTSIDE `tests/`, and how to keep it that way.** `testpaths` is
`["tests"]` and every group in `GROUPS` selects under `tests/`, so a fixture whose
job is to produce failures inside the tree would turn every full run and every
sweep red — and a suite that is always red tells a person nothing. The separation
is by PATH, not by a marker, so it cannot be undone by forgetting a decorator.

**Prove it holds, both ways, when you touch either side:**

```
python3 -c "import importlib.util,sys; s=importlib.util.spec_from_file_location('rt','scripts/testing/run_tests.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print([f for f in m._select('all', False) if 'selftest' in f])"
# -> []                     the runner's groups select none of it
cd backend && python3 -m pytest --collect-only -q | grep -c selftest
# -> 0                      and a raw pytest does not collect it either
```

Its own run is one file, so it is the fastest way to see a red run, a skip with a
reason, and a killable run without waiting for the suite.

## The markers (the semantic filters)

- `backend` — the connection-class tests (skip when the backend is down; the
  runner's pre-flight stamps the report, and `--require-backend` fails the run
  early)
- `quarantine` — the parked problem-children (excluded from every group by
  default; `--include-quarantine` runs them)

Markers must sit AFTER `import pytest` — never inside an embedded
fake-server heredoc, where they corrupt the payload.

## What the page SHOWS of a run — two display rules

A run's output is written for a DEVELOPER; the page's reader may be neither a
developer nor the person who started the run. Both rules were found by driving the
page with the deliberately red fixture, and both are the same move — show the fact,
not the machinery.

1. **How a run ended is stated in WORDS, never as an exit code.** `exit 1` means
   nothing to most people, and the codes COLLIDE (2 is both pytest's "interrupted"
   and the runner's "refused to run"), so the verdict comes from the run's own
   evidence first and the code only fills the gap. ONE function serves the live
   badge and the history's column (`frontend/src/utils/runVerdict.ts`); the raw code
   lives in the tooltip, for whoever wants it.

2. **pytest's own markers never reach the reader.** A failure's text in the JUnit
   XML arrives with `E`- and `>`-prefixed lines and trailing `___ test name ___`
   rules — pytest's rendering, not the test's words. The page strips the markers and
   the rules at DISPLAY (`frontend/src/utils/pytestProse.ts`) and keeps the
   substance, including `Error:`-style lines, which are the test's own message
   rather than a marker. Strip at display, never in the stored artifact: the XML is
   the evidence and stays exactly as pytest wrote it.

## The reports

**ONE RUN, ONE FOLDER** under `data/test-runs/<ts>/`, and **the hard copy is the
evidence** — a piped console run lies (truncation, interleaved workers). Three
artifacts, each answering a different question:

| file | answers | read by |
|---|---|---|
| `report.md` | what happened — the header (group, parallel, files, the backend stamp), the output, the durations, the summary, ELAPSED and EXIT | a developer |
| `report.xml` | what each test did — JUnit XML: per-test outcome, the skip message, the duration | the user-testing page |
| `events.jsonl` | what is happening NOW — one JSON line per test as it runs. The XML is written when the session ENDS, so progress can only come from here | the page, live |

**`events.jsonl` carries four kinds of line**, all written by
`scripts/testing/events_plugin.py` (inert unless `COGITATE_EVENTS_FILE` is set,
controller-only under xdist):

    session_start   the rootdir, once, before the first test
    collect         pytest's COLLECTED total for this run — the page's denominator
    test            one line per test: nodeid, outcome, duration, and the reason for a skip or a failure
    summary         pytest's own final tally, when the session reaches one

The **`collect` line has two sources, and neither is trivial**: in serial the
process running the tests is the one that collected them
(`pytest_collection_modifyitems`). Under `-n auto` the CONTROLLER never holds an
item — measured, its `session.items` is empty even at `sessionfinish` — so the
total comes from xdist's own per-node report, where every worker hands back the
WHOLE session. The total is therefore the LARGEST report, never the sum: summing
would count the session once per worker. A page-side count over the test tree
would be wrong in exactly the runs that matter most, because a parametrized file
expands into more cases than it has `def test_` lines (observed: a 53-file
selection whose catalog says 537 test functions collects 540 items).

**The `ui` (vitest) group gets the envelope only** — no per-test lines, because
the per-test source is pytest's `pytest_runtest_logreport`. It says so on screen
rather than showing an empty feed.

## Deleting a run

The page's **Delete** moves a run's folder to `trash/test-runs/<name>` — a
recovery, not an erasure: the folder keeps its three artifacts and a collision
gets a `-2` suffix rather than overwriting the copy already there. Nothing prunes
automatically (no retention rule anywhere), and **a run in progress cannot be
deleted** — the lock answers, and the refusal names it.

The runner prints `RUN_DIR: <path>` when it finishes, so a caller (the sweep, a
timer) can find the run without guessing its name. `--runs-dir` moves where run
folders are created; there is no `--output`, because a run has ONE name wherever
it is started from.

The runner's own runs and the **system sweep's** reports live apart on purpose:
runs are a person's work (`data/test-runs/`), the sweep's output is the chain
machine's health record (`data/sweep/`). Both are resolved from the locator, so
nothing test-related is written to `local/` — that directory is a developer's
scratch pad and does not exist in an installation.

## The discipline

- Run ONLY the failing tests while chasing; never the full suite
- Long runs need the user's prior OK
- Run the groups, not the tree (see above)
- A subdirectory run file-by-file is not the same as a batched run of that
  directory — some families stall when batched
- A subset that fails to reproduce a failure is evidence about that failure's
  precondition, not proof it is fixed

## The current state

- **Standing failure**: `test_skill_aware_cb.py::test_load_global_skill` — a
  missing sample skill file, NOT a regression (confirmed identical with the
  change stashed).
- **The api group errors at SETUP on one case** —
  `tests/api/test_agent_package_provision.py`: `UNIQUE constraint failed:
  providers.name`. The file's `provision_env` fixture inserts two fixed-name
  providers (`openrouter`, `ollama`), so the second test to use it collides with
  the first. **It reproduces alone**, so it is a test-isolation defect in that
  file, not a parallel-collision flake — and not this page's.
- **Quarantine**: ONE file — `workflows/test_monitor_family.py` (the ordering
  flake: passes alone, fails in the full parallel run).
- **The ordering/state class is wider than the quarantine list.** Observed in the
  full parallel group while green alone: `test_phase2_tools.py` (2 cases) and
  `test_workflow_compositions_api.py` (2 cases). Different files each run, which
  is the signature of shared state rather than one broken test — and the reason
  concurrency in the RUNNER (one run at a time) is not the same question as
  isolation *inside* a parallel run.

Counts belong in the runs, not here — read the newest run under
`data/test-runs/` for the current numbers.
