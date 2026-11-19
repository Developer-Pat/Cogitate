#!/usr/bin/env python3
"""
Bulk-fix TS6133 (unused declarations) errors across the frontend.

Reads `npx tsc -b` output from stdin and applies mechanical fixes.

Usage:
    cd frontend && npx tsc -b 2>&1 | python3 ../scripts/dev/fix_ts6133.py
"""

import re
import sys
from collections import defaultdict
from pathlib import Path


def parse_errors(lines: list[str]) -> list[dict]:
    error_pattern = re.compile(
        r"^(?P<file>src/[^:]+)\((?P<line>\d+),(?P<col>\d+)\): error TS6133: "
        r"'(?P<name>[^']+)' is declared but its value is never read\.$"
    )
    return [m.groupdict() for line in lines if (m := error_pattern.match(line.strip()))]


def remove_from_list(names_str: str, name_to_remove: str) -> str | None:
    """Remove a name from a comma-separated list. Returns None if unchanged."""
    names = [n.strip() for n in names_str.split(",")]
    filtered = [n for n in names if n.strip().split(":")[0].strip().split(" as ")[0].strip() != name_to_remove]
    if len(filtered) == len(names):
        return None
    if filtered:
        return ", ".join(filtered)
    return ""  # empty = remove whole line


def fix_file(filepath: Path, error_names: list[tuple[int, str]]) -> int:
    original = filepath.read_text()
    lines = original.split("\n")
    fixes = 0
    error_names.sort(key=lambda x: x[0], reverse=True)

    for line_no, name in error_names:
        idx = line_no - 1
        if idx >= len(lines):
            continue
        line = lines[idx]

        # --- Pattern 1: import { X, Y } from 'z' (remove X) ---
        m = re.match(r"^(\s*import\s+(?:type\s+)?)\{([^}]*)\}(\s+from\s+.+)$", line)
        if m:
            result = remove_from_list(m.group(2), name)
            if result is not None:
                if result:
                    lines[idx] = f"{m.group(1)}{{{result}}}{m.group(3)}"
                else:
                    lines[idx] = ""
                fixes += 1
                continue

        # --- Pattern 2: import Foo from 'bar' (remove line) ---
        m = re.match(r"^(\s*)import\s+(\w+)\s+from\s+['\"]", line)
        if m and m.group(2) == name:
            lines[idx] = ""
            fixes += 1
            continue

        # --- Pattern 3: const { x, y, ... }: Type = expr  (object destructuring) ---
        # With or without type annotation
        m = re.match(r"^(\s*)(const|let|var)\s+\{([^}]*)\}(\s*:\s*[^{=]+)?\s*=\s*(.+?);?\s*$", line)
        if m:
            indent, keyword, names_str, _, rhs = m.groups()
            result = remove_from_list(names_str, name)
            if result is not None:
                if result:
                    lines[idx] = f"{indent}{keyword} {{ {result} }} = {rhs};"
                else:
                    lines[idx] = ""
                fixes += 1
                continue

        # --- Pattern 4: [x, y] = ... array destructuring ---
        m = re.match(r"^(\s*)(const|let|var)\s+\[([^\]]*)\]\s*=\s*(.+?);?\s*$", line)
        if m:
            indent, keyword, names_str, rhs = m.groups()
            names = [n.strip() for n in names_str.split(",")]
            changed = False
            result = []
            for n in names:
                if n == name:
                    changed = True
                    result.append("")
                else:
                    result.append(n)
            if changed:
                parts = ", ".join(result).rstrip(", ")
                lines[idx] = f"{indent}{keyword} [{parts}] = {rhs};"
                fixes += 1
                continue

        # --- Pattern 5: function param destructuring: function Foo({ x, y, ... }: Props) ---
        m = re.match(r"^(\s*)(?:function\s+\w+\s*)?\(?\s*\{([^}]*)\}(\s*:\s*\w+)?\s*\)?\s*(?::\s*\w+)?\s*\{?\s*$", line)
        if m and '{' in line and '=>' not in line:
            result = remove_from_list(m.group(2), name)
            if result is not None:
                if result:
                    lines[idx] = f"{m.group(1)}{{{result}}}{m.group(3) or ''}" + '{' if '{' in line.split('{', 1)[1] else ''
                    # Reconstruct carefully
                    before_brace = line.split('{')[0]
                    after_brace = line.split('}')[1] if '}' in line else ''
                    lines[idx] = f"{before_brace}{{{result}}}{after_brace}"
                fixes += 1
                continue

        # --- Pattern 6: Arrow function param: ({ x, ... }) => ... or ({ x }: Type) => ... ---
        m = re.match(r"^(\s*)\(\s*\{([^}]*)\}(\s*:\s*[^)]+)?\s*\)\s*=>", line)
        if m:
            result = remove_from_list(m.group(2), name)
            if result is not None:
                if result:
                    type_anno = m.group(3) or ""
                    lines[idx] = f"{m.group(1)}({{ {result} }}{type_anno}) =>" + line.split("=>", 1)[1]
                fixes += 1
                continue

        # --- Pattern 7: Simple variable: const x = ... (no function calls in RHS) ---
        m = re.match(r"^(\s*)(const|let|var)\s+(\w+)\s*=\s*([^;(]+);?\s*$", line)
        if m and m.group(3) == name:
            rhs = m.group(4).strip()
            if not any(c in rhs for c in ("(", "await ", "new ", "import(")):
                lines[idx] = ""
                fixes += 1
                continue

        print(f"  ⚠ Cannot auto-fix '{name}' at {filepath}:{line_no}", file=sys.stderr)

    if fixes > 0:
        filepath.write_text("\n".join(lines))
    return fixes


def main():
    errors = parse_errors(sys.stdin.readlines())
    if not errors:
        print("No TS6133 errors found.", file=sys.stderr)
        return

    print(f"Found {len(errors)} TS6133 errors.\n", file=sys.stderr)

    by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for err in errors:
        by_file[err["file"]].append((int(err["line"]), err["name"]))

    total = 0
    for filepath_str, err_list in sorted(by_file.items()):
        full = Path(filepath_str)
        if not full.exists():
            print(f"  ⚠ File not found: {full}", file=sys.stderr)
            continue
        n = fix_file(full, err_list)
        if n:
            print(f"  ✓ {filepath_str}: {n} fix(es)", file=sys.stderr)
        total += n

    print(f"\nTotal: {total}/{len(errors)} errors auto-fixed.", file=sys.stderr)


if __name__ == "__main__":
    main()