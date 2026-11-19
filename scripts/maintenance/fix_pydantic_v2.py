#!/usr/bin/env python3
"""
Automated fix for Pydantic V2 deprecations.

Replaces:
  1. `class Config:` inside Pydantic models → `model_config = ConfigDict(...)`
  2. `regex=` keyword in FastAPI Query/Path → `pattern=`

Usage:
    python3 scripts/maintenance/fix_pydantic_v2.py [--dry-run] [files...]

Examples:
    # Run on all known affected files
    python3 scripts/maintenance/fix_pydantic_v2.py

    # Dry run (shows what would change without modifying)
    python3 scripts/maintenance/fix_pydantic_v2.py --dry-run

    # Run on specific files
    python3 scripts/maintenance/fix_pydantic_v2.py backend/app/domain/logs/schemas.py
"""

import ast
import re
import sys
from pathlib import Path
from typing import Optional


# Files known to have class Config: deprecations
AFFECTED_FILES = [
    "backend/app/domain/workflows/schemas/version_config.py",
    "backend/app/domain/logs/schemas.py",
    "backend/app/workflows/agent_versioning/registry.py",
    "backend/app/api/v1/providers/config_router.py",
    "backend/app/api/v1/providers/management_router.py",
    "backend/app/domain/agents/schemas.py",
    "backend/app/workflows/agent_versioning/ab_testing.py",
    "backend/app/workflows/state/workflow_state.py",
    "backend/app/domain/workflows/schemas/composition_config.py",
    "backend/app/domain/workflows/schemas/trigger_config.py",
    "backend/app/domain/workflows/schemas/routing_config.py",
]

# File with regex= → pattern= issue
FASTAPI_ROUTER_FILE = "backend/app/api/v1/providers/models_router.py"

# Known parent class names that are Pydantic models
PYDANTIC_BASES = {"BaseModel"}

# Mapping of Config inner-class attributes to ConfigDict kwargs
CONFIG_ATTR_MAP = {
    "from_attributes": "from_attributes",
    "populate_by_name": "populate_by_name",
    "json_schema_extra": "json_schema_extra",
    "orm_mode": "from_attributes",  # Pydantic V1 compat
}


def file_needs_configdict_import(filepath: Path, source: str) -> bool:
    """Check if the file needs a ConfigDict import added."""
    if "ConfigDict" in source:
        return False
    # Check if file already imports from pydantic
    return "from pydantic import" in source


def add_configdict_import(source: str) -> str:
    """
    Add ConfigDict to the pydantic import line.

    Handles:
        from pydantic import BaseModel, Field
        from pydantic import BaseModel
        from pydantic import BaseModel, Field, field_validator
    """
    pattern = re.compile(r'(from pydantic import .*?)(\n)')
    def replacer(m: re.Match) -> str:
        imports = m.group(1)
        if "ConfigDict" not in imports:
            # Add ConfigDict after BaseModel, or at the end
            if "BaseModel" in imports:
                imports = imports.replace("BaseModel", "BaseModel, ConfigDict")
            else:
                imports = imports.rstrip(",") + ", ConfigDict"
        return imports + m.group(2)

    new_source = pattern.sub(replacer, source)
    if new_source == source:
        # No from pydantic import line found; add one after existing imports
        # Find the last import line
        lines = source.split("\n")
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                last_import_idx = i
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, "from pydantic import ConfigDict")
            new_source = "\n".join(lines)
    return new_source


