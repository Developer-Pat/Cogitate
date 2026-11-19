#!/usr/bin/env python3
"""
Cogitate Factsheet Metrics Generator

Collects current project metrics (file counts, LOC, largest files, tech stack,
database info) and outputs a timestamped markdown report.

Intended to be invoked on demand to provide up-to-date project statistics
for onboarding tours and the wiki docs section.

Layout (optimized for developers):
  1. Development Environment
  2. Tech Stack Summary (high-level only)
  3. Source Code Metrics (counts, LOC, largest hand-written files)
  4. Detailed Tech Stack  (full dependency tables — towards end)
  5. Database Details      (towards end)

Usage:
    uv run python scripts/dev/generate_factsheet_metrics.py
    uv run python scripts/dev/generate_factsheet_metrics.py --output report.md
    uv run python scripts/dev/generate_factsheet_metrics.py --quiet
    uv run python scripts/dev/generate_factsheet_metrics.py --timestamp   # include date in filename

Output is written to wiki/docs/factsheet-metrics.md by default (wiki docs page).
Use --timestamp to keep dated copies in backend/reports/. The reports directory is gitignored.
"""

import argparse
import datetime
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "backend" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# System-generated reports land here — wiki/docs is the docs area (wiki-git-tracked)
AUTOGEN_DIR = PROJECT_ROOT / "wiki" / "docs"
AUTOGEN_DIR.mkdir(parents=True, exist_ok=True)

# Directories excluded entirely from scanning (runtime artifacts)
EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".mypy_cache",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    "dist",
    "build",
    "backups",
    ".uv",
    ".egg-info",
    "_archive",
    "_research",
    "local",
    "todo",  # local working notes since 2026-11-17 — not part of the shipped tree
    "exports",
    "tmp",
    "trash",
    "data",
}

# Source code extensions we track meaningfully
SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".scss",
    ".html",
    ".sh",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".md",
    ".sql",
    ".mako",
    ".cjs",
    ".mjs",
}

EXCLUDE_PATTERNS = [
    re.compile(r"\.git/"),
    re.compile(r"node_modules/"),
    re.compile(r"\.mypy_cache/"),
    re.compile(r"__pycache__/"),
    re.compile(r"\.venv/"),
    re.compile(r"\.pytest_cache/"),
    re.compile(r"dist/"),
    re.compile(r"build/"),
    re.compile(r"backups/"),
    re.compile(r"\.egg-info/"),
    re.compile(r"\.uv/"),
    re.compile(r"/_archive/"),
    re.compile(r"/_research/"),
    re.compile(r"/local/"),
    re.compile(r"/exports/"),
    re.compile(r"/tmp/"),
    re.compile(r"/trash/"),
    re.compile(r"/data/"),
    re.compile(r"/data/.*\.db"),
    re.compile(r"/logs/"),
    re.compile(r"backend/reports/"),
    re.compile(r"nohup\.out"),
    re.compile(r"profile_images/"),
    re.compile(r"docs/local/"),
    re.compile(r"wiki/docs/"),
]

# Patterns that identify auto-generated files
GENERATED_PATTERNS = [
    re.compile(r"package-lock\.json$"),
    re.compile(r"uv\.lock$"),
    re.compile(r"\.generated\.(ts|tsx|js)$"),
    re.compile(r"\.doc_index\.json$"),
    re.compile(r"api\.generated\.ts$"),
]


def _should_exclude(path: Path, root: Path) -> bool:
    """Check if a path should be excluded."""
    rel = path.relative_to(root).as_posix()
    return any(p.search(rel) for p in EXCLUDE_PATTERNS)


def _is_generated(path: Path) -> bool:
    """Check if a file is auto-generated rather than hand-written."""
    return any(p.search(str(path)) for p in GENERATED_PATTERNS)


