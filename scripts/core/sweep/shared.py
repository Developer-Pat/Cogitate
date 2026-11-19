#!/usr/bin/env python3
"""
Shared utilities for the sweep package.

Extracted from the monolithic sweep.py to support separate backend/frontend
subcommands with independent reports.
"""

import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


def _locator_dir(field: str, fallback: Path) -> Path:
    """Resolve a canonical dir from the app's locator (`Paths`).

    ONE authority for where things live. The sweep asks `Paths` instead of
    repeating the path — two copies of one location is the drift class the
    locator exists to end (and it is how every report ended up in `local/`,
    which does not exist in an installation).

    The fallback keeps the sweep runnable on an interpreter that cannot import
    the app; it is the same value the locator declares.
    """
    try:
        import sys

        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))
        from app.core.config import Paths

        return Path(getattr(Paths, field))
    except Exception:
        return fallback


#: The sweep's OWN output — system space, deliberately apart from the test runs
#: a person makes (design §1: the chain machine is not the workbench).
REPORTS_DIR = _locator_dir("sweep_dir", REPO_ROOT / "data" / "sweep")
BASELINE_PATH = REPORTS_DIR / "sweep-baseline.md"

OUTPUT_CHAR_LIMIT = 8000


def timestamp() -> str:
    """Return a human-readable UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def file_timestamp() -> str:
    """Return a file-safe UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ── Command execution ────────────────────────────────────────────────────────