class ConfigClassFinder(ast.NodeVisitor):
    """Finds class Config definitions inside Pydantic model classes."""

    def __init__(self) -> None:
        self.hits: list[tuple[int, int, str, int]] = []  # (start_line, end_line, parent_name, body_length)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Only look at classes that inherit from BaseModel
        base_names = set()
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.add(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.add(base.attr)

        if not base_names & PYDANTIC_BASES:
            # Still visit children to handle nested classes
            self.generic_visit(node)
            return

        for child in ast.walk(node):
            if isinstance(child, ast.ClassDef) and child.name == "Config":
                # Found a class Config inside a Pydantic model
                body_len = len(child.body)
                self.hits.append((
                    child.lineno,
                    child.end_lineno or child.lineno,
                    node.name,
                    body_len,
                ))

        # Don't visit children of Config classes themselves
        self.generic_visit(node)


def parse_config_body(source_lines: list[str], start_line: int, end_line: int) -> Optional[str]:
    """
    Parse the body of a class Config definition and return ConfigDict() kwargs string.

    Handles:
        class Config:
            from_attributes = True

        class Config:
            json_schema_extra = {
                "example": { ... }
            }

        class Config:
            populate_by_name = True

        class Config:
            from_attributes = True
            json_schema_extra = { ... }
    """
    # Extract the body lines (indented content after `class Config:`)
    body_lines: list[str] = []
    for i in range(start_line, end_line + 1):
        if i < len(source_lines):
            line = source_lines[i]
            # Skip the `class Config:` line itself
            if i == start_line - 1:  # 0-indexed adjustment
                continue
            # Check if line is indented (body of Config class)
            stripped = line.strip()
            if stripped and line[0] == ' ':
                body_lines.append(line)

    if not body_lines:
        return None

    # Dedent and parse
    min_indent = min(len(line) - len(line.lstrip()) for line in body_lines if line.strip())
    dedented_lines = [line[min_indent:] for line in body_lines]

    # Join and find assignments
    body_text = "\n".join(dedented_lines)

    # Parse assignments
    kwargs: list[str] = []
    for line in dedented_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Handle multi-line dict values
        if stripped.startswith("json_schema_extra") or stripped.startswith("from_attributes") or stripped.startswith("populate_by_name") or stripped.startswith("orm_mode"):
            attr_match = re.match(r'(from_attributes|populate_by_name|orm_mode|json_schema_extra)\s*=\s*(.+)', stripped, re.DOTALL)
            if attr_match:
                attr_name = attr_match.group(1)
                config_kwarg = CONFIG_ATTR_MAP.get(attr_name, attr_name)
                value = attr_match.group(2).strip().rstrip(",")

                # If json_schema_extra has a multi-line dict, we need to collect it
                if attr_name == "json_schema_extra" and value == "{":
                    # Multi-line dict - find the closing brace
                    full_dict = collect_multiline_dict(dedented_lines, dedented_lines.index(line))
                    if full_dict:
                        kwargs.append(f"json_schema_extra={full_dict}")
                    continue

                kwargs.append(f"{config_kwarg}={value}")

    if not kwargs:
        return None

    return ", ".join(kwargs)


def collect_multiline_dict(lines: list[str], start_idx: int) -> Optional[str]:
    """Collect a multi-line dict literal starting at start_idx."""
    collected: list[str] = []
    brace_count = 0
    started = False

    for i in range(start_idx, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not started:
            # Skip assignment part
            if "=" in stripped:
                _, _, after_eq = stripped.partition("=")
                if after_eq.strip().startswith("{"):
                    collected.append(after_eq.strip())
                    brace_count = after_eq.count("{") - after_eq.count("}")
                    started = True
                    if brace_count <= 0:
                        break
                    continue
            continue

        collected.append(stripped)
        brace_count += stripped.count("{") - stripped.count("}")
        if brace_count <= 0:
            break

    if collected:
        return " ".join(collected)
    return None


def fix_class_config(source: str, filepath: Path) -> tuple[str, int, bool]:
    """
    Replace all class Config: definitions inside Pydantic models with model_config = ConfigDict(...).

    Returns (new_source, replacement_count, needs_configdict_import).
    """
    lines = source.split("\n")
    tree = ast.parse(source)

    finder = ConfigClassFinder()
    finder.visit(tree)

    if not finder.hits:
        return source, 0, False

    # Process hits in reverse order to preserve line numbers
    hits_sorted = sorted(finder.hits, key=lambda h: h[0], reverse=True)

    changes = 0
    needs_import = False

    for start_line, end_line, parent_name, body_len in hits_sorted:
        # Parse the Config body
        config_kwargs = parse_config_body(lines, start_line, end_line)

        if config_kwargs is None and body_len == 0:
            # Empty Config class - skip
            continue

        if config_kwargs is None:
            config_str = "ConfigDict()"
        else:
            config_str = f"ConfigDict({config_kwargs})"

        # Calculate indentation from the Config class definition
        config_line = lines[start_line - 1]
        indent = " " * (len(config_line) - len(config_line.lstrip()))

        # Replace lines from class Config: to end of Config body
        replacement = f"{indent}model_config = {config_str}"
        new_lines = lines[:start_line - 1] + [replacement] + lines[end_line:]

        if new_lines != lines:
            changes += 1
            needs_import = True

        lines = new_lines

    return "\n".join(lines), changes, needs_import


def fix_regex_kwarg(source: str, filepath: Path) -> tuple[str, int]:
    """
    Replace regex= with pattern= in FastAPI Query/Path/Body decorators.

    This handles: Query(..., regex="^(asc|desc)$") → Query(..., pattern="^(asc|desc)$")
    """
    # Use regex to find regex= as a keyword argument
    pattern = re.compile(r'(Query|Path|Body|Header|Cookie)\s*\((.*?)\)', re.DOTALL)

    def replace_regex(m: re.Match) -> str:
        func_name = m.group(1)
        args = m.group(2)
        new_args = re.sub(r'\bregex\s*=', 'pattern=', args)
        return f"{func_name}({new_args})"

    new_source = pattern.sub(replace_regex, source)
    count = 1 if new_source != source else 0
    return new_source, count


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """Process a single file for Pydantic V2 deprecations."""
    result = {
        "file": str(filepath),
        "config_changes": 0,
        "regex_changes": 0,
        "import_added": False,
        "modified": False,
    }

    if not filepath.exists():
        print(f"  ✗ File not found: {filepath}")
        return result

    source = filepath.read_text(encoding="utf-8")
    original_source = source

    # Fix class Config → model_config = ConfigDict(...)
    source, config_count, needs_import = fix_class_config(source, filepath)
    result["config_changes"] = config_count

    # Add ConfigDict import if needed
    if needs_import and not dry_run:
        new_source = add_configdict_import(source)
        if new_source != source:
            source = new_source
            result["import_added"] = True

    # Fix regex= → pattern=
    if str(filepath) == str(FASTAPI_ROUTER_FILE):
        source, regex_count = fix_regex_kwarg(source, filepath)
        result["regex_changes"] = regex_count

    if source != original_source:
        result["modified"] = True
        if not dry_run:
            filepath.write_text(source, encoding="utf-8")
            print(f"  ✓ {filepath} - {config_count} Config→ConfigDict, {result['regex_changes']} regex→pattern, import_added={result['import_added']}")
        else:
            print(f"  ~ {filepath} - Would apply {config_count} Config→ConfigDict, {result['regex_changes']} regex→pattern")
    else:
        print(f"  - {filepath} - No changes needed")

    return result


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        sys.argv.remove("--dry-run")

    # Determine which files to process
    files_to_process: list[Path] = []
    if len(sys.argv) > 1:
        # Specific files provided as arguments
        for arg in sys.argv[1:]:
            files_to_process.append(Path(arg))
    else:
        # All known affected files
        for f in AFFECTED_FILES:
            files_to_process.append(Path(f))
        files_to_process.append(Path(FASTAPI_ROUTER_FILE))

    print(f"{'[DRY RUN] ' if dry_run else ''}Pydantic V2 Deprecation Fixer")
    print(f"  Files to process: {len(files_to_process)}")
    print()

    total_config = 0
    total_regex = 0
    total_modified = 0

    for filepath in files_to_process:
        result = process_file(filepath, dry_run=dry_run)
        total_config += result["config_changes"]
        total_regex += result["regex_changes"]
        if result["modified"]:
            total_modified += 1

    print()
    print(f"Summary:")
    print(f"  Files modified: {total_modified}")
    print(f"  Config→ConfigDict replacements: {total_config}")
    print(f"  regex→pattern replacements: {total_regex}")

    if dry_run:
        print()
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
