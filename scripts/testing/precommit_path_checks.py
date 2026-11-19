#!/usr/bin/env python3
"""The path gates, as a pre-commit entry point.

Runs the checks the sweep already owns, so a commit cannot introduce a path that
escapes the resolver, names a specific machine, or names a module that is not
there:

  check_path_arithmetic     — hand-computed path arithmetic (the phantom-DB class)
  check_absolute_paths      — absolute paths, which leak a username and a layout
  check_module_specifiers   — frontend module specifiers that resolve to nothing

Kept as a script rather than inlined in .pre-commit-config.yaml: a multi-line
python -c inside YAML is a syntax trap, and a hook that is hard to read is a hook
nobody trusts.

Exit code is non-zero if any check fails, which is what makes the commit stop.

Run it by hand any time:
    python3 scripts/testing/precommit_path_checks.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_DIR = REPO_ROOT / "scripts" / "core" / "sweep"


def _load_module(module_name: str, path: Path):
    """Import a sweep module by file location (the sweep is not an installed package)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "core"))
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    backend = REPO_ROOT / "backend"
    sweep_backend = _load_module("sweep_backend", SWEEP_DIR / "backend.py")
    sweep_frontend = _load_module("sweep_frontend", SWEEP_DIR / "frontend.py")

    # The backend checks read the tree relative to the backend dir; the frontend check resolves its
    # own tree by absolute path, so this working directory does not change what it examines.
    import os

    os.chdir(backend)

    failed = 0
    for check, label in (
        (sweep_backend.check_path_arithmetic, "resolver discipline"),
        (sweep_backend.check_absolute_paths, "absolute paths"),
        (sweep_frontend.check_module_specifiers, "module specifiers resolve (frontend)"),
    ):
        try:
            code, output = check()
        except Exception as exc:  # noqa: BLE001 — never let the hook crash a commit
            print(f"--- {label}: the check itself failed to run ---")
            print(f"    {type(exc).__name__}: {exc}")
            failed = 1
            continue
        if code:
            failed = 1
            print(f"--- {label} ---")
            print(output)

    if failed:
        print("\nThese are the project's path rules. See:")
        print("  wiki/dev-notes/testing/test-isolation.md")
        print("  wiki/dev-notes/architecture/Paths and Path Resolution.md")
        print("  (a frontend module specifier must resolve — name it by the `@/` alias)")
        print("\nTo commit anyway (a work-in-progress commit): git commit --no-verify")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
