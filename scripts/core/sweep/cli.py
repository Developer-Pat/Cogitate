#!/usr/bin/env python3
"""
CLI dispatcher for the sweep package.

Provides subcommands:
    sweep.py backend   — Run backend checks only (separate report)
    sweep.py frontend  — Run frontend checks only (separate report)
    sweep.py full      — Run all checks (default, combined report)

Each subcommand generates its own separate report file.

Legacy flags (--backend-only, --frontend-only) are deprecated and
will emit a warning. Use the subcommand form instead.
"""

import argparse
import time
from pathlib import Path

from sweep.shared import (
    REPORTS_DIR,
    file_timestamp,
    _run_check,
    run_parallel,
    write_report,
    roll_baseline,
)
from sweep import backend as be
from sweep import frontend as fe


def run_backend_checks(args):
    """Run all backend checks and return results list."""
    results = []

    if getattr(args, "test_group", None):
        be.TEST_GROUP = args.test_group

    if args.parallel:
        # Run quick backend checks in parallel, then pytest separately
        results.extend(run_parallel(be.get_parallel_checks(include_slow=args.include_slow)))
        # pytest must run alone (DB state)
        results.append(_run_check(*be.get_pytest_check(include_slow=args.include_slow)))
    else:
        for check_fn, label in be.get_all_checks(include_slow=args.include_slow):
            t0 = time.time()
            rc, out = check_fn()
            results.append({"label": label, "returncode": rc, "output": out, "duration": time.time() - t0})

    return results


def run_frontend_checks(args):
    """Run all frontend checks and return results list."""
    results = []

    if getattr(args, "test_group", None):
        be.TEST_GROUP = args.test_group

    if args.parallel:
        # All frontend checks are independent — run them in parallel
        results.extend(run_parallel(fe.get_all_checks()))
    else:
        for check_fn, label in fe.get_all_checks():
            t0 = time.time()
            rc, out = check_fn()
            results.append({"label": label, "returncode": rc, "output": out, "duration": time.time() - t0})

    return results


