"""Generate the script catalog from the scripts themselves.

`wiki/docs/script-catalog.md` is a catalogue, and a catalogue rots one row at a
time: rows for scripts that were deleted, rows missing for scripts that were
added. So it is BUILT, not typed — the Purpose column is each script's own module
docstring and the Invocation is its documented `Usage:` line (or the project
default for its file type). Prose lives here, in the builder, so a regeneration
cannot revert a hand-edited sentence.

    python3 scripts/dev/generate_script_catalog.py            # write the page
    python3 scripts/dev/generate_script_catalog.py --check    # gate: exit 1 if stale
    python3 scripts/dev/generate_script_catalog.py --stdout    # print, write nothing

`--check` compares CONTENT: the frontmatter's `updated:` line is the day of the run, not a
fact about the scripts, so it is normalised out of the comparison (see `normalise`). The gate
is wired into the pre-commit hook and into `scripts/testing/verify_flat_tree.sh`, because a
catalog nobody regenerates rots one row at a time — a row for a script that is gone, no row
for a script that arrived.

Sections are the script directories. A file with no module docstring is listed
honestly as `(no module docstring)` rather than given an invented purpose.
"""

import argparse
import ast
import datetime
import pathlib
import re
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "wiki" / "docs" / "script-catalog.md"

#: The directories that hold developer scripts, in catalogue order, with the one
#: line of prose that heads each section.
SECTIONS: list[tuple[str, str]] = [
    ("scripts/analysis", "Trace and log analysis, metric collection."),
    ("scripts", "Top-level verification helpers."),
    ("scripts/bench", "THE BENCH: the fixed job set and its driver."),
    ("scripts/core", "Seeding, RAG ingestion, backup, export, sweep, docs."),
    ("scripts/dev", "Developer tools: metrics, codemods, API limit probes."),
    ("scripts/diagnostics", "Health checks, model probes, conflict detection."),
    ("scripts/maintenance", "Migrations, cleanup, database recovery."),
    ("scripts/spikes", "Throwaway experiments kept for the record."),
    ("scripts/testing", "Test execution, suites, gates, provider probes."),
    ("backend/scripts", "Backend-internal: tools, schema, docs DB, workflows."),
]

CODE_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts"}

