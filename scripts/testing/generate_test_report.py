#!/usr/bin/env python3
"""
Test Report Generator — run both suites and produce a timestamped markdown report.

Default mode is the fast "light scan". Use `--full-sweep` for the complete suite.

Usage:
    python3 scripts/testing/generate_test_report.py                     # light scan (default, ~2 min)
    python3 scripts/testing/generate_test_report.py --medium             # medium scan (excludes slow only)
    python3 scripts/testing/generate_test_report.py --full-sweep         # full sweep (~5-6 min)
    python3 scripts/testing/generate_test_report.py --output report.md   # custom output path

Output is written to backend/reports/test-report-{date}.md by default.
This directory is gitignored — reports are never committed.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "backend" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── helpers ──────────────────────────────────────────────────────────────


def _fmt_delta(seconds: float) -> str:
    """Format a duration in seconds to a human-friendly string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = seconds % 60
    if mins < 60:
        return f"{mins}m {secs:.0f}s"
    hours = mins // 60
    mins = mins % 60
    return f"{hours}h {mins}m {secs:.0f}s"


def _run(cmd: list[str], cwd: Path, label: str, timeout: int = 600) -> dict:
    """Run a command, capture output, and return structured results."""
    print(f"  → {label} ... ", end="", flush=True)
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
        print(f"done ({_fmt_delta(elapsed)})")
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed": elapsed,
            "started": started,
        }
    except subprocess.TimeoutExpired:
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
        print(f"TIMEOUT after {_fmt_delta(elapsed)}")
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "elapsed": elapsed,
            "started": started,
        }
    except FileNotFoundError:
        print("SKIPPED (command not found)")
        return {
            "returncode": -2,
            "stdout": "",
            "stderr": f"Command not found: {cmd[0]}",
            "elapsed": 0.0,
            "started": started,
        }


def _parse_pytest_summary(text: str) -> dict:
    """Extract pass/fail/skip/warn counts from pytest summary line."""
    result = {"passed": 0, "failed": 0, "skipped": 0, "warnings": 0, "deselected": 0, "errors": 0}
    # Match: "703 passed, 10 skipped, 1 deselected" or "9 failed, 703 passed, 10 skipped, 1 deselected"
    m = re.search(
        r"(?P<failed>\d+)\s+failed\s*|(?P<passed>\d+)\s+passed\s*|(?P<skipped>\d+)\s+skipped\s*|(?P<deselected>\d+)\s+deselected\s*|(?P<errors>\d+)\s+error",
        text,
    )
    if not m:
        # Try simpler: "1 passed" etc
        m = re.search(r"=+ ([0-9, ]+passed[^=]*) =+", text)
        if m:
            summary = m.group(1)
        else:
            return result
    else:
        summary = text

    for key in result:
        m2 = re.search(rf"(\d+)\s+{key}", summary)
        if m2:
            result[key] = int(m2.group(1))

    # Extract warning count from "= warnings summary ==" section
    warn_match = re.search(r"=+\s*warnings summary\s*=+\s+\n\n(.*?)(?:\n--|\Z)", text, re.DOTALL)
    if warn_match:
        warn_count = warn_match.group(1).strip().count("::")
        result["warnings"] = warn_count

    return result


def _parse_failed_tests(text: str) -> list[str]:
    """Extract names of failed tests from pytest output."""
    failed = []
    lines = text.splitlines()
    in_summary = False
    for line in lines:
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            stripped = line.strip()
            if stripped.startswith("FAILED "):
                failed.append(stripped.replace("FAILED ", "", 1))
    return failed


# ─── failure classification ──────────────────────────────────────────────


def _classify_failure(test_name: str, stdout: str, stderr: str) -> str:
    """Classify a test failure as 'connection', 'code', or 'unknown'.

    Uses two strategies:
    1. File-path heuristic — tests under ``tests/e2e/`` are connection failures.
    2. Content scan — search the full stderr for connection-level error
       patterns, which indicates the test requires a running backend.

    Falls back to checking for common code-level indicators otherwise.
    """
    # --- Strategy 1: path-based --------------------------------
    if test_name.startswith("tests/e2e/") or "/e2e/" in test_name:
        return "connection"

    combined = stdout + "\n" + stderr

    # --- Strategy 2: full-output scan for connection errors -----
    connection_patterns = [
        "ConnectError",
        "ConnectionRefusedError",
        "All connection attempts failed",
        "Cannot connect to host",
        "NewConnectionError",
        "RemoteProtocolError",
    ]
    for pattern in connection_patterns:
        if pattern.lower() in combined.lower():
            return "connection"

    # --- Fallback: common code-level indicators -----------------
    code_patterns = [
        "AssertionError",
        "pytest.fail",
        "template_id is required",
        "compile_workflow",
        "ModuleNotFoundError",
        "ImportError",
        "TypeError",
        "ValueError",
        "KeyError",
        "AttributeError",
        "SyntaxError",
        "IndentationError",
    ]
    for pattern in code_patterns:
        if pattern.lower() in combined.lower():
            return "code"

    return "unknown"


