#!/usr/bin/env python3
"""The test runner — the test-sweeps redesign's harness.

Runs the backend test GROUPS (the functional partitions — the
directory layout) and writes the run's artifacts (the policy: "the
hard copy is the evidence").

Usage:
    python3 scripts/testing/run_tests.py [--group unit|workflows|api|
        components|integration|e2e|all]
        [--parallel | --sequential] [--runs-dir PATH] [--timeout N]
        [--require-backend] [--include-quarantine]

    python3 scripts/testing/run_tests.py --file tests/unit/foo.py
        [--file tests/unit/bar.py::test_one ...]

One module is the fastest loop — prefer it while working:
    --file PATH runs exactly that module (or PATH::test_name, one
    test), repeatable, bypassing --group. Not every test has to run
    every time.

The groups:
    unit / workflows / api / components / integration / e2e / all / ui
    (ui = the frontend's vitest suite — the backend groups run
    pytest; the ui group runs vitest)

The quarantine (the parked problem-children, 04-quarantine.md) is
EXCLUDED from every group by default — it runs only with
--include-quarantine (the visible section, never silent).

The semantic markers ride on top: `backend` (the connection-class —
skips when the backend's down) and `quarantine` (the parked set).

ONE RUN, ONE FOLDER. A run lands in its own directory under the runs
dir (default: the locator's `Paths.test_runs_dir`, i.e.
`data/test-runs/<ts>/`) holding three artifacts, each answering a
different question:

    report.md      what happened — the developer's hard copy: the
                   header, pytest's own output verbatim, ELAPSED/EXIT
    report.xml     what each test did — JUnit XML (pytest's own
                   `--junitxml`) for the page to parse, instead of
                   reverse-engineering prose with regexes
    events.jsonl   what is happening NOW — one JSON object per line,
                   written as the run happens. XML is written when the
                   session ENDS, so progress can only come from here.

`report.md` keeps its exact shape: the developer's workflow does not
change. The runner prints `RUN_DIR: <path>` so a caller (the sweep,
the backend) can find the run without knowing its name.

Parallelism follows the work: a GROUP runs parallel (minutes to
spread), a --file run runs serial (xdist's worker startup costs more
than one or two modules). Force either with --parallel/--sequential.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
PLUGIN_DIR = ROOT / "scripts" / "testing"

#: The pytest plugin that writes the per-test events (scripts/testing/
#: events_plugin.py). Loaded by name, so PLUGIN_DIR goes on PYTHONPATH.
EVENTS_PLUGIN = "events_plugin"

# The functional GROUPS (the directory partitions)
GROUPS = {
    "unit": ["tests/unit"],
    "workflows": ["tests/workflows"],
    "api": ["tests/api"],
    "components": ["tests/components"],
    "integration": ["tests/integration"],
    "e2e": ["tests/e2e"],
    "all": ["tests"],
}

# The QUARANTINE (04-quarantine.md — the parked problem-children).
# 2026-08-27: the ACP family was RELEASED — their "failures" were
# the quarantine-marker's heredoc-corruption (my breakage, fixed —
# the fake-servers' NameError cascade; all 6 files pass now).
# 2026-09-25: THE MONITOR IS RELEASED TOO. Its parking condition was
# "parked until the ordering's root-caused", and the ordering WAS
# root-caused: the cross-group interference was a POISONED lru_cached
# settings object (`test_provisioning.py` left DATABASE_URL naming a
# throwaway database, so every later test in its xdist worker resolved the
# shared DB from a database without the migration-only tables, and died on
# `no such table: workflow_templates`). With that fixed the file passes
# alone (18) and inside `--group all`.
#
# THE LIST IS NOW EMPTY, and empty is the healthy state: a name here is a
# test hidden from EVERY group, and the suite's job is to be a signal.
# Keep it empty — fix the flake instead.
QUARANTINE_FILES: list[str] = []


def default_runs_dir() -> Path:
    """The runs dir, from the LOCATOR — one authority for where things live.

    The app's `Paths` is the single declaration; this script asks it rather than
    repeating the path (the bug class the locator exists to end: two copies of
    one location, one of them silently stale).

    The fallback exists ONLY so the script still runs on an interpreter that
    cannot import the app. The backend always passes --runs-dir explicitly when
    it spawns, so the spawn path never depends on the import succeeding.
    """
    try:
        sys.path.insert(0, str(BACKEND))
        from app.core.config import Paths  # noqa: PLC0415

        return Path(Paths.test_runs_dir)
    except Exception:
        return ROOT / "data" / "test-runs"


def _files_in(dirs: list[str]) -> list[str]:
    files = []
    for d in dirs:
        base = BACKEND / d
        if not base.exists():
            continue
        for dirpath, _, fnames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for fn in fnames:
                if fn.startswith("test_") and fn.endswith(".py"):
                    files.append(os.path.relpath(os.path.join(dirpath, fn), BACKEND))
    return sorted(files)


def _select(group: str, include_quarantine: bool) -> list[str]:
    files = _files_in(GROUPS[group])
    if not include_quarantine:
        files = [f for f in files if f not in QUARANTINE_FILES]
    return files


def _fingerprint(selection: list[str], label: str) -> str:
    """A short hash of WHAT THIS RUN SELECTED — the fact a diff needs.

    THE PROBLEM IT SOLVES. The run record carried `selection[:50]`, so a 53-file
    run could not prove which selection it was, and "compare against the last run
    of the same selection" was a guess that a changed selection would quietly
    invalidate. A count plus a hash of the SORTED list is a fact, and it costs one
    field in the envelope.

    The `ui` group declares an EMPTY selection — vitest picks its own files — so
    its fingerprint is the label. That identifies the group, not the files, which
    is exactly what it can honestly claim.
    """
    basis = sorted(selection) if selection else [f"group:{label}"]
    return hashlib.sha256("\n".join(basis).encode("utf-8")).hexdigest()[:12]


def _next_run_dir(runs_dir: Path, ts: str) -> Path:
    """The name a run's folder WILL have. Nothing is created here.

    The name is chosen before the lock is taken, so the lock can carry the run's
    id; creation follows the lock, so a refused run leaves no empty folder behind.
    A second run in the same second gets a suffix rather than sharing a folder —
    two runs must never mix their artifacts.
    """
    for n in range(1, 100):
        candidate = runs_dir / (ts if n == 1 else f"{ts}-{n}")
        if not candidate.exists():
            return candidate
    raise SystemExit("[run_tests] cannot name a run dir — 99 collisions")


def _the_lock():
    """The run lock, from the app's domain (ONE definition, shared with the page).

    FATAL when unavailable, deliberately. The lock is what keeps two runs from
    presenting as flaky tests, and a run that quietly proceeded without it would
    be the exact failure it exists to prevent.
    """
    sys.path.insert(0, str(BACKEND))
    try:
        from app.domain.testing.run_lock import (  # noqa: PLC0415
            RunInProgress,
            acquire,
            clear_stale,
            release,
        )
    except ImportError:
        print(
            "[run_tests] cannot import the run lock (app.domain.testing.run_lock).\n"
            "  The single-run lock is what keeps two overlapping runs from\n"
            "  presenting as FLAKY TESTS — the worst possible presentation,\n"
            "  because the report blames the code. Refusing to run without it.\n"
            "  Run from the project root, with the project's environment."
        )
        raise SystemExit(5) from None
    return acquire, release, clear_stale, RunInProgress


def _report_refusal(exc, runs_dir: Path) -> None:
    """Say what is in the way, and what to do about it. Never a bare code."""
    print(f"[run_tests] REFUSING TO START — {exc}")
    if getattr(exc, "stale", False):
        print(
            "  That process is GONE, so the run died without releasing its lock.\n"
            "  Clearing it is a DELIBERATE act, never automatic — a lock that\n"
            "  clears itself when it feels stale can clear itself while another\n"
            "  run is starting, which is the collision it exists to prevent.\n"
            "  Clear it with: python3 scripts/testing/run_tests.py --clear-stale-lock"
        )
    elif getattr(exc, "unreadable", False):
        print(f"  The lock file: {runs_dir / '.run.lock'}")
    else:
        print(
            "  Two overlapping runs do not present as \"two runs\": pytest needs\n"
            "  exclusive database access, so they present as FLAKY TESTS. Wait\n"
            "  for it, or stop that run."
        )


def _emit(events_path: Path, event: dict) -> None:
    """Append one JSON line to the run's event stream.

    Never raises. A feed that can break the thing it observes is worse than no
    feed at all — the same rule the plugin follows.
    """
    try:
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError:
        pass


def _run_streaming(cmd: list[str], cwd: Path, out_path: Path, timeout: int, live: bool,
                   env: dict | None = None):
    """Run a command, writing to BOTH the report file and the console.

    THE GAP THIS CLOSES: the runner wrote stdout straight to the report, so a
    ten-minute run showed nothing at all until it ended — and a run that timed
    out showed nothing, ever. The user's ask was "a switch that tells us what is
    happening", so the output is streamed line by line as it arrives: pytest's
    dots and failure lines appear live, and the file still holds the full record.

    Returns a namespace with .returncode (-1 on timeout), matching what the
    callers already expect.
    """
    started_lines: list[str] = []
    with open(out_path, "a", buffering=1) as f:
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                f.write(line)
                started_lines.append(line)
                if live:
                    # pytest writes progress without newlines; keep the cursor
                    # where it is so the dots accumulate on one line.
                    sys.stdout.write(line if line.endswith("\n") else line)
                    sys.stdout.flush()
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            msg = f"\n---\nTIMEOUT after {timeout}s — killed\n"
            f.write(msg)
            if live:
                sys.stdout.write(msg)
            return argparse.Namespace(returncode=-1)
    return argparse.Namespace(returncode=proc.returncode)


def _plugin_env(events_path: Path, backend_up: bool | None = None) -> dict:
    """The environment the test process runs in: the plugin on the path, the file it must write
    to, and THE BACKEND ANSWER the pre-flight already took.

    The plugin is INERT without the variable, so a plain `pytest` call is unaffected. The backend
    answer travels because the alternative is every xdist worker probing the same endpoint inside
    the same second — which is how a healthy backend produced 10 spurious skips under load.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PLUGIN_DIR) + (os.pathsep + existing if existing else "")
    env["COGITATE_EVENTS_FILE"] = str(events_path)
    if backend_up is not None:
        env["COGITATE_BACKEND_UP"] = "1" if backend_up else "0"
    return env


