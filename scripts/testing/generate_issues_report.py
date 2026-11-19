#!/usr/bin/env python3
"""
Issues Report Generator — run all static analysis tools and produce a
timestamped markdown report of current errors and warnings across the monorepo.

Usage:
    python3 scripts/testing/generate_issues_report.py                      # full sweep
    python3 scripts/testing/generate_issues_report.py --backend-only       # ruff + mypy only
    python3 scripts/testing/generate_issues_report.py --frontend-only      # eslint + tsc only
    python3 scripts/testing/generate_issues_report.py --output report.md   # custom output path

Output is written to backend/reports/issues-report-{date}.md by default.
This directory is gitignored — reports are never committed.
"""

import argparse
import datetime
import re
import subprocess
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "backend" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── helpers ──────────────────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path, label: str, timeout: int = 120) -> dict:
    """Run a command, capture output, and return structured results."""
    print(f"  → {label} ... ", end="", flush=True)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        status = "done" if result.returncode == 0 else f"exit {result.returncode}"
        print(status)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        print("SKIPPED (command not found)")
        return {"returncode": -2, "stdout": "", "stderr": f"Command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return {"returncode": -1, "stdout": "", "stderr": "Timed out"}


# ─── parsers ──────────────────────────────────────────────────────────────


def _parse_ruff(text: str) -> dict:
    """Return {errors, warnings} from ruff output (concise or default format).

    Ruff concise format: ``path:line:col: CODE message``
    Code prefix determines severity: F/I/UPG/W (warnings) or E/N (errors).
    """
    errors = 0
    warnings = 0
    for line in text.splitlines():
        # Match: "path:line:col: CODE message"
        m = re.match(r"^[^:]+:\d+:\d+:\s+([A-Z]+\d+)", line)
        if m:
            code = m.group(1)
            # Ruff conventions:
            #   E = error (style)
            #   N = naming convention error
            #   F = pyflakes (error)
            #   I = isort (warning-style)
            #   W = warning (style)
            #   UP = pyupgrade
            if code.startswith("E") or code.startswith("N") or code.startswith("F"):
                errors += 1
            else:
                warnings += 1
    # Fallback: check "Found N error(s)" in output
    if errors == 0:
        m = re.search(r"Found (\d+) error", text)
        if m:
            errors = int(m.group(1))
    return {"errors": errors, "warnings": warnings}


def _parse_mypy(text: str) -> dict:
    """Return {errors} from mypy output."""
    errors = 0
    for line in text.splitlines():
        if "error:" in line.lower():
            errors += 1
    # If "no issues found" or empty, count 0
    if "no issues found" in text.lower():
        errors = 0
    return {"errors": errors}


def _parse_eslint(text: str) -> dict:
    """Return {errors, warnings} from eslint output (stylish format).

    Picks counts from the summary line: "✖ X problems (Y errors, Z warnings)".
    """
    errors = 0
    warnings = 0
    # Summary line: "✖ X problems (Y errors, Z warnings)"
    m = re.search(r"(\d+)\s+problems?", text)
    m_err = re.search(r"(\d+)\s+errors?", text)
    m_warn = re.search(r"(\d+)\s+warnings?", text)
    if m_err:
        errors = int(m_err.group(1))
    if m_warn:
        warnings = int(m_warn.group(1))
    return {"errors": errors, "warnings": warnings}


def _parse_tsc(text: str) -> dict:
    """Return {errors} from tsc output."""
    errors = 0
    for line in text.splitlines():
        if "error TS" in line or "error  TS" in line:
            errors += 1
    return {"errors": errors}


def _parse_eslint_rule_breakdown(text: str) -> list[dict]:
    """Extract individual rule violations from eslint output (compact format)."""
    violations: list[dict] = []
    for line in text.splitlines():
        # compact format: "file:line:col: Error/Warning message [rule]"
        m = re.match(r"^(.+?):\d+:\d+:\s+(Error|Warning)\s+(.+?)\s+\[(.+?)\]$", line)
        if m:
            violations.append({
                "file": m.group(1),
                "severity": m.group(2).lower(),
                "message": m.group(3),
                "rule": m.group(4),
            })
    return violations


# ─── main ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static-analysis issues report")
    parser.add_argument("--backend-only", action="store_true", help="Run ruff + mypy only")
    parser.add_argument("--frontend-only", action="store_true", help="Run eslint + tsc only")
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output path (default: backend/reports/issues-report-{date}.md)",
    )
    args = parser.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    local_now = now.astimezone()
    date_str = now.strftime("%Y-%m-%d")
    timestamp = local_now.strftime("%Y-%m-%d %H:%M:%S %Z")

    output_path = args.output
    if not output_path:
        output_path = str(REPORTS_DIR / f"issues-report-{date_str}.md")

    run_backend = not args.frontend_only
    run_frontend = not args.backend_only

    print(f"╔══ Issues Report Generator ══╗")
    print(f"  Timestamp: {timestamp}")
    print(f"  Output:    {output_path}")
    print()

    # ── 1. Backend: Ruff ──────────────────────────────────────────────
    backend_dir = PROJECT_ROOT / "backend"
    ruff: dict | None = None
    if run_backend:
        print("[1/2] Backend")
        ruff = _run(
            ["uv", "run", "ruff", "check", "."],
            cwd=backend_dir, label="ruff (lint)",
        )
        ruff_summary = _parse_ruff(ruff["stdout"] + ruff["stderr"])

        print(f"       Ruff: {ruff_summary['errors']} errors, {ruff_summary['warnings']} warnings")

        mypy = _run(
            ["uv", "run", "mypy", "app/"],
            cwd=backend_dir, label="mypy (types)",
        )
        mypy_summary = _parse_mypy(mypy["stdout"] + mypy["stderr"])
        print(f"       Mypy: {mypy_summary['errors']} errors")
    else:
        ruff_summary = {"errors": 0, "warnings": 0}
        mypy_summary = {"errors": 0}

    # ── 2. Frontend: ESLint + tsc ──────────────────────────────────────
    frontend_dir = PROJECT_ROOT / "frontend"
    eslint: dict | None = None
    tsc: dict | None = None
    if run_frontend:
        print("[2/2] Frontend")
        eslint = _run(
            ["npx", "eslint", "."],
            cwd=frontend_dir, label="eslint",
        )
        eslint_summary = _parse_eslint(eslint["stdout"] + eslint["stderr"])
        eslint_rules = _parse_eslint_rule_breakdown(eslint["stdout"] + eslint["stderr"])
        print(f"       ESLint: {eslint_summary['errors']} errors, {eslint_summary['warnings']} warnings")

        tsc = _run(
            ["npx", "tsc", "--noEmit"],
            cwd=frontend_dir, label="tsc (types)",
        )
        tsc_summary = _parse_tsc(tsc["stdout"] + tsc["stderr"])
        print(f"       tsc: {tsc_summary['errors']} errors")
    else:
        eslint_summary = {"errors": 0, "warnings": 0}
        tsc_summary = {"errors": 0}
        eslint_rules = []

    # ── 3. Compile report ──────────────────────────────────────────────
    total_errors = ruff_summary["errors"] + mypy_summary["errors"] + eslint_summary["errors"] + tsc_summary["errors"]
    total_warnings = ruff_summary["warnings"] + eslint_summary["warnings"]

    def badge(count: int, ok_if_zero: bool = True) -> str:
        if count == 0 and ok_if_zero:
            return "✅"
        return "❌" if count > 0 else "✅"

    report = f"""# Issues Report

**Date**: {date_str}
**Timestamp**: {timestamp}
**Duration**: N/A (static analysis only)

---

## Summary Dashboard

| Tool | Scope | Errors | Warnings | Status |
|------|-------|:------:|:--------:|:------:|
| **Ruff** | Backend lint | {ruff_summary['errors']} | {ruff_summary['warnings']} | {badge(ruff_summary['errors'])} |
| **Mypy** | Backend types | {mypy_summary['errors']} | — | {badge(mypy_summary['errors'])} |
| **ESLint** | Frontend lint | {eslint_summary['errors']} | {eslint_summary['warnings']} | {badge(eslint_summary['errors'])} |
| **tsc** | Frontend types | {tsc_summary['errors']} | — | {badge(tsc_summary['errors'])} |
| **Total** | — | **{total_errors}** | **{total_warnings}** | |

---

## Backend

### Ruff — {ruff_summary['errors']} error(s), {ruff_summary['warnings']} warning(s)

"""

    if ruff_summary["errors"] == 0 and ruff_summary["warnings"] == 0:
        report += "✅ All checks passed.\n\n"
    else:
        report += "```\n"
        report += (ruff["stdout"] if ruff else "") + "\n"
        report += "```\n\n"

    report += f"""### Mypy — {mypy_summary['errors']} error(s)

"""
    if mypy_summary["errors"] == 0:
        report += "✅ No type issues found.\n\n"
    else:
        # Show error lines
        report += "```\n"
        for line in (mypy["stdout"] if mypy else "").splitlines():
            if "error:" in line.lower():
                report += line + "\n"
        report += "```\n\n"

    report += """---

## Frontend

"""

    report += f"""### ESLint — {eslint_summary['errors']} error(s), {eslint_summary['warnings']} warning(s)

"""
    if eslint_summary["errors"] == 0 and eslint_summary["warnings"] == 0:
        report += "✅ All checks passed.\n\n"
    else:
        # Rule breakdown
        rule_counts: dict[str, dict] = {}
        for v in eslint_rules:
            if v["rule"] not in rule_counts:
                rule_counts[v["rule"]] = {"errors": 0, "warnings": 0, "files": set()}
            rule_counts[v["rule"]][v["severity"]] += 1
            rule_counts[v["rule"]]["files"].add(v["file"])

        report += "| Rule | Errors | Warnings | Files Affected |\n"
        report += "|------|:------:|:--------:|:--------------:|\n"
        for rule in sorted(rule_counts.keys(), key=lambda r: -rule_counts[r]["errors"]):
            rc = rule_counts[rule]
            report += f"| `{rule}` | {rc['errors']} | {rc['warnings']} | {len(rc['files'])} |\n"
        report += "\n"

    report += f"""### tsc — {tsc_summary['errors']} error(s)

"""
    if tsc_summary["errors"] == 0:
        report += "✅ No type errors.\n\n"
    else:
        report += "```\n"
        for line in (tsc["stdout"] if tsc else "").splitlines():
            if "error" in line.lower():
                report += line + "\n"
        report += "```\n\n"

    report += f"""---

## Summary

| Tool | Total | Notes |
|------|:----:|-------|
| Ruff | {ruff_summary['errors']} errors, {ruff_summary['warnings']} warnings | Run `uv run ruff check backend/` for details |
| Mypy | {mypy_summary['errors']} errors | Run `uv run mypy backend/app/` for details |
| ESLint | {eslint_summary['errors']} errors, {eslint_summary['warnings']} warnings | Run `cd frontend && npx eslint .` for details |
| tsc | {tsc_summary['errors']} errors | Run `cd frontend && npx tsc --noEmit` for details |
| **Total** | **{total_errors} errors, {total_warnings} warnings** | |

*Report generated automatically by [`scripts/testing/generate_issues_report.py`](scripts/testing/generate_issues_report.py)*
"""

    # ── Write output ──────────────────────────────────────────────────
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\n✅ Report written to {output_path}")

    # ── Final summary ─────────────────────────────────────────────────
    print(f"\n╔══ Summary ══╗")
    print(f"  Backend:  Ruff {ruff_summary['errors']} err / {ruff_summary['warnings']} warn,  Mypy {mypy_summary['errors']} err")
    print(f"  Frontend: ESLint {eslint_summary['errors']} err / {eslint_summary['warnings']} warn,  tsc {tsc_summary['errors']} err")
    print(f"  Total:    {total_errors} errors, {total_warnings} warnings")
    print()


if __name__ == "__main__":
    main()