def _parse_vitest_summary(text: str) -> dict:
    """Extract pass/fail counts from vitest output."""
    result = {"passed": 0, "failed": 0, "files": 0, "duration": 0.0}
    # "Test Files  28 passed (28)"
    m = re.search(r"Test\s+Files\s+(\d+)\s+passed.*\((\d+)\)", text)
    if m:
        result["files"] = int(m.group(2))

    # "Tests  491 passed (491)"
    m = re.search(r"Tests\s+(\d+)\s+passed", text)
    if m:
        result["passed"] = int(m.group(1))

    # "Tests  491 passed (491)" / "Tests  489 passed, 2 failed (491)"
    m = re.search(r"Tests\s+.+?(\d+)\s+failed", text)
    if m:
        result["failed"] = int(m.group(1))

    # "Duration  5.26s"
    m = re.search(r"Duration\s+([\d.]+)s", text)
    if m:
        result["duration"] = float(m.group(1))

    return result


def _format_dashboard(b: dict, f: dict) -> str:
    """Build a status dashboard markdown table."""
    rows = []

    def row(cat, count, target, status):
        emoji = "✅" if status else ("⚠️" if "0" in str(count) else "❌")
        rows.append(f"| {cat} | {count} | {target} | {emoji} |")

    row("**pytest (backend)**", f"{b['passed']} pass, {b['skipped']} skip", "0 fail", b["failed"] == 0)
    row("**Vitest (frontend)**", f"{f['passed']} pass", "0 failures", f["failed"] == 0)

    return "\n".join(rows)


