#!/usr/bin/env python3
"""
UI Atlas Scaffolder: a stub doc for every frontend source file the atlas does not claim.

Walks frontend/src/ and writes a stub page (frontmatter + section skeleton) into the atlas for each
source file that NO existing doc names. Coverage is read from the docs' own `path:` frontmatter, not
from their filenames — the atlas names a doc for its subject (`NotificationsConfig.md` documents
`NotificationsConfigPage.tsx`), so a name match would report every page as undocumented and scaffold a
second doc beside the real one.

The directory indexes are hand-maintained and this script does not write them.

Usage:
    python3 scripts/core/scaffold_atlas.py [--dry-run]

Output:
    wiki/atlas/ui/{pages,components,hooks,services,stores}/<SourceName>.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
ATLAS_ROOT = PROJECT_ROOT / "wiki" / "atlas" / "ui"

# Top-level src dirs we document (mirrors the atlas's section layout)
SECTIONS = ["pages", "components", "hooks", "services", "stores"]

# Files that are not source (stories, tests, barrel files)
SKIP_FILES = {
    "__tests__",
    "index.ts",  # barrel exports — documented via directory README
}

TYPE_MAP = {
    "pages": "atlas-page",
    "components": "atlas-component",
    "hooks": "atlas-hook",
    "services": "atlas-service",
    "stores": "atlas-store",
}

SECTION_LABEL = {
    "pages": "Pages",
    "components": "Components",
    "hooks": "Hooks",
    "services": "Services",
    "stores": "Stores",
}


def file_title(path: Path, section: str) -> str:
    """Derive a human title from a file name."""
    name = path.stem
    if section == "hooks":
        # useHooks -> "useHooks" stays camelCase
        return name
    # kebab-case / PascalCase -> spaced words
    words = name.replace("_", " ").replace("-", " ")
    # split camelCase boundaries
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", words)
    return " ".join(w.capitalize() for w in words.split() if w)


def frontmatter(title: str, src_path: Path, section: str) -> str:
    rel = src_path.relative_to(PROJECT_ROOT).as_posix()
    today = date.today().isoformat()
    return (
        "---\n"
        f"title: {title}\n"
        f"type: {TYPE_MAP[section]}\n"
        f"path: {rel}\n"
        f"confidence: stub\n"
        f"updated: {today}\n"
        "---\n"
    )


def stub_body(title: str, src_path: Path, section: str) -> str:
    rel = src_path.relative_to(PROJECT_ROOT).as_posix()
    if section == "pages":
        return (
            f"# {title}\n\n"
            f"**Component**: `{rel}`\n"
            f"**Last Updated**: {date.today().isoformat()}\n\n"
            "## Purpose\n_TODO: read source and describe._\n\n"
            "## Key Features\n- _TODO_\n\n"
            "## Components Used\n_TODO_\n\n"
            "## Hooks Used\n_TODO_\n\n"
            "## Data Flow\n_TODO_\n\n"
            "## State Management\n_TODO_\n\n"
            "## API Endpoints Called\n_TODO_\n\n"
            "## Related Pages\n_TODO_\n"
        )
    if section == "components":
        return (
            f"# {title}\n\n"
            f"**Path**: `{rel}`\n"
            f"**Last Updated**: {date.today().isoformat()}\n\n"
            "## Purpose\n_TODO: read source and describe._\n\n"
            "## Props Interface\n```typescript\n// TODO\n```\n\n"
            "## Dependencies\n_TODO_\n\n"
            "## Usage Example\n```tsx\n// TODO\n```\n\n"
            "## State Used\n_TODO_\n\n"
            "## Related Components\n_TODO_\n"
        )
    if section == "hooks":
        return (
            f"# {title}\n\n"
            f"**Path**: `{rel}`\n"
            f"**Last Updated**: {date.today().isoformat()}\n\n"
            "## Purpose\n_TODO_\n\n"
            "## Parameters\n_TODO_\n\n"
            "## Return Value\n_TODO_\n\n"
            "## Dependencies\n_TODO_\n\n"
            "## Usage Example\n```ts\n// TODO\n```\n\n"
            "## State Interactions\n_TODO_\n"
        )
    if section == "services":
        return (
            f"# {title}\n\n"
            f"**Path**: `{rel}`\n"
            f"**Last Updated**: {date.today().isoformat()}\n\n"
            "## Purpose\n_TODO_\n\n"
            "## Methods/API\n_TODO_\n\n"
            "## Dependencies\n_TODO_\n\n"
            "## Usage Example\n```ts\n// TODO\n```\n\n"
            "## Error Handling\n_TODO_\n"
        )
    if section == "stores":
        return (
            f"# {title}\n\n"
            f"**Path**: `{rel}`\n"
            f"**Last Updated**: {date.today().isoformat()}\n\n"
            "## Purpose\n_TODO_\n\n"
            "## State Shape\n_TODO_\n\n"
            "## Actions\n_TODO_\n\n"
            "## Selectors\n_TODO_\n\n"
            "## Persistence\n_TODO_\n\n"
            "## Related Hooks\n_TODO_\n"
        )
    # architecture/fallback
    return (
        f"# {title}\n\n"
        f"**Source**: `{rel}`\n"
        f"**Last Updated**: {date.today().isoformat()}\n\n"
        "## Overview\n_TODO_\n"
    )


def is_source_file(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return False
    if path.suffix not in (".ts", ".tsx"):
        return False
    if path.name.endswith(".stories.tsx") or path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
        return False
    # Skip spec files
    if ".spec." in path.name or "__tests__" in path.parts:
        return False
    return True


def should_skip_dir(name: str) -> bool:
    return name.startswith(".") or name in ("__tests__", "node_modules")


SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


def covered_sources() -> set[str]:
    """Every source FILE an atlas doc already claims, read from its `path:` frontmatter.

    Only entries naming a source file count. An index's or an architecture overview's `path:` names a
    directory instead (`frontend/src`, `frontend/src/components`), and counting one of those would mark
    every file beneath it as covered — which is how a scaffolder reports nothing left to do.
    """
    covered: set[str] = set()
    for doc in ATLAS_ROOT.rglob("*.md"):
        text = doc.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"^path:\s*(.+)$", text, re.MULTILINE)
        if not match:
            continue
        for segment in match.group(1).split("+"):
            segment = segment.strip().strip("`").strip()
            if segment.endswith(SOURCE_SUFFIXES):
                covered.add(segment)
    return covered


def is_covered(rel: str, covered: set[str]) -> bool:
    """True when some doc's `path:` names this exact source file."""
    return rel in covered