def _run_ui(args, ts: str, run_dir: Path, events: Path) -> int:
    """The frontend group — vitest (the UI's own runner).

    The event envelope is the same; there are no per-test events, because the
    per-test source (pytest's `pytest_runtest_logreport`) is pytest's alone.
    Better to say nothing finer than to invent a matching stream for a
    different runner.
    """
    frontend = ROOT / "frontend"
    report = run_dir / "report.md"

    cmd = ["npx", "vitest", "run", "--reporter=verbose"]
    print(f"[run_tests] group=ui (vitest) -> {run_dir}")
    started = datetime.datetime.now(datetime.timezone.utc)
    # The label IS the selection here: vitest chooses its own files, so the
    # fingerprint says "the ui group ran" and says nothing about which files.
    fingerprint = _fingerprint([], "ui")
    _emit(events, {
        "t": "run_start", "id": run_dir.name, "kind": "vitest", "group": "ui",
        "files": 0, "parallel": True, "backend": "n/a", "pid": os.getpid(),
        "started": started.isoformat(),
        "selection_count": 0,
        "selection_fingerprint": fingerprint,
    })
    with open(report, "w") as f:
        f.write(f"# Test run — {ts}\n")
        f.write(f"group: ui (vitest — no backend dependency)  fingerprint: {fingerprint}\n\n")
        f.flush()
    r = _run_streaming(cmd, frontend, report, args.timeout, args.live)
    elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
    with open(report, "a") as f:
        f.write(f"\n---\nELAPSED: {elapsed:.1f}s  EXIT: {r.returncode}\n")
    _emit(events, {"t": "run_end", "exit": r.returncode, "elapsed_s": round(elapsed, 1)})
    print(f"[run_tests] ui done in {elapsed:.1f}s — EXIT {r.returncode} — run: {run_dir}")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group", choices=list(GROUPS) + ["ui"], default="unit")
    ap.add_argument("--file", dest="files", action="append", default=[],
                    metavar="PATH[::TEST]",
                    help="run ONE module (or one test: path::test_name), "
                         "repeatable. Bypasses --group, so only what you name "
                         "runs — the fastest feedback loop while chasing a "
                         "failure. Accepts a backend-relative path "
                         "(tests/unit/foo.py) or a repo path.")
    ap.add_argument("--parallel", dest="parallel", action="store_true", default=None)
    ap.add_argument("--sequential", dest="parallel", action="store_false",
                    help="force one process. Slower for a GROUP; already the "
                         "default for --file, where xdist costs more than it saves.")
    ap.add_argument("--runs-dir", dest="runs_dir", default=None,
                    help="where run FOLDERS are created (default: the locator's "
                         "test-runs dir). Each run gets its own folder under it — "
                         "this is a directory, not a report path.")
    ap.add_argument("--run-id", dest="run_id", default=None,
                    help="name this run (default: the timestamp). A caller that "
                         "needs to WATCH the run — the page — passes an id so it "
                         "does not have to guess which folder appeared.")
    ap.add_argument("--clear-stale-lock", dest="clear_stale_lock", action="store_true",
                    help="remove a lock whose run is GONE (the deliberate "
                         "unblocking action; never done automatically). Refuses "
                         "if the run behind the lock is still alive.")
    ap.add_argument("--timeout", type=int, default=600,
                    help="seconds before the run is killed (default 600)")
    ap.add_argument("--require-backend", action="store_true",
                    help="fail the run when the backend is down (the strict gate)")
    ap.add_argument("--include-quarantine", action="store_true",
                    help="include the parked quarantine files (default: excluded)")
    ap.add_argument("--live", dest="live", action="store_true", default=None,
                    help="stream the run to the console as it happens (the "
                         "running log). Default: on when stdout is a terminal.")
    ap.add_argument("--no-live", dest="live", action="store_false",
                    help="write only the report file; show nothing while running")
    args = ap.parse_args()
    if args.live is None:
        args.live = sys.stdout.isatty()  # a piped run stays quiet by default

    # THE SLOW-PATH WARNING. Parallel is the default for a reason: a GROUP runs
    # minutes one way and tens of minutes the other. It is only a slow path for
    # GROUPS though — for a single named module sequential is FASTER, because
    # xdist spins a worker per core to run one file (measured: 30s parallel vs
    # 12s sequential). The `ui` group is vitest, which takes neither flag, so
    # it is excluded too.
    if args.parallel is False and not args.files and args.group != "ui":
        print(
            "[run_tests] WARNING — SEQUENTIAL run (the slow path).\n"
            "  Parallel is the default: the tools run across cores instead of one\n"
            "  file after another in a single process, so the same tests finish in\n"
            "  minutes rather than tens of minutes. Approximate, for the whole\n"
            "  backend suite: ~2-3 min parallel vs ~25-30 min sequential.\n"
            "  You want --sequential only to reproduce an ORDERING-dependent\n"
            "  failure, where the serial order IS the thing under test.\n"
            "  Otherwise just drop the flag to get the default parallel run.\n"
            "  How to run the tests, group by group, with approximate times:\n"
            "    wiki/dev-notes/testing/README.md"
        )

    ts = args.run_id or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    runs_dir = Path(args.runs_dir) if args.runs_dir else default_runs_dir()
    runs_dir = runs_dir if runs_dir.is_absolute() else ROOT / runs_dir
    acquire, release, clear_stale, RunInProgress = _the_lock()

    # THE DELIBERATE UNBLOCKING ACTION. A stale lock is never cleared for you: a
    # lock that clears itself when it feels stale can clear itself while another
    # run is starting, which is the collision it exists to prevent.
    if args.clear_stale_lock:
        try:
            stale = clear_stale(runs_dir)
        except RunInProgress as exc:
            _report_refusal(exc, runs_dir)
            return 4
        if stale is None:
            print("[run_tests] nothing to clear — no lock is held")
        else:
            print(f"[run_tests] cleared a stale lock: {stale.describe()}")
        return 0

    # THE SELECTION COMES FIRST. A bad --file path must fail before the lock is
    # taken, or a typo would hold the lock for the length of an argument check.
    if args.group == "ui":
        selection, label = [], "ui"      # vitest picks its own files
    elif args.files:
        # NAMING A MODULE IS THE VISIBILITY. An explicit path bypasses both
        # --group and the quarantine filter: run exactly what was asked for,
        # including a parked file if someone names it deliberately.
        selection = []
        for raw in args.files:
            path, sep, test = raw.partition("::")
            p = Path(path)
            if not p.is_absolute():
                # backend-relative first (tests/unit/foo.py), then repo-relative
                # (backend/tests/unit/foo.py). Absent from BOTH is "no such
                # file" — not "outside backend/", which is a different mistake.
                if (BACKEND / p).exists():
                    p = BACKEND / p
                elif (ROOT / p).exists():
                    p = ROOT / p
                else:
                    print(f"[run_tests] no such file: {path}")
                    return 2
            try:
                rel = str(p.relative_to(BACKEND))
            except ValueError:
                print(f"[run_tests] {path}: is not inside backend/ — nothing to run")
                return 2
            selection.append(f"{rel}::{test}" if sep else rel)
        label = "files"
    else:
        selection = _select(args.group, args.include_quarantine)
        label = args.group
        if not selection:
            print(f"[run_tests] no files for group={args.group}")
            return 2

    # THE BACKEND PRE-FLIGHT (the 2026-08-27 decision): the harness
    # checks BEFORE pytest — the report's header carries the stamp;
    # --require-backend fails the run early.
    import urllib.request
    backend_up = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2) as resp:
            backend_up = resp.status == 200
    except Exception:
        backend_up = False
    if args.require_backend and not backend_up:
        print("[run_tests] --require-backend set and the backend is DOWN — aborting")
        return 3

    # THE PARALLELISM DEFAULT. xdist pays a worker-startup cost per invocation
    # that only earns itself back when there is real work to spread: a GROUP is
    # minutes of work, so parallel wins; a handful of named modules is seconds,
    # so serial wins (measured for two modules: 14s serial vs 29s parallel).
    # An explicit --parallel or --sequential overrides either way.
    if args.parallel is None:
        use_parallel = not args.files
    else:
        use_parallel = args.parallel

    run_dir = _next_run_dir(runs_dir, ts) if not args.run_id else runs_dir / args.run_id
    if args.run_id:
        # A NAMED RUN MEANS EXACTLY THAT NAME. The caller watches this id, so a
        # collision must be an error rather than a silent suffix — the page would
        # otherwise stream a run it did not start.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
            print(f"[run_tests] --run-id {args.run_id!r} is not a plain name "
                  "(letters, digits, dot, dash, underscore)")
            return 2
        if run_dir.exists():
            print(f"[run_tests] --run-id {args.run_id} is already taken")
            return 2
    events = run_dir / "events.jsonl"
    # WHO started this run is DATA, not a guess: the page reads it out of the
    # lock to say "a run is in progress — started outside this page at 09:14".
    origin = os.environ.get("COGITATE_RUN_ORIGIN") or "terminal"

    # THE LOCK, AND THE SENTENCE. One run at a time; a second attempt is told
    # what it collided with rather than failing as mysterious flakiness later.
    try:
        acquire(runs_dir, run_dir.name, origin=origin)
    except RunInProgress as exc:
        _report_refusal(exc, runs_dir)
        return 4

    # A CANCEL MUST NOT LEAVE A LOCK BEHIND. Installed after the lock is taken
    # and before any work starts, so a SIGTERM anywhere in the run ends orderly.
    try:
        signal.signal(signal.SIGTERM, _on_term)
    except ValueError:
        pass  # not the main thread (a caller embedding this) — nothing to do

    try:
        run_dir.mkdir(parents=True, exist_ok=False)
        if args.group == "ui":
            return _run_ui(args, ts, run_dir, events)
        return _run_pytest(args, ts, run_dir, events, selection, label,
                           use_parallel, backend_up)
    finally:
        release(runs_dir, run_dir.name)


