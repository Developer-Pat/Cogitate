"""The UI-atlas validation gate — frontmatter, stale names, wikilinks and codebase sync.

The atlas validation (scripts/core/check_atlas_validation.py) verifies:
  - frontmatter completeness (atlas docs)
  - stale-name scan (no removed-feature refs, removal records exempt)
  - wikilink resolution (exact -> dir index -> recursive -> html)
  - codebase sync (every doc path: exists)
  - mermaid fence balance

Runs independently (pytest backend/tests/test_atlas_validation.py) and as
part of the full sweep (sweep backend/full includes the same check).
"""
import pytest

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
VALIDATOR = REPO_ROOT / "scripts" / "core" / "check_atlas_validation.py"


def test_atlas_validation_passes():
    """The UI Atlas must pass all validation checks."""
    result = subprocess.run(
        ["python3", str(VALIDATOR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Atlas validation failed (rc={result.returncode})\n"
        f"{result.stdout[-2000:]}\n{result.stderr[-1000:]}"
    )