def scaffold(section: str, dry_run: bool, covered: set[str]) -> tuple[int, int]:
    src_dir = FRONTEND_SRC / section
    if not src_dir.exists():
        return 0, 0

    target_dir = ATLAS_ROOT / section
    files_written = 0
    dirs_created = 0

    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        rel_root = Path(root).relative_to(src_dir)
        target_root = target_dir / rel_root

        # Skip .stories dirs etc.
        if any(should_skip_dir(p) for p in rel_root.parts):
            continue

        source_files = sorted(f for f in files if is_source_file(Path(f)))
        if not source_files:
            continue

        if not dry_run:
            target_root.mkdir(parents=True, exist_ok=True)
        dirs_created += 1

        for f in source_files:
            src_path = Path(root) / f
            rel = src_path.relative_to(PROJECT_ROOT).as_posix()
            if is_covered(rel, covered):
                continue
            doc_path = target_root / src_path.with_suffix(".md").name
            if doc_path.exists():
                # A doc already sits at the name this file would take: never overwrite live prose.
                continue
            title = file_title(src_path, section)
            content = frontmatter(title, src_path, section) + stub_body(title, src_path, section)
            if not dry_run:
                doc_path.write_text(content, encoding="utf-8")
            files_written += 1

    return files_written, dirs_created


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold wiki/atlas/ui from frontend/src")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    covered = covered_sources()
    print(f"Frontend src: {FRONTEND_SRC}")
    print(f"Atlas target: {ATLAS_ROOT}")
    print(f"Source paths already documented: {len(covered)}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'WRITE'}\n")

    total_files = 0
    total_dirs = 0
    for section in SECTIONS:
        files, dirs = scaffold(section, args.dry_run, covered)
        total_files += files
        total_dirs += dirs
        print(f"  {section:12s}: {files:4d} stub files, {dirs:4d} directories")

    print(f"\nTotal: {total_files} stub files, {total_dirs} directories")
    if args.dry_run:
        print("Dry run — nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
