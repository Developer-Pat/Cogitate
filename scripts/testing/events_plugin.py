"""The test-EVENTS plugin — the live record of a run.

WHY A PLUGIN AT ALL. `--junitxml` is written when the session ENDS, so it can
never report progress: it answers "what did each test do", asked afterwards.
Progress needs a source that speaks WHILE the run happens, and
`pytest_runtest_logreport` is pytest's own per-test report — the only honest
place to learn a test's outcome without scraping the console. Scraping `-q`
dots cannot name a test, and a runner that guessed would be inventing results,
which is the exact lie the user-testing page exists to avoid.

WHAT IT WRITES. One JSON object per line, appended as the run happens:

    {"t":"session_start","rootdir":"/home/…/cogitate"}
    {"t":"collect","count":1484,"via":"xdist"}
    {"t":"test","nodeid":"tests/unit/foo.py::test_bar","outcome":"passed","duration":0.04}
    {"t":"test","nodeid":"tests/unit/foo.py::test_baz","outcome":"skipped","reason":"needs Ollama"}
    {"t":"summary","counts":{"passed":916,"failed":1,"skipped":8},"duration_s":104.9}

The ENVELOPE (`run_start` / `run_end`) is the runner's business, not the
plugin's: the runner owns the process, so it is the only honest source for the
pid, the working directory, and the exit code.

THREE RULES, each learned the hard way:

1. **INERT WITHOUT THE ENVIRONMENT.** The plugin does nothing unless
   ``COGITATE_EVENTS_FILE`` is set, so a plain ``pytest`` call — a developer, CI,
   the sweep — behaves exactly as before: no file, no writes, no cost. The
   events are a capability of the runner, not a tax on every invocation.

2. **THE CONTROLLER WRITES, NEVER A WORKER.** Under ``-n auto`` every xdist
   worker loads this plugin too, and its reports are a fragment of the run. Only
   the controller sees the merged view, so every worker must stay silent
   (``config.workerinput`` is present in a worker) — otherwise N workers
   interleave N copies of each event into one line-per-event file.

3. **IT NEVER FAILS THE RUN.** Every write swallows its own errors. A feed that
   can break the thing it observes is worse than no feed at all.

AND ONE THING TO KNOW ABOUT THE TOTAL, because it is the one number that cannot
come from the obvious place:

4. **THE COLLECTED TOTAL HAS TWO SOURCES, and neither is the other's guess.**
   In SERIAL the process running the tests is the one that collected them, so
   `pytest_collection_modifyitems` sees every item. **Under `-n auto` the
   CONTROLLER NEVER HOLDS AN ITEM AT ALL** — measured, not assumed: its
   `session.items` is empty even at `sessionfinish`, and no collection hook
   fires on it. The total there comes from xdist's own per-node report, where
   every worker hands back the WHOLE session (measured: 12 nodes, each
   reporting all 26 ids of a two-file selection). So the total is the LARGEST
   report, **never the sum** — summing would count the session once per worker
   and report a 13× run.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

#: Set in `pytest_configure` when this process is an xdist WORKER. Only the
#: controller sees the merged picture, so a worker must stay silent (rule 2).
_SILENT = False

#: The largest collected total written so far — both sources can report more
#: than once, and the run's total must be ONE line (rule 4).
_COLLECTED = 0


def _events_path() -> str | None:
    """Where this run's events go — or None, which means stay silent."""
    return os.environ.get("COGITATE_EVENTS_FILE") or None


def _emit(event: dict[str, Any]) -> bool:
    """Append one line. Never raises (rule 3); True when it landed."""
    path = _events_path()
    if not path:
        return False
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001 — a telemetry write must never be fatal
        return False
    return True


def _skip_reason(report: Any) -> str:
    """pytest's skip message, dug out of the longrepr it actually is.

    A skip during `setup` carries a tuple (file, line, reason); a skip raised by
    a marker carries the reason as a string. Both are reasons, and the reason is
    the whole point — the page's job is to say WHY a test did not run.
    """
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) >= 3:
        return str(longrepr[2]).strip()
    text = getattr(report, "longreprtext", None) or str(longrepr or "")
    return " ".join(text.split())[:300]