# ─── main ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a test-suite markdown report")
    parser.add_argument(
        "--full-sweep",
        action="store_true",
        help="Full sweep: run all tests (default is light scan, ~5-6 min)",
    )
    parser.add_argument(
        "--medium",
        action="store_true",
        help="Medium scan: exclude @pytest.mark.slow only (includes all vitest)",
    )
    parser.add_argument(
        "--light",
        action="store_true",
        help="Light scan: explicit alias for the default behavior",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output path (default: backend/reports/test-report-{date}.md)",
    )
    args = parser.parse_args()

    scan_mode = "light-scan"
    if args.full_sweep:
        scan_mode = "full-sweep"
    elif args.medium:
        scan_mode = "medium-scan"

    now = datetime.datetime.now(datetime.timezone.utc)
    local_now = now.astimezone()
    date_str = now.strftime("%Y-%m-%d")
    timestamp = local_now.strftime("%Y-%m-%d %H:%M:%S %Z")

    output_path = args.output
    if not output_path:
        output_path = str(REPORTS_DIR / f"test-report-{date_str}.md")

    print(f"╔══ Test Report Generator ══╗")
    print(f"  Mode:      {scan_mode}")
    print(f"  Timestamp: {timestamp}")
    print(f"  Output:    {output_path}")
    print()

    # ── 1. Run backend pytest ──────────────────────────────────────────
    print("[1/2] Backend pytest")
    backend_dir = PROJECT_ROOT / "backend"
    if args.full_sweep:
        # Full sweep: everything
        pytest_cmd = [
            "uv", "run", "pytest",
            "-v", "--tb=short",
        ]
    elif args.medium:
        # Medium: all backend except slow
        pytest_cmd = [
            "uv", "run", "pytest",
            "-m", "not slow",
            "-v", "--tb=short",
        ]
    else:
        # Light scan (default): exclude slow, only fast directories
        pytest_cmd = [
            "uv", "run", "pytest",
            "-m", "not slow",
            "tests/unit/", "tests/components/", "app/workflows/tests/",
            "-v", "--tb=short",
        ]

    be = _run(pytest_cmd, cwd=backend_dir, label="pytest (backend)")
    be_summary = _parse_pytest_summary(be["stdout"])
    be_failed = _parse_failed_tests(be["stdout"])

    # ── 2. Run frontend vitest ─────────────────────────────────────────
    print("[2/2] Frontend vitest")
    frontend_dir = PROJECT_ROOT / "frontend"
    if args.full_sweep:
        vitest_cmd = ["npx", "vitest", "run", "--reporter=verbose"]
    else:
        # Light/medium: exclude the long-running StreamingService test
        vitest_cmd = ["npx", "vitest", "run", "--reporter=verbose", "--exclude", "**/StreamingService.test.ts"]

    fe = _run(vitest_cmd, cwd=frontend_dir, label="vitest (frontend)")
    fe_summary = _parse_vitest_summary(fe["stdout"])
    fe_failed = _parse_failed_tests(fe["stdout"])

    # ── 3. Compile report ──────────────────────────────────────────────
    total_time = (be["elapsed"] + fe["elapsed"])

    report = f"""# Test Suite Report

**Date**: {now.strftime("%Y-%m-%d")}
**Timestamp**: {timestamp}
**Mode**: {scan_mode}
**Duration**: {_fmt_delta(total_time)}

---

## Build Status Dashboard

| Category | Count | Target | Status |
|----------|:-----:|:------:|--------|
{_format_dashboard(be_summary, fe_summary)}

---

## Backend — pytest

| Metric | Value |
|--------|:-----:|
| Passed | {be_summary["passed"]} |
| Failed | {be_summary["failed"]} |
| Skipped | {be_summary["skipped"]} |
| Deselected | {be_summary["deselected"]} |
| Warnings | {be_summary["warnings"]} |
| Duration | {_fmt_delta(be["elapsed"])} |

"""

    if be_failed:
        report += "### Failed Tests\n\n"
        for t in be_failed:
            report += f"- `{t}`\n"
        report += "\n"

    report += f"""---

## Frontend — vitest

| Metric | Value |
|--------|:-----:|
| Test files | {fe_summary["files"]} |
| Tests passed | {fe_summary["passed"]} |
| Tests failed | {fe_summary["failed"]} |
| Duration | {_fmt_delta(fe_summary["duration"]) or _fmt_delta(fe["elapsed"])} |

"""

    if fe_failed:
        report += "### Failed Tests\n\n"
        for t in fe_failed:
            report += f"- `{t}`\n"
        report += "\n"

    # ── 4. Timing breakdown ───────────────────────────────────────────
    both_ok = be["returncode"] in (0, 1) and fe["returncode"] in (0, 1, -2)
    if both_ok:
        be_pct = (be["elapsed"] / total_time * 100) if total_time > 0 else 0
        fe_pct = (fe["elapsed"] / total_time * 100) if total_time > 0 else 0
        report += f"""---

## Timing Breakdown

| Suite | Time | % of Total |
|:------|:----:|:----------:|
| pytest (backend) | {_fmt_delta(be["elapsed"])} | {be_pct:.0f}% |
| vitest (frontend) | {_fmt_delta(fe["elapsed"])} | {fe_pct:.0f}% |
| **Total** | **{_fmt_delta(total_time)}** | **100%** |

"""

    # ── 5. Classify failures ──────────────────────────────────────────
    connection_failures: list[str] = []
    code_failures: list[str] = []
    unknown_failures: list[str] = []

    for t in be_failed:
        cat = _classify_failure(t, be["stdout"], be["stderr"])
        if cat == "connection":
            connection_failures.append(t)
        elif cat == "code":
            code_failures.append(t)
        else:
            unknown_failures.append(t)

    fe_connection: list[str] = []
    fe_code: list[str] = []
    fe_unknown: list[str] = []
    for t in fe_failed:
        cat = _classify_failure(t, fe["stdout"], fe["stderr"])
        if cat == "connection":
            fe_connection.append(t)
        elif cat == "code":
            fe_code.append(t)
        else:
            fe_unknown.append(t)

    # ── 6. Known Issues ────────────────────────────────────────────────
    report += """---

## Known Issues

"""

    if connection_failures:
        report += f"""### 🔌 {len(connection_failures)} Backend Connection Failure(s)
These tests require the backend server to be running at `http://localhost:8000/api/v1`.
Start the application with `./cogitate.sh start` before running these.

"""
        for t in connection_failures:
            report += f"- `{t}`\n"
        report += "\n"

    if code_failures:
        report += f"""### ❌ {len(code_failures)} Backend Code-Level Failure(s)
These indicate actual code or configuration issues.

"""
        for t in code_failures:
            report += f"- `{t}`\n"
        report += "\n"

    if fe_connection:
        report += f"""### 🔌 {len(fe_connection)} Frontend Connection Failure(s)
These tests require external services.\n\n"""
        for t in fe_connection:
            report += f"- `{t}`\n"
        report += "\n"

    if fe_code:
        report += f"""### ❌ {len(fe_code)} Frontend Test Failure(s)\n\n"""
        for t in fe_code:
            report += f"- `{t}`\n"
        report += "\n"

    if unknown_failures:
        report += f"""### ❓ {len(unknown_failures)} Unclassified Backend Failure(s)
Check the full pytest output for details.\n\n"""
        for t in unknown_failures:
            report += f"- `{t}`\n"
        report += "\n"

    if fe_unknown:
        report += f"""### ❓ {len(fe_unknown)} Unclassified Frontend Failure(s)
Check the full vitest output for details.\n\n"""
        for t in fe_unknown:
            report += f"- `{t}`\n"
        report += "\n"

    if be_summary["warnings"] > 0:
        report += f"""### 🟡 {be_summary["warnings"]} Pytest Warnings
Check the full output for details.\n\n"""

    report += f"""---

*Report generated automatically by [`scripts/testing/generate_test_report.py`](scripts/testing/generate_test_report.py)*
"""

    # ── Write output ──────────────────────────────────────────────────
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\n✅ Report written to {output_path}")

    # ── Final summary ─────────────────────────────────────────────────
    print(f"\n╔══ Summary ══╗")
    print(f"  Backend:  {be_summary['passed']} passed, {be_summary['failed']} failed, {be_summary['skipped']} skipped, {be_summary['warnings']} warnings")
    print(f"  Frontend: {fe_summary['passed']} passed, {fe_summary['failed']} failed")
    print(f"  Total:    {_fmt_delta(total_time)}")
    print()


if __name__ == "__main__":
    main()
