"""The shared-db guard's own test — a guard nobody has seen fire is a guess.

It runs the probe fixture (`tests/meta/shared_db_guard_probe.py`, never collected
by a group) in a SUBPROCESS, because the probe's whole point is that the guard
turns two of its tests red — and a suite cannot hold tests that are meant to
fail. The subprocess also gets its own worker, its own copy of the test
database, and its own guard state, so nothing leaks back into this run.
"""

import os
import subprocess
import sys

from app.core.config import Paths

# The locator, not a parent-crawl — the project's path rule (a hand-computed
# climb is the phantom-DB class). `Paths.tests_dir` is the canonical tests root,
# so backend/ is one step up from it.
BACKEND = Paths.tests_dir.parent
PROBE = str(Paths.tests_dir / "meta" / "shared_db_guard_probe.py")


def _run_probe() -> str:
    """Run the probe fixture; return its combined output."""
    env = dict(os.environ)
    env["PYTEST_ADDOPTS"] = ""  # the harness's own flags must not reach it
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", PROBE, "-q", "-p", "no:randomly"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    return proc.stdout + proc.stderr


def test_guard_passes_the_innocent_and_fails_the_two_contract_breaches():
    out = _run_probe()

    # 1. all three CALL phases passed — no false positive on the innocent one,
    #    and the guard reports itself in the teardown, not as a test failure
    assert "3 passed" in out, f"the call phases did not all pass:\n{out}"

    # 2. the two breaches were caught at teardown, one error each
    assert "2 error" in out, f"expected two teardown errors:\n{out}"
    assert out.count("SharedDbGuardError") >= 2, f"the guard did not fire twice:\n{out}"

    # 3. the messages say WHAT was wrong, not just that something was
    assert "OUTSIDE the test installation" in out, out
    assert "private.db" in out, out
    assert "NOTHING cleans" in out, out
    assert "workflow_kinds" in out, out