def _emit_collect(count: int, via: str) -> None:
    """Write the run's TOTAL, once per high-water mark (rule 4).

    A total is a live claim — "312 of 1484" — and the page needs a denominator
    that is a FACT for the run in progress rather than the page's own arithmetic
    over the tree. The two sources are `pytest_collection_modifyitems` (serial:
    the process is the collector) and xdist's per-node report (parallel: every
    worker reports the WHOLE session, so the LARGEST wins and a sum would be a
    lie). Both can report more than once, hence the high-water mark: the file
    gets ONE collect line in every real run, and a bigger report — if one ever
    arrives — is appended rather than ignored.

    The mark moves only when the write LANDED, so a transient write failure is
    retried by the next report instead of being remembered as done.
    """
    global _COLLECTED
    if _SILENT or count <= _COLLECTED:
        return
    if _emit({"t": "collect", "count": count, "via": via}):
        _COLLECTED = count


def pytest_collection_modifyitems(session: Any, config: Any, items: list[Any]) -> None:
    """SERIAL — the whole session, on the process that runs it."""
    _emit_collect(len(items), "session")


try:  # pragma: no cover - the import is the test; the hook needs the hookspec
    import xdist  # noqa: F401  (registers `pytest_xdist_node_collection_finished`)

    _HAS_XDIST = True
except ImportError:  # pragma: no cover - a fork without xdist
    _HAS_XDIST = False

if _HAS_XDIST:

    def pytest_xdist_node_collection_finished(node: Any, ids: list[str]) -> None:
        """PARALLEL — the total as the controller can honestly know it (rule 4).

        pytest REFUSES a hook whose hookspec is absent (`PluginValidationError`),
        so this is defined only where xdist provides the spec — otherwise the
        plugin would fail to load in a plain pytest run.

        `ids` is what ONE node collected, and under every xdist distribution mode
        a worker collects the whole session before the controller assigns work.
        The LARGEST report is the session's total; summing is the trap.
        """
        _emit_collect(len(ids), "xdist")


def pytest_configure(config: Any) -> None:
    """Mark an xdist worker silent (rule 2), and announce the session so a
    tailer that connected before the first test knows the run exists."""
    global _SILENT
    if hasattr(config, "workerinput"):
        _SILENT = True
        return
    if _events_path():
        _emit({"t": "session_start", "rootdir": str(config.rootpath)})


def pytest_runtest_logreport(report: Any) -> None:
    """ONE event per test — the outcome the test actually reached."""
    if _SILENT:
        return
    outcome: str | None = None
    event: dict[str, Any] = {
        "t": "test",
        "nodeid": report.nodeid,
        "duration": round(getattr(report, "duration", 0.0) or 0.0, 3),
    }
    if report.skipped:
        # An xfail arrives here too, and "skipped" with pytest's own reason is
        # the honest reading: it did not run to a verdict.
        outcome = "skipped"
        event["reason"] = _skip_reason(report)
    elif report.failed:
        # A failure in setup or teardown is an ERROR: the test never reached a
        # verdict, and calling that "failed" would blame the assertion.
        outcome = "failed" if report.when == "call" else "error"
        event["reason"] = _skip_reason(report)
    elif report.when == "call":
        outcome = "passed"
    else:
        return  # setup/teardown passed — not a result, and nobody asked
    event["outcome"] = outcome
    _emit(event)


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """The run's counts — pytest's OWN tally, not a second one kept alongside it.

    Reading the terminal reporter's stats is how the numbers the human saw and
    the numbers the page shows come from one place. A separate counter would be
    a claim, and a claim that can drift.
    """
    if _SILENT:
        return
    try:
        stats = getattr(terminalreporter, "stats", {}) or {}
        counts = {
            "passed": len(stats.get("passed", [])),
            "failed": len(stats.get("failed", [])),
            "errors": len(stats.get("error", [])),
            "skipped": len(stats.get("skipped", [])),
            "xfailed": len(stats.get("xfailed", [])),
            "xpassed": len(stats.get("xpassed", [])),
        }
        started = getattr(terminalreporter, "_session_start", None)
        # pytest 9 keeps the session's start as a `timing.Instant`, not a float
        # (the older `_sessionstarttime` is gone — reading it silently returned
        # None, which is how a duration quietly becomes "unknown").
        duration = round(started.elapsed().seconds, 2) if started is not None else None
        _emit({"t": "summary", "counts": counts, "duration_s": duration})
    except Exception:  # noqa: BLE001 — the summary is a courtesy, never a gate
        pass