def run_cmd(cmd, cwd, label, timeout=300):
    """Run a command and return (returncode, stdout+stderr)."""
    print(f"\n{'='*70}")
    print(f"  [{label}] Running: {' '.join(cmd)}")
    print(f"{'='*70}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        # Print truncated output inline
        lines = output.splitlines()
        if len(lines) > 50:
            print("\n".join(lines[:50]))
            print(f"  ... ({len(lines) - 50} more lines, see report for full output)")
        else:
            print(output)
        print(f"  [EXIT CODE: {result.returncode}]")
        return result.returncode, output
    except subprocess.TimeoutExpired:
        msg = f"[TIMEOUT after {timeout}s]"
        print(f"  {msg}")
        return -1, msg
    except FileNotFoundError as e:
        msg = f"[NOT FOUND: {e}]"
        print(f"  {msg}")
        return -2, msg


# ── Parallel execution helpers ───────────────────────────────────────────────


def _run_check(check_fn, label):
    """Wrapper to run a single check function and return a result dict."""
    t0 = time.time()
    rc, out = check_fn()
    return {"label": label, "returncode": rc, "output": out, "duration": time.time() - t0}


def run_parallel(checks: list[tuple]) -> list[dict]:
    """Run a list of (check_fn, label) tuples in parallel via ThreadPoolExecutor.

    Each check_fn is a zero-argument callable that returns (returncode, output).
    Returns a list of result dicts in the order the checks were submitted.
    """
    results: list[dict | None] = [None] * len(checks)
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        future_map = {}
        for i, (check_fn, label) in enumerate(checks):
            future = executor.submit(_run_check, check_fn, label)
            future_map[future] = i

        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {
                    "label": checks[idx][1],
                    "returncode": -3,
                    "output": f"[EXCEPTION: {e}]",
                    "duration": 0.0,
                }
    return results


# ── tsc error parsing ────────────────────────────────────────────────────────


def parse_tsc_per_file(text: str) -> dict[str, int]:
    """Parse tsc output into a dict of {file_path: error_count}, sorted descending."""
    counts: dict[str, int] = {}
    for line in text.splitlines():
        # tsc error format: "src/path/to/file.ts(line,col): error TS1234: message"
        if "error TS" in line or "error  TS" in line:
            # Extract file path (everything before the first parenthesis)
            file_path = line.split("(")[0].strip()
            if file_path:
                counts[file_path] = counts.get(file_path, 0) + 1
    # Sort descending by count
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ── Report generation ────────────────────────────────────────────────────────


def write_report(results, output_path, full_output=False, scope_label="full"):
    """Write a structured markdown report.

    Args:
        results: List of result dicts from checks.
        output_path: Path to write the report to.
        full_output: If True, include complete raw output (no truncation).
        scope_label: Label for the report scope (e.g. "full", "backend", "frontend").
    """
    total_checks = len(results)
    passed = sum(1 for r in results if r["returncode"] == 0)
    failed = total_checks - passed

    lines = []
    lines.append(f"# Sweep Report — {scope_label.title()} Checks\n")
    lines.append(f"**Generated:** {timestamp()}\n")
    lines.append(f"**Repository root:** `{REPO_ROOT}`\n")
    lines.append(f"**Scope:** {scope_label}\n")
    lines.append(f"**Checks run:** {total_checks} | **Passed:** {passed} | **Failed:** {failed}\n")
    lines.append("---\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| # | Check | Status | Exit Code |")
    lines.append("|---|-------|--------|-----------|")
    for i, r in enumerate(results, 1):
        status = "✅ PASS" if r["returncode"] == 0 else "❌ FAIL"
        lines.append(f"| {i} | {r['label']} | {status} | {r['returncode']} |")
    lines.append("")

    # Detailed results
    lines.append("---\n")
    lines.append("## Detailed Results\n")

    for r in results:
        status = "✅ PASSED" if r["returncode"] == 0 else "❌ FAILED"
        lines.append(f"### {r['label']} — {status} (exit: {r['returncode']})\n")
        lines.append(f"**Duration:** {r['duration']:.1f}s\n")

        # For tsc failures, add a per-file error summary table
        if r["returncode"] != 0 and ("tsc" in r["label"].lower()):
            per_file = parse_tsc_per_file(r["output"])
            if per_file:
                total_errs = sum(per_file.values())
                lines.append(f"**Error breakdown:** {total_errs} errors across {len(per_file)} files\n\n")
                lines.append("| File | Errors |")
                lines.append("|------|:------:|")
                for file_path, count in per_file.items():
                    lines.append(f"| `{file_path}` | {count} |")
                lines.append("")

        # Raw output (capped to protect context window)
        raw_output = r["output"].rstrip()
        if len(raw_output) > OUTPUT_CHAR_LIMIT and not full_output:
            lines.append(f"> ⚠️ Output truncated to {OUTPUT_CHAR_LIMIT} characters "
                         f"({len(raw_output)} total). Use `--full-output` for complete output.\n")
            lines.append("```")
            lines.append(raw_output[:OUTPUT_CHAR_LIMIT])
            lines.append("```\n")
        else:
            lines.append("```")
            lines.append(raw_output)
            lines.append("```\n")

    # Error summary
    failures = [r for r in results if r["returncode"] != 0]
    if failures:
        lines.append("---\n")
        lines.append("## Failed Checks Summary\n")
        lines.append("| Check | Exit Code | Key Issues |")
        lines.append("|-------|-----------|------------|")
        for r in failures:
            # Extract first few lines of actual errors
            output_lines = r["output"].splitlines()
            error_lines = [
                l.strip() for l in output_lines
                if any(kw in l.lower() for kw in ["error", "warning", "traceback", "failure"])
                and not l.startswith("  [")
            ][:5]
            key_issues = "; ".join(error_lines[:3]) if error_lines else "(see full output)"
            lines.append(f"| {r['label']} | {r['returncode']} | {key_issues[:120]} |")
        lines.append("")

    lines.append("---\n")
    lines.append(f"*Report generated by `scripts/core/sweep/` at {timestamp()}*\n")

    report = "\n".join(lines)
    output_path.write_text(report)
    return report


def roll_baseline():
    """Roll the existing baseline to a timestamped archive before overwriting."""
    if BASELINE_PATH.exists():
        archive_name = f"sweep-baseline-{file_timestamp()}.md"
        archive_path = REPORTS_DIR / archive_name
        shutil.copy2(str(BASELINE_PATH), str(archive_path))
        print(f"  📋 Archived previous baseline: {archive_path}")
    else:
        print(f"  📋 No existing baseline to archive")