def _fmt_size(num: int) -> str:
    """Format a byte count human-readably."""
    for unit in ("B", "KB", "MB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def _count_lines(fpath: Path) -> int:
    """Count lines in a file safely."""
    try:
        return sum(1 for _ in fpath.open("rb") if _)
    except (OSError, IOError):
        return 0


# ─── collectors ──────────────────────────────────────────────────────────


def collect_env_info() -> dict:
    """Collect OS, Python, and Node environment info."""
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "python_version": platform.python_version(),
    }
    uv_python = PROJECT_ROOT / ".python-version"
    if uv_python.exists():
        info["uv_python_version"] = uv_python.read_text().strip()
    for cmd, key in [
        (["node", "--version"], "node_version"),
        (["npm", "--version"], "npm_version"),
        (["uv", "--version"], "uv_version"),
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info[key] = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            info[key] = "not found"
    return info


def collect_tech_stack() -> dict:
    """Extract tech stack info from project config files."""
    stack = {}

    root_pyproject = PROJECT_ROOT / "pyproject.toml"
    if root_pyproject.exists():
        stack["root_dependencies"] = _parse_pyproject_deps(root_pyproject)

    backend_pyproject = PROJECT_ROOT / "backend" / "pyproject.toml"
    if backend_pyproject.exists():
        stack["backend_dependencies"] = _parse_pyproject_deps(backend_pyproject)
        stack["backend_description"] = _parse_pyproject_field(
            backend_pyproject, "description"
        )

    frontend_pkg = PROJECT_ROOT / "frontend" / "package.json"
    if frontend_pkg.exists():
        pkg = json.loads(frontend_pkg.read_text())
        stack["frontend_dependencies"] = {
            k: v for k, v in pkg.get("dependencies", {}).items()
        }
        stack["frontend_dev_dependencies"] = {
            k: v for k, v in pkg.get("devDependencies", {}).items()
        }

    return stack


def _parse_pyproject_deps(path: Path) -> dict[str, str]:
    """Parse dependencies from a pyproject.toml."""
    deps = {}
    text = path.read_text()
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if stripped == "]":
                break
            m = re.match(r'"(?P<name>[^>=<]+)(?P<spec>[>=<].*)?"', stripped.strip(","))
            if m:
                name = m.group("name")
                spec = m.group("spec") or "*"
                deps[name] = spec
    return deps


def _parse_pyproject_field(path: Path, field: str) -> str | None:
    """Parse a top-level field from pyproject.toml."""
    m = re.search(rf'^{field}\s*=\s*"(.+)"', path.read_text(), re.MULTILINE)
    return m.group(1) if m else None


def collect_code_metrics() -> dict:
    """Count source code files and lines by extension, plus largest files.

    Splits files into hand-written vs. auto-generated categories.
    Only tracks extensions in SOURCE_EXTENSIONS. Excludes runtime artifacts.
    """
    metrics = {
        "by_extension": {},
        "total_source_files": 0,
        "total_source_loc": 0,
        "hand_written_files": [],
        "generated_files": [],
    }

    for root, dirs, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        if _should_exclude(root_path, PROJECT_ROOT):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            fpath = root_path / file
            if _should_exclude(fpath, PROJECT_ROOT):
                continue

            ext = fpath.suffix.lower()
            if ext not in SOURCE_EXTENSIONS:
                continue

            loc = _count_lines(fpath)

            if ext not in metrics["by_extension"]:
                metrics["by_extension"][ext] = {"files": 0, "loc": 0}
            metrics["by_extension"][ext]["files"] += 1
            metrics["by_extension"][ext]["loc"] += loc
            metrics["total_source_files"] += 1
            metrics["total_source_loc"] += loc

            entry = {
                "path": str(fpath.relative_to(PROJECT_ROOT)),
                "loc": loc,
                "size": fpath.stat().st_size,
            }

            if _is_generated(fpath):
                metrics["generated_files"].append(entry)
            else:
                metrics["hand_written_files"].append(entry)

    metrics["hand_written_files"].sort(key=lambda x: x["loc"], reverse=True)
    metrics["generated_files"].sort(key=lambda x: x["loc"], reverse=True)
    metrics["hand_written_files"] = metrics["hand_written_files"][:20]
    metrics["generated_files"] = metrics["generated_files"][:10]

    return metrics


def collect_frontend_complexity() -> list[dict]:
    """Identify most complex frontend pages/components by file size."""
    components = []
    fe_root = PROJECT_ROOT / "frontend" / "src"

    if not fe_root.exists():
        return []

    for root, dirs, files in os.walk(fe_root):
        root_path = Path(root)
        for file in files:
            if not (file.endswith(".tsx") or file.endswith(".ts")):
                continue
            fpath = root_path / file
            loc = _count_lines(fpath)
            components.append(
                {
                    "path": str(fpath.relative_to(PROJECT_ROOT)),
                    "loc": loc,
                    "size": fpath.stat().st_size,
                }
            )

    components.sort(key=lambda x: x["loc"], reverse=True)
    return components[:15]


def collect_db_metrics() -> dict:
    """Count Alembic migrations and identify SQLAlchemy model files."""
    metrics = {
        "alembic_migrations": 0,
        "migration_files": 0,
        "model_files": [],
        "core_tables": [],
    }

    alembic_versions = PROJECT_ROOT / "backend" / "alembic" / "versions"
    if alembic_versions.exists():
        metrics["alembic_migrations"] = len(list(alembic_versions.glob("*.py")))

    migrations = PROJECT_ROOT / "backend" / "migrations"
    if migrations.exists():
        metrics["migration_files"] = len(list(migrations.glob("*.py")))

    # Find core SQLAlchemy model definitions
    core_models = PROJECT_ROOT / "backend" / "app" / "infrastructure" / "database" / "models.py"
    if core_models.exists():
        text = core_models.read_text()
        tables = re.findall(
            r"class\s+(\w+)\s*\(?\s*(?:Base|DeclarativeBase|db\.Model)",
            text,
        )
        metrics["core_tables"] = tables

    # Find all model files
    for model_file in PROJECT_ROOT.rglob("*.py"):
        if _should_exclude(model_file, PROJECT_ROOT):
            continue
        try:
            text = model_file.read_text()
            tables = re.findall(
                r"class\s+(\w+)\s*\(?\s*(?:Base|DeclarativeBase|db\.Model)",
                text,
            )
            if tables:
                metrics["model_files"].append(
                    {
                        "file": str(model_file.relative_to(PROJECT_ROOT)),
                        "tables": tables,
                    }
                )
        except (OSError, IOError):
            continue

    return metrics


# ─── report generation ───────────────────────────────────────────────────


def _summary_tech_stack(stack: dict) -> str:
    """Generate a concise tech stack summary suitable for the report top."""
    key_technologies = []

    backend = stack.get("backend_dependencies", {})
    frontend = stack.get("frontend_dependencies", {})

    # Core backend technologies
    for name, label in [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
        ("langchain", "LangChain"),
        ("langgraph", "LangGraph"),
        ("litellm", "LiteLLM"),
        ("uvicorn", "Uvicorn"),
        ("apscheduler", "APScheduler"),
        ("langfuse", "Langfuse"),
    ]:
        if name in backend or any(name in k for k in backend):
            key_technologies.append(label)

    # Core frontend technologies
    for name, label in [
        ("react", "React"),
        ("zustand", "Zustand"),
        ("tanstack/react-query", "TanStack Query"),
        ("react-router", "React Router"),
        ("vite", "Vite"),
        ("tailwindcss", "Tailwind CSS"),
        ("typescript", "TypeScript"),
        ("zod", "Zod"),
        ("recharts", "Recharts"),
        ("mermaid", "Mermaid"),
        ("daisyui", "daisyUI"),
        ("storybook", "Storybook"),
    ]:
        if name in frontend or any(name in k for k in frontend):
            key_technologies.append(label)

    return " · ".join(sorted(set(key_technologies)))


def generate_report(
    env: dict, stack: dict, code: dict, complexity: list, db: dict
) -> str:
    """Generate a markdown report from collected metrics.

    Layout: summary first → code metrics → detailed breakdowns at end.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    lines = []

    lines.append("# Cogitate Factsheet Metrics")
    lines.append("")
    lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1: Development Environment + Tech Stack Summary
    # ═══════════════════════════════════════════════════════════════
    lines.append("## Development Environment")
    lines.append("")
    lines.append("| Attribute | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| OS | {env['os']} |")
    lines.append(f"| Python | {env['python_version']} (uv pin: {env.get('uv_python_version', 'N/A')}) |")
    lines.append(f"| Node | {env.get('node_version', 'N/A')} |")
    lines.append(f"| npm | {env.get('npm_version', 'N/A')} |")
    lines.append(f"| uv | {env.get('uv_version', 'N/A')} |")
    lines.append("")

    lines.append("## Tech Stack")
    lines.append("")
    lines.append(_summary_tech_stack(stack))
    lines.append("")
    lines.append(
        "*See [Detailed Tech Stack](#detailed-tech-stack) at end of report for full dependency tables.*"
    )
    lines.append("")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2: Source Code Metrics
    # ═══════════════════════════════════════════════════════════════
    lines.append("## Source Code Metrics")
    lines.append("")
    lines.append(f"**Total source files:** {code['total_source_files']:,}")
    lines.append(f"**Total source lines of code:** {code['total_source_loc']:,}")
    lines.append("")

    lines.append("### By Extension")
    lines.append("")
    lines.append("| Extension | Files | Lines of Code |")
    lines.append("|-----------|-------|--------------|")
    sorted_exts = sorted(
        code["by_extension"].items(), key=lambda x: x[1]["loc"], reverse=True
    )
    for ext, data in sorted_exts:
        label = ext if ext != "(no extension)" else "*(none)*"
        lines.append(f"| {label} | {data['files']:,} | {data['loc']:,} |")
    lines.append(
        f"| **Total** | **{code['total_source_files']:,}** | **{code['total_source_loc']:,}** |"
    )
    lines.append("")

    # ── Largest Hand-Written Files ──
    lines.append("### Largest Hand-Written Source Files")
    lines.append("")
    lines.append("| # | File | LOC | Size |")
    lines.append("|---|------|-----|------|")
    for i, f in enumerate(code["hand_written_files"], 1):
        lines.append(
            f"| {i} | `{f['path']}` | {f['loc']:,} | {_fmt_size(f['size'])} |"
        )
    lines.append("")

    # ── Largest Auto-Generated Files ──
    if code["generated_files"]:
        lines.append("### Largest Generated Files ⚙️")
        lines.append("")
        lines.append(
            "These files are auto-generated (lockfiles, API types, indexes) "
            "and are not hand-maintained by developers."
        )
        lines.append("")
        lines.append("| # | File | LOC | Size |")
        lines.append("|---|------|-----|------|")
        for i, f in enumerate(code["generated_files"], 1):
            lines.append(
                f"| {i} | `{f['path']}` | {f['loc']:,} | {_fmt_size(f['size'])} |"
            )
        lines.append("")

    lines.append(
        "*Runtime artifacts (databases, logs, backups) and binaries are excluded.*"
    )
    lines.append("")

    # ── Frontend Complexity ──
    if complexity:
        lines.append("### Most Complex Frontend Files")
        lines.append("")
        lines.append("| # | File | LOC | Size |")
        lines.append("|---|------|-----|------|")
        for i, f in enumerate(complexity, 1):
            lines.append(
                f"| {i} | `{f['path']}` | {f['loc']:,} | {_fmt_size(f['size'])} |"
            )
        lines.append("")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3: Detailed Tech Stack (detailed, at end)
    # ═══════════════════════════════════════════════════════════════
    lines.append("---")
    lines.append("")
    lines.append("## Detailed Tech Stack")
    lines.append("")

    if stack.get("backend_dependencies"):
        lines.append("### Backend (Python/FastAPI)")
        lines.append("")
        lines.append(f"Description: {stack.get('backend_description', 'N/A')}")
        lines.append("")
        lines.append("| Dependency | Version Spec |")
        lines.append("|------------|-------------|")
        for name, spec in sorted(stack["backend_dependencies"].items()):
            lines.append(f"| {name} | {spec} |")
        lines.append("")

    if stack.get("frontend_dependencies"):
        lines.append("### Frontend (React/TypeScript)")
        lines.append("")
        lines.append("| Dependency | Version |")
        lines.append("|------------|---------|")
        for name, ver in sorted(stack["frontend_dependencies"].items()):
            lines.append(f"| {name} | {ver} |")
        lines.append("")

    if stack.get("frontend_dev_dependencies"):
        lines.append("### Frontend Dev Dependencies")
        lines.append("")
        lines.append("| Dependency | Version |")
        lines.append("|------------|---------|")
        for name, ver in sorted(stack["frontend_dev_dependencies"].items()):
            lines.append(f"| {name} | {ver} |")
        lines.append("")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 4: Database Details (at end)
    # ═══════════════════════════════════════════════════════════════
    lines.append("---")
    lines.append("")
    lines.append("## Database")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Alembic migration files | {db['alembic_migrations']} |")
    lines.append(f"| Manual migration scripts | {db['migration_files']} |")
    lines.append(f"| SQLAlchemy model files found | {len(db['model_files'])} |")
    lines.append("")

    lines.append("### Core Tables")
    lines.append("")
    if db.get("core_tables"):
        lines.append("The main model file defines these tables:")
        lines.append("")
        for t in sorted(db["core_tables"]):
            lines.append(f"- `{t}`")
        lines.append("")
    else:
        lines.append("*(not detected)*")
        lines.append("")

    lines.append("### SQLAlchemy Model Files")
    lines.append("")
    lines.append("| File | Classes Found |")
    lines.append("|------|-------------|")
    for entry in db.get("model_files", []):
        tables_str = ", ".join(entry["tables"])
        lines.append(f"| `{entry['file']}` | {tables_str} |")
    if not db.get("model_files"):
        lines.append("| *(no model files detected)* | |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Report generated by `scripts/dev/generate_factsheet_metrics.py`*"
    )

    return "\n".join(lines)


# ─── main ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate Cogitate factsheet metrics report."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Custom output path (default: wiki/docs/factsheet-metrics.md)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--timestamp",
        "-t",
        action="store_true",
        help="Include date in filename (backend/reports/factsheet-metrics-{date}.md)",
    )
    args = parser.parse_args()

    def log(msg: str):
        if not args.quiet:
            print(msg)

    log("🔍 Cogitate Factsheet Metrics Generator")
    log("")

    log("📦 Collecting environment info...")
    env = collect_env_info()

    log("📦 Collecting tech stack...")
    stack = collect_tech_stack()

    log("📦 Counting source code files and lines of code...")
    code = collect_code_metrics()

    log("📦 Analyzing frontend complexity...")
    complexity = collect_frontend_complexity()

    log("📦 Checking database info...")
    db = collect_db_metrics()

    log("📝 Generating report...")
    report = generate_report(env, stack, code, complexity, db)

    if args.output:
        output_path = Path(args.output)
    elif args.timestamp:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d"
        )
        output_path = REPORTS_DIR / f"factsheet-metrics-{date_str}.md"
    else:
        output_path = AUTOGEN_DIR / "factsheet-metrics.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # THE ATLAS FRONTMATTER. This file lives in the wiki, and every wiki page needs
    # it (`check_atlas_validation.py` reads it). Writing only the body meant every
    # regeneration silently stripped the page's metadata, so a later hand-edit had
    # to put it back — the generator owns the whole file.
    frontmatter = (
        "---\n"
        "title: Factsheet Metrics\n"
        "type: atlas-docs\n"
        "path: wiki/docs/factsheet-metrics.md\n"
        "confidence: medium\n"
        f"updated: {datetime.date.today().isoformat()}\n"
        "tags: [type/docs, domain/docs]\n"
        "---\n\n"
    )
    output_path.write_text(frontmatter + report)
    log(f"✅ Report written to {output_path}")

    # Print summary
    py_data = code["by_extension"].get(".py", {})
    ts_data = code["by_extension"].get(".ts", {})
    tsx_data = code["by_extension"].get(".tsx", {})

    log("")
    log("── Summary ──")
    log(f"  Source files:           {code['total_source_files']:,}")
    log(f"  Source LOC:             {code['total_source_loc']:,}")
    log(f"  Python files:           {py_data.get('files', 0):,}")
    log(f"  Python LOC:             {py_data.get('loc', 0):,}")
    log(f"  TS/TSX files:           {ts_data.get('files', 0) + tsx_data.get('files', 0):,}")
    log(f"  TS/TSX LOC:             {ts_data.get('loc', 0) + tsx_data.get('loc', 0):,}")
    log(f"  Alembic migrations:     {db['alembic_migrations']}")
    log(f"  Model files found:      {len(db['model_files'])}")
    if code["hand_written_files"]:
        log(f"  Largest hand-written:   {code['hand_written_files'][0]['path']} ({code['hand_written_files'][0]['loc']:,} LOC)")


if __name__ == "__main__":
    main()