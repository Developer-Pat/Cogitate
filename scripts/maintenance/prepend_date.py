#!/usr/bin/env python3
"""
Prepend Date Script

Prepends a machine-readable date (YYYY-MM-DD) to filenames based on file
creation time, so files collate chronologically when sorted alphabetically.

This is useful for documentation files that accumulate over time and become
difficult to sort by date or sequence.

Behavior for files that already have a date prefix:
  - Extracts the existing date and compares it against the file's actual
    timestamp.
  - If the existing date matches → skipped (already correct).
  - If the existing date differs → the old date is replaced with the correct
    one.  The file is never left with two date prefixes.

Usage:
    python prepend_date.py [options] [path ...]

Examples:
    # Dry-run on all .md files in a directory (recursive)
    python prepend_date.py --dry-run ./docs/

    # Prepend dates to all .md files in a directory recursively
    python prepend_date.py ./docs/

    # Prepend dates to .md files in multiple directories
    python prepend_date.py ./reports/ ./issues/

    # Use a different extension
    python prepend_date.py --ext .txt ./notes/

    # Non-recursive (top-level only)
    python prepend_date.py --no-recursive ./docs/

Options:
    --dry-run, -n           Show what would be renamed without making changes
    --ext, -e EXT           File extension to target (default: .md)
    --recursive, -r         Process directories recursively (default: True)
    --no-recursive          Process only the top-level directory
    --force, -f             Re-process files even if the existing date prefix
                            matches the file's actual timestamp
    --date-source {ctime,mtime,atime}
                            Which timestamp to use (default: ctime)
                            ctime = inode change time (Linux) / creation (macOS)
                            mtime = last modification time
                            atime = last access time
    --help, -h              Show this help message and exit

Notes:
    - Files that already have a YYYY-MM-DD- or YYYY-MM-DD_ prefix are
      checked: if the existing date matches the file's actual timestamp, the
      file is skipped.  If it differs, the prefix is corrected.
    - On Linux, st_ctime is the inode change time, not the creation time.
      For true creation time on Linux, use --date-source mtime or rely on
      the filesystem's btime (birth time) if available.
    - The script skips hidden files (starting with '.') and common
      non-document files (e.g., .gitkeep, README.md at root).
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

# Matches YYYY-MM-DD followed by either a dash or underscore.
# Both conventions are used in the wild (e.g. 2026-06-21-report.md
# and 2026-06-21_report.md).
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[-_](.*)$")

SKIP_FILES = {
    ".gitkeep",
    ".gitignore",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
}

SKIP_EXTENSIONS = {
    ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".woff", ".woff2",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_timestamp(path: Path, source: str) -> float:
    """Get the file timestamp based on the chosen source."""
    stat = path.stat()
    if source == "ctime":
        return stat.st_ctime
    elif source == "mtime":
        return stat.st_mtime
    elif source == "atime":
        return stat.st_atime
    else:
        raise ValueError(f"Unknown date-source: {source}")


def _format_date(timestamp: float) -> str:
    """Format a Unix timestamp as YYYY-MM-DD."""
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _parse_existing_date(name: str) -> tuple[str | None, str]:
    """
    If *name* starts with YYYY-MM-DD-, return (existing_date, rest_of_name).
    Otherwise return (None, name).
    """
    m = DATE_PREFIX_RE.match(name)
    if m:
        return m.group(1), m.group(2)
    return None, name


def _should_skip(path: Path) -> bool:
    """Determine if a file should be skipped entirely."""
    # Skip hidden files/directories
    if path.name.startswith("."):
        return True

    # Skip known non-document files
    if path.name in SKIP_FILES:
        return True

    # Skip files with non-document extensions
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    return False


def _collect_files(
    root: Path,
    extension: str,
    recursive: bool,
) -> list[Path]:
    """Collect all files matching the extension under root."""
    files: list[Path] = []

    if recursive:
        iterator = root.rglob(f"*{extension}")
    else:
        iterator = root.glob(f"*{extension}")

    for path in sorted(iterator):
        if path.is_file() and not _should_skip(path):
            files.append(path)

    return files


# ── Core Logic ───────────────────────────────────────────────────────────────


def prepend_date(
    path: Path,
    *,
    extension: str = ".md",
    recursive: bool = True,
    dry_run: bool = False,
    force: bool = False,
    date_source: str = "ctime",
) -> tuple[int, int, int]:
    """
    Prepend date prefixes to files under *path*.

    Args:
        path: Directory or file to process.
        extension: File extension to target (e.g. '.md').
        recursive: Whether to recurse into subdirectories.
        dry_run: If True, only print what would be done.
        force: If True, re-process files even if the existing date prefix
               matches the file's actual timestamp.
        date_source: Which timestamp to use ('ctime', 'mtime', 'atime').

    Returns:
        (files_found, files_renamed, files_skipped_correct) tuple.
    """
    if path.is_file():
        targets = [path]
    elif path.is_dir():
        targets = _collect_files(path, extension, recursive)
    else:
        print(f"Warning: {path} does not exist, skipping")
        return 0, 0, 0

    found = len(targets)
    renamed = 0
    skipped_correct = 0

    for filepath in targets:
        name = filepath.name

        # ── Check for existing date prefix ──────────────────────────────
        existing_date, rest = _parse_existing_date(name)

        # Get the file's actual timestamp
        try:
            ts = _get_timestamp(filepath, date_source)
        except OSError as e:
            print(f"  ⚠ Could not read timestamp for {filepath}: {e}")
            continue

        actual_date = _format_date(ts)

        # ── Decide what to do ───────────────────────────────────────────
        if existing_date is not None:
            if existing_date == actual_date and not force:
                # Date is already correct — skip
                skipped_correct += 1
                continue

            # Date is wrong (or force) — replace the prefix
            new_name = f"{actual_date}-{rest}"
        else:
            # No existing prefix — prepend
            new_name = f"{actual_date}-{name}"

        new_path = filepath.parent / new_name

        # Safety: don't overwrite an existing file
        if new_path.exists() and new_path != filepath:
            print(f"  ⚠ Target already exists, skipping: {new_path}")
            continue

        if dry_run:
            if existing_date is not None and existing_date != actual_date:
                print(f"  Would correct: {filepath} → {new_path}  (was {existing_date}, actual {actual_date})")
            elif existing_date is not None and force:
                print(f"  Would re-apply (--force): {filepath} → {new_path}")
            else:
                print(f"  Would rename: {filepath} → {new_path}")
        else:
            try:
                filepath.rename(new_path)
                if existing_date is not None and existing_date != actual_date:
                    print(f"  ✓ Corrected: {filepath} → {new_path}  (was {existing_date}, actual {actual_date})")
                elif existing_date is not None and force:
                    print(f"  ✓ Re-applied (--force): {filepath} → {new_path}")
                else:
                    print(f"  ✓ Renamed: {filepath} → {new_path}")
            except OSError as e:
                print(f"  ✗ Error renaming {filepath}: {e}")
                continue

        renamed += 1

    return found, renamed, skipped_correct


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Prepend YYYY-MM-DD date prefix to filenames based on file creation time.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --dry-run ./docs/\n"
            "  %(prog)s ./reports/ ./issues/\n"
            "  %(prog)s --ext .txt --no-recursive ./notes/\n"
            "  %(prog)s --force --date-source mtime ./docs/\n"
        ),
    )

    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="One or more directories or files to process (default: current directory)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be renamed without making changes",
    )

    parser.add_argument(
        "--ext",
        "-e",
        default=".md",
        help="File extension to target (default: .md)",
    )

    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        dest="recursive",
        default=True,
        help="Process directories recursively (default: True)",
    )

    parser.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Process only the top-level directory",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Re-process files even if the existing date prefix matches the file's actual timestamp",
    )

    parser.add_argument(
        "--date-source",
        choices=["ctime", "mtime", "atime"],
        default="ctime",
        help=(
            "Which timestamp to use (default: ctime). "
            "On Linux, ctime is inode change time, not creation time. "
            "Use mtime for last-modified ordering."
        ),
    )

    return parser.parse_args(argv)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.dry_run:
        print("DRY RUN — No files will be modified\n")

    total_found = 0
    total_renamed = 0
    total_skipped_correct = 0

    for raw_path in args.paths:
        path = Path(raw_path).resolve()

        if not path.exists():
            print(f"Warning: {path} does not exist, skipping")
            continue

        found, renamed, skipped_correct = prepend_date(
            path,
            extension=args.ext,
            recursive=args.recursive,
            dry_run=args.dry_run,
            force=args.force,
            date_source=args.date_source,
        )
        total_found += found
        total_renamed += renamed
        total_skipped_correct += skipped_correct

    # Summary
    print()
    print(f"Summary: {total_found} files found, {total_renamed} renamed, {total_skipped_correct} already correct")

    if total_found == 0:
        print("No matching files found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
