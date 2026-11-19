#!/usr/bin/env python3
"""Verify the test harness reports (and stops) its own installation leaks.

Four halves, because each one alone is a false green:

  1. FORCED FAILURE — a sandbox that cannot be removed raises the warning and
     the message NAMES the file that held it. (A check that has never fired is
     not a check.)
  2. QUIET HEALTHY PATH — an ordinary removal raises nothing and leaves
     nothing. (A checker that fires on healthy input reads as a finding.)
  3. END-TO-END — a real `pytest --collect-only` creates a root, and no root
     survives it. This is the LEAK PATH THE FIXTURE NEVER COVERED: the root is
     made at import and the cleanup runs at interpreter exit, whether or not
     any test ever asked for the database fixture.
  4. REVERT CHECK (`--revert-check`) — with the conftest change stashed, the
     same end-to-end run DOES leave a root. Proves step 3 can go red.

Run from anywhere:  .venv/bin/python scripts/verify_test_harness_cleanup.py
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
CONFTEST = os.path.join(BACKEND, "tests", "conftest.py")
PYTEST = os.path.join(ROOT, ".venv", "bin", "python")

# The plugin that makes step 3's positive control possible: it writes down every
# TEST_ROOT each process created, so "no root survived" cannot be a run that
# never made one.
PROBE_PLUGIN = '''
import os


def pytest_sessionstart(session):
    for plugin in session.config.pluginmanager.get_plugins():
        root = getattr(plugin, "TEST_ROOT", None)
        if isinstance(root, str) and "cogitate-test-" in root:
            with open(os.environ["LEAK_PROBE_LOG"], "a") as fh:
                fh.write(root + "\\n")
'''


def _live_roots() -> set[str]:
    return set(glob.glob("/tmp/cogitate-test-*"))


def _load_conftest():
    """Import backend/tests/conftest.py under its own name.

    It is a pytest plugin, not a module — importing it is what a test process
    does, and it is the only way to reach `_cleanup_test_db` and TEST_ROOT.
    """
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    spec = importlib.util.spec_from_file_location("cogitate_conftest_probe", CONFTEST)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def part1_forced_failure(mod) -> None:
    root = mod.TEST_ROOT
    assert os.path.isdir(root), f"the installation does not exist: {root}"

    # A directory that cannot be emptied: r-x lets the walk SEE the file and
    # refuses to unlink it, so the removal stops there and names it. (A held-open
    # handle does NOT do this on Linux — unlink of an open file succeeds — so
    # forcing it needs a real refusal, not a held fd.)
    blocker = os.path.join(root, "held-by-a-handle")
    os.makedirs(blocker, exist_ok=True)
    with open(os.path.join(blocker, "blocker.txt"), "w") as fh:
        fh.write("held")
    os.chmod(blocker, 0o555)

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            mod._cleanup_test_db()

        leaks = [w for w in caught if isinstance(w.message, mod.TestInstallationLeakWarning)]
        assert leaks, f"no leak warning raised (caught: {[str(w.message) for w in caught]})"
        msg = str(leaks[0].message)
        assert root in msg, f"the message does not name the installation: {msg}"
        assert "held-by-a-handle" in msg, f"the message does not name the holder: {msg}"
        assert os.path.isdir(root), "the sandbox was removed after all — nothing was forced"
        print(f"[1] forced failure  OK  warning names the holder:\n      {msg.splitlines()[0]}")
    finally:
        os.chmod(blocker, 0o755)
        shutil.rmtree(root, ignore_errors=True)


def part2_quiet_healthy(mod) -> None:
    quiet = tempfile.mkdtemp(prefix="cogitate-test-quiet-")
    with open(os.path.join(quiet, "ordinary.txt"), "w") as fh:
        fh.write("nothing is holding this")
    # TEST_ROOT is read at CALL time — set the module attribute, do not rebind a
    # local (a probe that captured the value at import would measure a snapshot).
    mod.TEST_ROOT = quiet
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mod._cleanup_test_db()

    leaks = [w for w in caught if isinstance(w.message, mod.TestInstallationLeakWarning)]
    assert not leaks, f"the healthy path raised a leak warning: {leaks[0].message}"
    assert not os.path.exists(quiet), f"the healthy removal left the root behind: {quiet}"
    print("[2] quiet healthy   OK  removed, nothing raised")


def _collect_run() -> tuple[list[str], subprocess.CompletedProcess]:
    """Run `pytest tests/unit --collect-only`, returning the roots it created.

    The probe plugin writes down every TEST_ROOT each process created — without
    it, "no root survived" is indistinguishable from a run that never made one.
    """
    log = tempfile.NamedTemporaryFile("w", prefix="leak-probe-", suffix=".log", delete=False)
    log.close()
    probe_dir = tempfile.mkdtemp(prefix="leak-probe-plugin-")
    with open(os.path.join(probe_dir, "leak_probe_plugin.py"), "w") as fh:
        fh.write(PROBE_PLUGIN)

    env = dict(os.environ, LEAK_PROBE_LOG=log.name, PYTHONPATH=probe_dir)
    proc = subprocess.run(
        [PYTEST, "-m", "pytest", "tests/unit", "--collect-only", "-q",
         "-p", "leak_probe_plugin", "-p", "no:cacheprovider"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    created = [ln.strip() for ln in open(log.name) if ln.strip()]
    os.unlink(log.name)
    shutil.rmtree(probe_dir, ignore_errors=True)
    return created, proc


def part3_end_to_end() -> None:
    before = _live_roots()
    created, proc = _collect_run()

    assert proc.returncode == 0, f"the collection run failed:\n{proc.stdout[-2000:]}"
    # THE HARNESS-OK LINE. Without it, "no root survived" is indistinguishable
    # from a run that never created one.
    assert created, "HARNESS: the run created no TEST_ROOT at all — the probe or the import failed"
    survivors = sorted(p for p in created if os.path.exists(p))
    assert not survivors, "the run left roots behind: " + ", ".join(survivors)
    print(f"[3] end-to-end      OK  {len(created)} root(s) created, 0 survived "
          f"({len(_live_roots() - before)} new in /tmp)")
    print(f"      collected: {proc.stdout.strip().splitlines()[-1]}")


def part4_revert_check() -> None:
    """With the change stashed, the same run leaks — so step 3 can go red."""
    def _git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)

    marker = "atexit.register(_cleanup_test_db)"
    assert marker in open(CONFTEST).read(), "the fix is not in place before the revert"
    assert _git("stash", "push", "--", "backend/tests/conftest.py").returncode == 0, "stash failed"
    try:
        # PROVE THE MUTATION TOOK: a stash that silently left the fix in place
        # would make the run below green for the wrong reason.
        assert marker not in open(CONFTEST).read(), "the stash did not remove the fix"
        created, _ = _collect_run()
        new = sorted(p for p in created if os.path.exists(p))
        assert new, "the pre-fix tree left NO root — the check cannot see this leak"
        for p in new:
            shutil.rmtree(p, ignore_errors=True)
        print(f"[4] revert check    OK  pre-fix tree leaked {len(new)} root(s): {new[0]}")
    finally:
        assert _git("stash", "pop").returncode == 0, "STASH POP FAILED — restore the conftest by hand"
        assert marker in open(CONFTEST).read(), "the fix did not come back after the revert check"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--revert-check", action="store_true",
                    help="also prove the end-to-end check can go RED (stashes the fix)")
    args = ap.parse_args()

    mod = _load_conftest()
    part1_forced_failure(mod)
    part2_quiet_healthy(mod)
    part3_end_to_end()
    if args.revert_check:
        part4_revert_check()
        # The stash cycle reloads nothing; re-run the green half on the restored tree.
        part3_end_to_end()
    print("\nALL VERIFICATIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
