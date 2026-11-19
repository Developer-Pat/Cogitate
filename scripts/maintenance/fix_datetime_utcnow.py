#!/usr/bin/env python3
"""
Fix datetime.utcnow() deprecation across the backend.

Replaces:
  - datetime.utcnow()  →  datetime.now(UTC)
  - __import__('datetime').datetime.utcnow()  →  datetime.now(UTC)

Also adds UTC to the import where needed:
  - from datetime import datetime  →  from datetime import datetime, UTC
  - from datetime import datetime, timezone  →  from datetime import datetime, timezone, UTC
  - from datetime import datetime, timedelta  →  from datetime import datetime, timedelta, UTC

Skips files where UTC is already imported (already fixed).
"""

import os
import re
import sys

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
DRY_RUN = "--dry-run" in sys.argv

IMPORT_WITH_UTC_RE = re.compile(r"^from datetime import .*\bUTC\b")
IMPORT_DATETIME_ONLY_RE = re.compile(r"^from datetime import datetime\s*$")
IMPORT_DATETIME_WITH_OTHERS_RE = re.compile(r"^(from datetime import datetime(?:,\s*\w+)*)\s*$")
IMPORT_DATETIME_NO_YET_RE = re.compile(r"^(from datetime import datetime(?:,\s*\w+)*)")

# Track which files need __import__ fix but don't have proper imports yet
NEEDS_IMPORT_FIX = re.compile(r"__import__\('datetime'\)\.datetime\.utcnow\(\)")


def fix_imports(content: str) -> tuple[str, bool]:
    """Add UTC to the import line if needed."""
    lines = content.split("\n")
    changed = False

    # Check if UTC is already imported somewhere
    for line in lines:
        if IMPORT_WITH_UTC_RE.search(line):
            return content, False

    # Find the datetime import line and add UTC
    for i, line in enumerate(lines):
        # Match any from datetime import ... that doesn't have UTC yet
        m = IMPORT_DATETIME_WITH_OTHERS_RE.match(line)
        if m:
            import_part = m.group(1)
            new_import = import_part + ", UTC"
            lines[i] = new_import
            changed = True
            break

    return "\n".join(lines), changed


def needs_import_fix(content: str) -> bool:
    """Check if file uses __import__ pattern and needs a proper import added."""
    return bool(NEEDS_IMPORT_FIX.search(content))


def fix_import_router_file(content: str) -> tuple[str, bool]:
    """Fix __import__('datetime').datetime.utcnow() → datetime.now(UTC) + add import."""
    changed = False
    
    if not needs_import_fix(content):
        return content, False

    # Replace the __import__ pattern
    content = content.replace(
        "__import__('datetime').datetime.utcnow()",
        "datetime.now(UTC)"
    )
    changed = True

    # Add the import line after existing imports
    lines = content.split("\n")
    has_utc_import = False
    has_datetime_import = False
    last_import_line = -1

    for i, line in enumerate(lines):
        if line.startswith("from datetime import"):
            has_datetime_import = True
            if "UTC" in line:
                has_utc_import = True
            last_import_line = i
        elif line.startswith("import ") or line.startswith("from "):
            last_import_line = i

    if not has_datetime_import and not has_utc_import:
        # Add from datetime import datetime, UTC after the last import line
        insert_at = last_import_line + 1 if last_import_line >= 0 else 0
        lines.insert(insert_at + 1, "from datetime import datetime, UTC")
        changed = True
    elif has_datetime_import and not has_utc_import:
        # Fix the existing import
        lines[last_import_line] = fix_imports(lines[last_import_line])[0]
        changed = True

    return "\n".join(lines), changed


def fix_content_utcnow(content: str) -> tuple[str, bool]:
    """Replace datetime.utcnow() with datetime.now(UTC)."""
    # Handle __import__('datetime').datetime.utcnow() → datetime.now(UTC)
    # These files don't have a proper import, so the full pattern must be replaced
    if "__import__('datetime').datetime.utcnow()" in content:
        # This is handled by fix_import_router_file which also adds import
        pass

    if "datetime.utcnow()" not in content:
        return content, False

    content = content.replace("datetime.utcnow()", "datetime.now(UTC)")
    return content, True


def process_file(filepath: str) -> bool:
    """Process a single file. Returns True if changes were made."""
    with open(filepath, "r") as f:
        content = f.read()

    content_changed = False
    import_changed = False

    # Check for __import__ pattern first (these need special handling)
    if needs_import_fix(content):
        content, content_changed = fix_import_router_file(content)
    else:
        # Fix content
        content, content_changed = fix_content_utcnow(content)

        # Fix imports if needed
        if content_changed:
            content, import_changed = fix_imports(content)

    if not content_changed and not import_changed:
        return False

    if DRY_RUN:
        relpath = os.path.relpath(filepath, os.path.join(BACKEND_DIR, ".."))
        print(f"[DRY RUN] Would fix: {relpath} (content_changed={content_changed}, import_changed={import_changed})")
        return False

    with open(filepath, "w") as f:
        f.write(content)

    relpath = os.path.relpath(filepath, os.path.join(BACKEND_DIR, ".."))
    print(f"✅ Fixed: {relpath}")
    return True


def main():
    """Find and fix all backend .py files with datetime.utcnow()."""
    if DRY_RUN:
        print("🔍 DRY RUN - no files will be modified\n")

    fixed_count = 0
    error_count = 0
    skipped = 0

    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip .venv and __pycache__
        dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules")]

        for fname in files:
            if not fname.endswith(".py"):
                continue

            filepath = os.path.join(root, fname)

            try:
                with open(filepath, "r") as f:
                    content = f.read()

                if "utcnow()" not in content:
                    continue

                if not process_file(filepath):
                    if "utcnow()" in content:
                        skipped += 1
                    continue

                fixed_count += 1
            except Exception as e:
                print(f"❌ Error processing {fname}: {e}", file=sys.stderr)
                error_count += 1

    print(f"\n{'='*50}")
    print(f"Summary: {fixed_count} files fixed, {error_count} errors, {skipped} already clean")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
