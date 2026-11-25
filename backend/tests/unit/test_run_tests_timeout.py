"""The runner's per-test cap — the flag that makes a stall NAME ITSELF.

CI's `backend · unit` group ran for 30 minutes and was cancelled by the job's own
timeout, twice across two days. Each time the evidence was the word "cancelled" plus
49 test files that never reported, and finding even that cost an artifact download.
A per-test cap turns the next stall into `FAILED <nodeid> -- timed out after Ns`.

Three claims, and this file pins them:

1. **The flag is on the command line at all** — without it CI is back to silence.
2. **The value is sane**: above the slowest honest test (40s, a permission test that
   waits on purpose) and far below the 30-minute job cap that used to swallow the
   evidence.
3. **It can be tuned** by `COGITATE_TEST_TIMEOUT` without editing the script.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Paths

#: The runner under test — resolved through the LOCATOR, never re-derived from
#: `__file__` (the project's path rule: one place knows where things live).
RUNNER_PATH = Path(Paths.root) / "scripts" / "testing" / "run_tests.py"


def load_runner() -> Any:
    """A FRESH module per test — `PER_TEST_TIMEOUT_S` is read once, at import."""
    spec = importlib.util.spec_from_file_location("cogitate_run_tests_under_test", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_pytest_command_carries_a_per_test_timeout(tmp_path: Path) -> None:
    runner = load_runner()
    cmd = runner._pytest_args(["tests/unit/x.py"], tmp_path, use_parallel=False)

    assert f"--timeout={runner.PER_TEST_TIMEOUT_S}" in cmd, (
        "a stalled test must fail BY NAME — without the cap the job is cancelled after "
        "30 minutes and names nothing"
    )


def test_the_cap_is_above_honest_slowness_and_below_the_job_timeout() -> None:
    runner = load_runner()

    # 40s is the slowest honest test (the permission timeout waits on purpose); the
    # CI job's own cap is 30 minutes (1800s), and that is what swallowed the evidence.
    assert 60 <= runner.PER_TEST_TIMEOUT_S <= 600, (
        f"a {runner.PER_TEST_TIMEOUT_S}s cap either false-fails an honest test or "
        "re-creates the 30-minute silence it exists to break"
    )


def test_the_cap_can_be_tuned_without_editing_the_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COGITATE_TEST_TIMEOUT", "45")
    runner = load_runner()

    assert runner.PER_TEST_TIMEOUT_S == 45
    assert "--timeout=45" in runner._pytest_args(["x"], tmp_path, use_parallel=True)