def _prune_old_reports(reports_dir, keep: int) -> None:
    """Prune sweep reports beyond the newest `keep`.

    Only touches the sweep-backend-*.md pattern (the auto-generated
    reports). Human docs (llm-wiki-feasibility.md etc.) + the
    baseline are never pruned.
    """
    import re
    reports = sorted(
        (p for p in reports_dir.glob("sweep-backend-*.md")),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in reports[keep:]:
        try:
            old.unlink()
            print(f"  (pruned old report: {old.name})")
        except OSError:
            pass


def cmd_backend(args):
    """Handle the 'backend' subcommand."""
    print(f"\n{'#'*70}")
    print(f"  SWEEP: Backend Checks Only")
    print(f"  Started: {timestamp()}")
    print(f"  Parallel: {'YES' if args.parallel else 'NO'}")
    print(f"{'#'*70}\n")

    if args.roll_baseline:
        roll_baseline()

    results = run_backend_checks(args)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else REPORTS_DIR / f"sweep-backend-{file_timestamp()}.md"
    report = write_report(results, output_path, full_output=args.full_output, scope_label="backend")

    # retention: keep the newest N sweep reports (the launch-plan's
    # lean-repo discipline — sweep reports are machine logs; the roll
    # to _archive/reports/ is a manual dated move, like sessions)
    _prune_old_reports(REPORTS_DIR, keep=getattr(args, "keep", 10))

    _print_summary(results, output_path)

    if args.roll_baseline:
        _save_baseline(output_path)

    return 0 if sum(1 for r in results if r["returncode"] == 0) == len(results) else 1


def cmd_frontend(args):
    """Handle the 'frontend' subcommand."""
    print(f"\n{'#'*70}")
    print(f"  SWEEP: Frontend Checks Only")
    print(f"  Started: {timestamp()}")
    print(f"  Parallel: {'YES' if args.parallel else 'NO'}")
    print(f"{'#'*70}\n")

    if args.roll_baseline:
        roll_baseline()

    results = run_frontend_checks(args)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else REPORTS_DIR / f"sweep-frontend-{file_timestamp()}.md"
    report = write_report(results, output_path, full_output=args.full_output, scope_label="frontend")

    _print_summary(results, output_path)

    if args.roll_baseline:
        _save_baseline(output_path)

    return 0 if sum(1 for r in results if r["returncode"] == 0) == len(results) else 1


def cmd_full(args):
    """Handle the 'full' subcommand — run all checks."""
    print(f"\n{'#'*70}")
    print(f"  SWEEP: All Checks")
    print(f"  Started: {timestamp()}")
    print(f"  Parallel: {'YES' if args.parallel else 'NO'}")
    print(f"{'#'*70}\n")

    if args.roll_baseline:
        roll_baseline()

    results = []
    results.extend(run_backend_checks(args))
    results.extend(run_frontend_checks(args))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else REPORTS_DIR / f"sweep-report-{file_timestamp()}.md"
    report = write_report(results, output_path, full_output=args.full_output, scope_label="full")

    _print_summary(results, output_path)

    if args.roll_baseline:
        _save_baseline(output_path)

    return 0 if sum(1 for r in results if r["returncode"] == 0) == len(results) else 1


def _print_summary(results, output_path):
    """Print a summary of results to stdout."""
    passed = sum(1 for r in results if r["returncode"] == 0)
    total = len(results)
    print(f"\n{'#'*70}")
    print(f"  SWEEP COMPLETE")
    print(f"  Report: {output_path}")
    print(f"  Results: {passed}/{total} checks passed")
    print(f"{'#'*70}\n")


def _save_baseline(output_path):
    """Save the report as the new baseline."""
    from sweep.shared import BASELINE_PATH
    import shutil
    try:
        shutil.copy2(str(output_path), str(BASELINE_PATH))
        print(f"  📋 New baseline saved: {BASELINE_PATH}")
    except Exception as e:
        print(f"  ⚠️  Failed to save baseline: {e}")


def timestamp():
    """Return a human-readable UTC timestamp string."""
    from sweep.shared import timestamp as ts
    return ts()


def build_parser():
    """Build the argument parser with subcommands as the primary interface."""
    parser = argparse.ArgumentParser(
        description="Sweep for errors and warnings — backend, frontend, or full"
    )

    subparsers = parser.add_subparsers(dest="command", help="Scope of checks to run")

    # --- backend subcommand ---
    bp = subparsers.add_parser("backend", help="Run backend checks only (separate report)")
    bp.add_argument("--output", default=None, help="Custom output report path")
    bp.add_argument("--include-slow", action="store_true", help="Include slow/integration tests")
    bp.add_argument(
        "--test-group",
        default=None,
        choices=["unit", "workflows", "api", "components", "integration", "e2e", "all"],
        help="The test GROUP to run (the PHASED sweep). Default: unit. "
             "The groups are the runner's directory partitions, so a full run is "
             "never required - e.g. --test-group workflows.",
    )
    bp.add_argument("--full-output", action="store_true",
                    help="Include complete raw output (default: capped at 8000 chars per check)")
    bp.add_argument("--roll-baseline", action="store_true",
                    help="Roll the previous baseline to a timestamped archive, then save the new report as the baseline")
    bp.add_argument("--parallel", action="store_true",
                    help="Run independent checks in parallel to reduce total wall-clock time")
    bp.add_argument("--keep", type=int, default=10,
                    help="Keep the newest N sweep reports, prune the rest (default: 10)")

    # --- frontend subcommand ---
    fp = subparsers.add_parser("frontend", help="Run frontend checks only (separate report)")
    fp.add_argument("--output", default=None, help="Custom output report path")
    fp.add_argument("--full-output", action="store_true",
                    help="Include complete raw output (default: capped at 8000 chars per check)")
    fp.add_argument("--roll-baseline", action="store_true",
                    help="Roll the previous baseline to a timestamped archive, then save the new report as the baseline")
    fp.add_argument("--parallel", action="store_true",
                    help="Run independent checks in parallel to reduce total wall-clock time")

    # --- full subcommand ---
    fullp = subparsers.add_parser("full", help="Run all checks (backend + frontend, combined report)")
    fullp.add_argument("--output", default=None, help="Custom output report path")
    fullp.add_argument("--include-slow", action="store_true", help="Include slow/integration tests")
    fullp.add_argument("--full-output", action="store_true",
                       help="Include complete raw output (default: capped at 8000 chars per check)")
    fullp.add_argument("--roll-baseline", action="store_true",
                       help="Roll the previous baseline to a timestamped archive, then save the new report as the baseline")
    fullp.add_argument("--parallel", action="store_true",
                       help="Run independent checks in parallel to reduce total wall-clock time")
    fullp.add_argument("--keep", type=int, default=10,
                       help="Keep the newest N sweep reports, prune the rest (default: 10)")

    # Legacy flags — deprecated, emit warning when used
    parser.add_argument("--backend-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--frontend-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--include-slow", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--full-output", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--roll-baseline", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--parallel", action="store_true", help=argparse.SUPPRESS)

    return parser


def main():
    """Main entry point for the sweep CLI."""
    parser = build_parser()
    args = parser.parse_args()

    # Map legacy flags to subcommands with deprecation warning
    if args.command is None:
        if args.backend_only:
            print("⚠️  DEPRECATED: --backend-only flag. Use 'sweep.py backend' instead.\n")
            args.command = "backend"
        elif args.frontend_only:
            print("⚠️  DEPRECATED: --frontend-only flag. Use 'sweep.py frontend' instead.\n")
            args.command = "frontend"
        else:
            args.command = "full"

    if args.command == "backend":
        return cmd_backend(args)
    elif args.command == "frontend":
        return cmd_frontend(args)
    elif args.command == "full":
        return cmd_full(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
