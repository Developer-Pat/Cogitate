---
title: The Scripts-Core Sweep
type: dev-note
path: scripts/core/sweep/
created: 2026-08-25
tags: [type/dev-note, domain/devtooling, status/active]
---

# The Scripts-Core Sweep (the code-quality sweep)

The SECOND sweep surface (the runtime sweep is the IntegrityAudit in
`backend/app/domain/audit/`). The scripts-core sweep scans the CODE
quality: `scripts/core/sweep/` (backend.py + frontend.py + shared.py
+ cli.py). 2026-08-25: the two sweeps had NO cross-reference — the
scripts sweep was effectively lost (the path-crawl check existed but
nobody knew). This note is the indexing fix.

## The checks (backend.py)

- `check_path_arithmetic` — hand-computed path arithmetic (the
  phantom-DB class): `Path(__file__).parent` crawls (incl. the
  `.resolve()` variant), the `dirname(__file__)` up-crawls, the
  cwd-dependent paths, the raw shared-DB opens. Fails (EXIT 1) on
  the violations; the Paths locator is the ONE resolver.
- `check_mypy` / `check_pytest` / `check_pytest_all` — the type
  checker + the test suites.
- `check_imports` / `check_deprecation_warnings` / the router
  decorators — the hygiene checks.

## The invocation

From the repo root (the venv):

```bash
.venv/bin/python3 -c "import sys; sys.path.insert(0, 'scripts/core');
from sweep.backend import check_path_arithmetic
print(check_path_arithmetic())"
```

The cli: `scripts/core/sweep/cli.py` (the full sweep's entry).

## The doctrine (the pathing)

The Paths locator (`backend/app/core/config.py`) is the ONE
resolver for the canonical app paths — `logs_dir`, `skills_dir`,
`agents_dir`, `root`, etc. New code must use the locator; the
`check_path_arithmetic` enforces it.