def _on_term(signum, frame):
    """Turn a CANCEL into an orderly exit, so the `finally` above releases the
    lock.

    Without this, SIGTERM kills the interpreter outright: the lock file survives
    its owner, and the next run refuses until somebody clears it. The kill is
    legitimate — the run is being stopped on purpose — so it should end cleanly.
    """
    raise SystemExit(130)


def _run_pytest(args, ts: str, run_dir: Path, events: Path, selection: list[str],
                label: str, use_parallel: bool, backend_up: bool) -> int:
    """The backend groups: pytest, one run folder, three artifacts."""
    cmd = [
        str(ROOT / ".venv" / "bin" / "python3"),
        "-m", "pytest",
        *selection,
        "-q", "--durations=15", "--tb=short",
        # -rf: a clean, greppable FAILED list in the report. Without it the
        # report holds dots and tracebacks, and the failure NAMES have to be
        # dug out of the middle - which is how a 66-failure run reads as "~10".
        "-rf",
        # THE STRUCTURED RESULT. Written when the session ENDS, which is why it
        # answers "what did each test do" and never "what is happening".
        f"--junitxml={run_dir / 'report.xml'}",
        # THE LIVE RECORD. The plugin is inert without COGITATE_EVENTS_FILE.
        "-p", EVENTS_PLUGIN,
    ]
    if use_parallel:
        cmd += ["-n", "auto"]

    report = run_dir / "report.md"
    print(f"[run_tests] group={label} parallel={use_parallel} "
          f"files={len(selection)} -> {run_dir}")
    started = datetime.datetime.now(datetime.timezone.utc)
    fingerprint = _fingerprint(selection, label)
    _emit(events, {
        "t": "run_start", "id": run_dir.name, "kind": "pytest", "group": label,
        "files": len(selection), "parallel": use_parallel,
        "backend": "healthy" if backend_up else "down",
        "pid": os.getpid(), "started": started.isoformat(),
        "selection": selection[:50],
        # WHAT WAS SELECTED, provably. `selection` is capped at 50 entries, so the
        # count and the hash are what let a LATER run be compared against this one.
        "selection_count": len(selection),
        "selection_fingerprint": fingerprint,
    })
    with open(report, "w") as f:
        f.write(f"# Test run — {ts}\n")
        f.write(f"group: {label}  parallel: {use_parallel}  files: {len(selection)}"
                f"  fingerprint: {fingerprint}\n")
        f.write(f"backend: {'healthy' if backend_up else 'DOWN — the backend-marked tests will skip'}\n\n")
        f.flush()
    r = _run_streaming(cmd, BACKEND, report, args.timeout, args.live,
                       env=_plugin_env(events, backend_up))
    elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
    with open(report, "a") as f:
        f.write(f"\n---\nELAPSED: {elapsed:.1f}s  EXIT: {r.returncode}\n")
    _emit(events, {"t": "run_end", "exit": r.returncode, "elapsed_s": round(elapsed, 1)})
    print(f"[run_tests] done in {elapsed:.1f}s — EXIT {r.returncode} — run: {run_dir}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