#: Scripts that are gone, kept because a search for the name should land somewhere
#: useful. Hand-maintained: the tree cannot tell us what used to be in it.
CONSOLIDATED: list[tuple[str, str, str]] = [
    ("add_duckduckgo_tool.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("add_jina_reader_tool.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("add_sqlite_manager_tool.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("add_tavily_tool.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("add_wikipedia_tool.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("seed_builtin_tools.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("seed_guide_dev_tools.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("seed_introspection_tools.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("seed_tools.py", "folded into `seed_all_tools.py`", "backend/scripts/seed_all_tools.py"),
    ("seed_docs_content.py", "wrote to the wrong database path; the help docs are written by this",
     "scripts/core/update_help_docs.py"),
    ("update_tavily_tool.py", "tool config is seeded from the code registry at boot (`auto_sync_tools`)", ""),
    ("update_tool_arguments_schema.py",
     "argument schemas live in the code registry and sync at boot", ""),
]

DEFAULT_INVOCATION = {
    ".py": "`uv run python {path}`",
    ".sh": "`./{path}`",
    ".js": "`node {path}`",
    ".mjs": "`node {path}`",
    ".cjs": "`node {path}`",
    ".ts": "`npx tsx {path}`",
}

USAGE_LINE = re.compile(r"^\s*(?:Usage|USAGE|[Ee]xamples?)\s*:\s*(.*)$")

#: Lines that end the description: the docstring turns to instructions.
PROSE_STOP = re.compile(r"^\s*(?:Usage|USAGE|Examples?|Args|Arguments|Options|Parameters)\s*:", re.IGNORECASE)
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s)")

#: A docstring underline (`=====`, `-----`).
RULE_LINE = re.compile(r"^[=\-_*~#]{3,}$")

#: Docstring asides that date the file instead of describing it.
DATED_ASIDE = re.compile(r"\s*\((?:[^()]*20\d\d-\d\d-\d\d[^()]*)\)")


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def python_docstring(path: pathlib.Path) -> str | None:
    try:
        return ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None


def comment_header(path: pathlib.Path) -> str | None:
    """The leading `#` comment block of a shell/JS file, minus the shebang."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not kept and (not stripped or stripped.startswith("#!")):
            continue
        if stripped.startswith("#"):
            kept.append(stripped.lstrip("#").strip())
            continue
        if not stripped and kept:
            break
        if stripped:
            break
    return " ".join(part for part in kept if part) or None


def one_line(text: str, limit: int = 170) -> str:
    """Collapse a docstring to the sentence or two that say what the script does."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    for stop in (". ", "; "):
        at = cut.rfind(stop)
        if at > 60:
            return cut[: at + 1]
    clipped = cut.rsplit(" ", 1)[0].rstrip(",;:—-")
    return clipped + "…"


SELF_NAMED = re.compile(r"^\s*[\w.\-/]+\.(?:py|sh|js|mjs|cjs|ts)\b[\s:\u2014-]*", re.IGNORECASE)


def purpose_of(path: pathlib.Path, rel: str) -> str:
    doc = python_docstring(path) if path.suffix == ".py" else comment_header(path)
    if not doc:
        return "(no module docstring)"
    first, _, rest = doc.strip().partition("\n")
    first = " ".join(first.split())
    # A docstring that opens with its own filename says nothing twice.
    first = SELF_NAMED.sub("", first, count=1) or first

    # The description ends where the docstring turns to instructions or a list.
    prose: list[str] = []
    for line in rest.splitlines():
        if PROSE_STOP.match(line) or LIST_ITEM.match(line):
            break
        stripped = line.strip()
        if not stripped or RULE_LINE.match(stripped):
            continue  # a docstring's ASCII underline is not prose
        prose.append(stripped)
    body = " ".join(prose)

    if not body:
        return one_line(first)
    # A short first line is a title, not a description — carry the prose behind it.
    if len(first) < 70:
        return one_line(f"{first} — {body}", limit=190)
    return one_line(first, limit=190)


def invocation_of(path: pathlib.Path, rel: str, doc: str | None) -> str:
    if doc:
        for line in doc.splitlines():
            match = USAGE_LINE.match(line)
            if match:
                usage = match.group(1).strip()
                if not usage:
                    continue
                usage = usage.strip("`").strip()
                if usage:
                    return f"`{usage}`"
    return DEFAULT_INVOCATION.get(path.suffix, "`{path}`").format(path=rel)


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def build() -> str:
    files = tracked_files()
    sections: list[tuple[str, str, list[str]]] = []
    for directory, blurb in SECTIONS:
        members = [
            f for f in files
            if pathlib.Path(f).suffix in CODE_SUFFIXES
            and f.rsplit("/", 1)[0] == directory
            and pathlib.Path(f).name != "__init__.py"
        ]
        sections.append((directory, blurb, sorted(members)))

    total = sum(len(members) for _, _, members in sections)
    today = datetime.date.today().isoformat()

    out: list[str] = [
        "---",
        "title: Script Catalog",
        "type: atlas-docs",
        "path: wiki/docs/script-catalog.md",
        "confidence: medium",
        f"updated: {today}",
        "tags: [type/docs, domain/docs]",
        "---",
        "",
        "# Script Catalog",
        "",
        "Every developer script in `scripts/` and `backend/scripts/`, generated from the",
        "scripts themselves: **Purpose** is the file's own module docstring, **Invocation**",
        "is its documented `Usage:` line or the project default for that file type.",
        "",
        "Regenerate with `python3 scripts/dev/generate_script_catalog.py`; `--check`",
        "fails when the page is stale.",
        "",
        f"**{total} scripts** in {len(sections)} directories.",
        "",
        "---",
        "",
        "## Overview",
        "",
        "| Directory | What lives there | Scripts |",
        "|-----------|------------------|--------:|",
    ]
    for directory, blurb, members in sections:
        out.append(f"| `{directory}/` | {blurb} | {len(members)} |")
    out.append("")

    for index, (directory, blurb, members) in enumerate(sections, start=1):
        out += ["---", "", f"## {index}. `{directory}/`", "", blurb, ""]
        if not members:
            out += ["(empty)", ""]
            continue
        out += [
            "| Script | Purpose | Invocation |",
            "|--------|---------|------------|",
        ]
        for rel in members:
            path = PROJECT_ROOT / rel
            doc = python_docstring(path) if path.suffix == ".py" else None
            name = pathlib.Path(rel).name
            out.append(
                f"| [`{name}`]({rel}) | {cell(DATED_ASIDE.sub('', purpose_of(path, rel)))} "
                f"| {cell(invocation_of(path, rel, doc))} |"
            )
        out.append("")

    out += [
        "---",
        "",
        "## Consolidated scripts",
        "",
        "Gone, and where their work went. A search for one of these names should land",
        "somewhere useful rather than nowhere.",
        "",
        "| Script | Disposition | Now |",
        "|--------|-------------|-----|",
    ]
    for name, disposition, replacement in CONSOLIDATED:
        now = f"[`{pathlib.Path(replacement).name}`]({replacement})" if replacement else "—"
        out.append(f"| `{name}` | {disposition} | {now} |")
    out += [
        "",
        "---",
        "",
        "## Common run patterns",
        "",
        "| Kind | Command |",
        "|------|---------|",
        "| Python, project dependencies | `uv run python scripts/...` |",
        "| Python, standard library only | `python3 scripts/...` |",
        "| Shell | `./scripts/...` |",
        "| Node | `node scripts/...` |",
        "",
        "## Notes",
        "",
        "- Scripts that rewrite files take `--dry-run` where their docstring says so — run",
        "  that first.",
        "- Report generators write to `backend/reports/`, which is gitignored.",
        "",
    ]
    return "\n".join(out)


STAMP = re.compile(r"(?m)^updated:.*$")


def normalise(text: str) -> str:
    """Blank the frontmatter's `updated:` line so `--check` compares content, not the clock.

    The stamp records the day the page was written, which is not a fact about the scripts:
    compared literally, the page is "stale" every midnight and the gate can never hold. The
    root of a flatten has one commit and therefore one date, so deriving the stamp from git
    would fail the very tree the gate exists to clear.
    """
    return STAMP.sub("updated: <normalised>", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the page is stale")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args()

    try:
        rendered = build()
    except FileNotFoundError as missing:
        # Tracked in the index, absent from the working tree: the row cannot be built, so the
        # gate says which file rather than dying inside ast.parse.
        print(f"MISSING: {missing.filename} is tracked but not on disk — stage the deletion")
        return 1

    if args.stdout:
        print(rendered)
        return 0

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if normalise(current) != normalise(rendered):
            print("STALE: wiki/docs/script-catalog.md does not match the scripts")
            print("       run: python3 scripts/dev/generate_script_catalog.py")
            return 1
        print("CURRENT: the catalog matches the scripts")
        return 0

    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)} ({len(rendered.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
