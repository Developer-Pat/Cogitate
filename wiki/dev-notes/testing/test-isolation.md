---
tags: [type/dev-notes]
---

# Test Isolation — the suite runs in its own installation

The test suite runs against a **temporary installation root**, not the project's.
The database, the agent workspaces, the per-agent memory databases, the pipeline
traces and the logs all live in one temp directory, created before the
application is imported and removed when the session ends.

This is not tidiness. Before it, a test run left workspaces in the real `agents/`
directory, wrote synthetic traces into the production trace database where they
read as real runs, and appended to the production log.

## How it works

| piece | what it does |
|---|---|
| `conftest` | creates `TEST_ROOT` and sets `DATABASE_URL` into it **before importing the app** |
| `Paths.from_settings` | derives the installation root from the shared database's location, and re-roots every other declared path against it |
| `test_engine` | builds the test engine from that URL; teardown removes the whole root — and the interpreter's exit removes it again if no test ever asked for that fixture |

**The ordering is load-bearing.** The database engine is created at *import
time* from `settings.database_url`, so a fixture that sets it later leaves
`AsyncSessionLocal` bound to the real database — and only the FastAPI dependency
path would be isolated.

**Why the root follows the database.** The shared database sits at the root of an
installation, so its parent *is* that root, and everything else hangs off it.
Moving one value moves the installation. Production is unaffected: its database
is already there, and the resolver returns the declared defaults unchanged.

## The installation never leaks silently

`TEST_ROOT` is created at **import**, so every process that imports the conftest
makes one — the xdist controller, and any worker whose tests never touched the
database, included. The removal is registered twice for that reason: the engine
fixture's teardown (the ordinary path) and interpreter exit (every other one).

A removal that fails is **reported, not swallowed**. `TestInstallationLeakWarning`
names the root, the path the removal stopped at, and what is left inside, so a
leak is a line in the run's `report.md` rather than a slow accumulation in
`/tmp`. Most of the 57 roots (248 MB) found in `/tmp` came from the path that
never called the cleanup at all, not from removals that failed.

Verify both halves — the warning firing, the healthy path staying quiet, and
that the end-to-end check can go red — with:

```bash
.venv/bin/python scripts/verify_test_harness_cleanup.py --revert-check
```

## The rule this exists to protect

**A path resolved from settings must go through `Paths`.** Two things silently
escape it, and neither fails when it does:

- reading a raw setting directly — `settings.log_file` was written to the
  production log for exactly this reason;
- computing `BASE_DIR / "something"` by hand.

If a new path is needed, add it to `Paths` as a field declared relative to
`BASE_DIR`. It will be re-rooted automatically; nothing else needs to know.

## How to check this page

**Run the scanner:**

```bash
python3 `check_path_arithmetic()` in `scripts/core/sweep/backend.py`
```

**Do not substitute a grep for it.** The obvious one —
`grep -rn "BASE_DIR /" backend/app` — is wrong twice over, and this page's first
version made exactly that mistake:

- **the wrong tree**: eleven sites lived in `backend/tests/`, and the whole
  macro-saves family in `backend/app/api/v1/macros/`;
- **the wrong shapes**: a parent-walk (`parents[3] / "cogitate.db"`), an
  `expanduser("~/Projects/...")` and a cwd-relative `"./data/..."` contain no
  `BASE_DIR` at all.

The scanner walks app, tests and scripts and knows every shape. It exits 1 when
it finds anything, so it can become a gate.

Then confirm the isolation itself, by measuring before and after a test run that
creates things:

```bash
ls agents/ | wc -l                                  # before
cd backend && uv run pytest tests/unit/test_agent_rename_reset.py -q
ls ../agents/ | wc -l                               # after — must be identical
```

## Related

- [[dev-notes/lifecycle/startup|Startup — the boot sequence]]
- [[dev-notes/architecture/Paths and Path Resolution|Paths and Path Resolution]]
- [[dev-notes/known-issues|Known Issues]]
