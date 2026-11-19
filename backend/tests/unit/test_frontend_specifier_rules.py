"""The frontend module-specifier gate, exercised — and the real tree asserted against it.

WHY THIS TEST EXISTS
--------------------
`check_module_specifiers` is a GATE: it blocks a commit (the path-checks pre-commit hook) and the
frontend sweep runs it. A gate whose rules are never exercised has one failure mode that matters —
it keeps reporting clean after the shape it was written for changes, or after it stops looking.

That is not hypothetical here. The failure this gate was built for was found live: four test files
mocked a module at a path that did not exist (three of them `'../../services/frontendLoggingService'`
→ a doubled `services/`, one `'./TraceService'` → a file that lives one level up), and **the mock
silently did not apply — the real service ran inside the tests, with no error and no warning.** The
climb sweep that found the first three could not see the fourth: its rule was `(\\.\\./){2,}`, and a
`./` reference is not a climb. Hence a gate that asks the question covering all of them: does it
resolve?

So this test pins BOTH halves: the shapes it must catch, and the sanctioned forms it must leave
alone (the alias, a relative path that exists, an index directory, a bare package name, a Vite
query suffix). The samples are built in a tmp tree rather than kept as files under `frontend/src`,
because samples living in the scanned tree would be flagged by the rule they test.

The last test runs the rule over the REAL tree, so the gate the commit hook runs and the gate the
suite runs cannot disagree.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "scripts/core")

# The sweep is a script tree, not a typed package, and it is outside the hook's mypy scope
# (`cd backend && uv run mypy app`). The ignore keeps this file's own type report honest.
from sweep.frontend import (  # type: ignore[import-not-found]
    check_module_specifiers,
    module_specifier_findings,
)
from sweep.shared import FRONTEND_DIR  # type: ignore[import-not-found]


def _tree(tmp_path: Path) -> Path:
    """A small frontend tree: one file per shape the gate must judge."""
    src = tmp_path / "src"
    (src / "services").mkdir(parents=True)
    (src / "types").mkdir(parents=True)
    (src / "lib" / "ui").mkdir(parents=True)
    (src / "styles").mkdir(parents=True)

    # everything the gate must LEAVE ALONE
    (src / "services" / "thing.ts").write_text("export const thing = 1\n", encoding="utf-8")
    (src / "types" / "models.ts").write_text("export type M = 1\n", encoding="utf-8")
    (src / "lib" / "ui" / "index.ts").write_text("export const ui = 1\n", encoding="utf-8")
    (src / "styles" / "app.css").write_text("body {}\n", encoding="utf-8")

    (src / "good.ts").write_text(
        "\n".join(
            [
                "import { thing } from '@/services/thing'",          # alias
                "import type { M } from './types/models'",           # relative, same level up
                "import { ui } from '@/lib/ui'",                     # a directory's index
                "import { css } from '@/styles/app.css?inline'",     # Vite query suffix
                "import { describe, it, vi } from 'vitest'",         # a package — not ours to resolve
                "import { readFileSync } from 'node:fs'",            # a builtin — likewise
                "const lazy = () => import('@/services/thing')",     # dynamic import
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # everything the gate must CATCH
    (src / "bad.test.ts").write_text(
        "\n".join(
            [
                "import { describe, it, vi } from 'vitest'",
                "vi.mock('../../services/thing', () => ({}))",   # climbs past the root of src
                "vi.mock('./TraceService', () => ({}))",         # one level, and not there either
                "const later = () => import('./nope')",          # a dynamic import that names nothing
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return src


def test_it_flags_every_specifier_that_names_nothing(tmp_path):
    findings, checked = module_specifier_findings(_tree(tmp_path))

    assert checked >= 10, "the scan has to actually read the tree"
    assert len(findings) == 3, f"expected exactly the three bad ones, got {findings}"
    assert any("../../services/thing" in f for f in findings), "a climb past the root"
    assert any("./TraceService" in f for f in findings), "a ONE-level reference — the fourth case"
    assert any("./nope" in f for f in findings), "a dynamic import"
    assert all(f.startswith("  src/bad.test.ts:") for f in findings), (
        "findings name the file and line, so a reader can open it"
    )


def test_it_leaves_the_sanctioned_forms_alone(tmp_path):
    findings, _ = module_specifier_findings(_tree(tmp_path))
    for shape in ("@/services/thing", "./types/models", "@/lib/ui", "vitest", "node:fs"):
        assert not any(shape in f for f in findings), f"{shape} resolves and must not be flagged"


def test_the_check_reports_the_count_it_examined(tmp_path, monkeypatch):
    """A gate that says 'clean' must also say how much it looked at — otherwise it cannot be told
    from a gate that stopped looking."""
    import sweep.frontend as sweep_frontend  # type: ignore[import-not-found]

    tree = _tree(tmp_path)
    _findings, checked = module_specifier_findings(tree)

    monkeypatch.setattr(sweep_frontend, "FRONTEND_DIR", tmp_path)
    code, output = check_module_specifiers()

    assert code == 1, "this tree has findings"
    assert f"3 of {checked}" in output, output
    assert "To fix" in output, "a finding without a remedy is a shrug"


def test_a_missing_source_tree_is_reported_not_passed_off_as_clean(tmp_path, monkeypatch):
    """The other branch: no `src/` at all says so, rather than reporting 'all N resolve'."""
    import sweep.frontend as sweep_frontend  # type: ignore[import-not-found]

    monkeypatch.setattr(sweep_frontend, "FRONTEND_DIR", tmp_path / "absent")
    code, output = check_module_specifiers()

    assert code == 0, "a tree that is not there is not a failure"
    assert "no frontend source tree" in output
    assert "✅" not in output


def test_the_real_tree_resolves():
    """The gate the commit hook runs, over the tree as committed."""
    findings, checked = module_specifier_findings(FRONTEND_DIR / "src")

    assert checked > 1000, f"the scan read {checked} specifiers — far too few for frontend/src"
    assert findings == [], "frontend/src must have no specifier that resolves to nothing"


def test_the_hooks_check_and_the_sweeps_check_are_the_same_function():
    """One gate, two callers: the pre-commit hook and the frontend sweep must not grow two rules."""
    import sweep.frontend as sweep_frontend  # type: ignore[import-not-found]

    labels = {label for _fn, label in sweep_frontend.get_all_checks()}
    assert "Frontend: module specifiers resolve" in labels
    assert sweep_frontend.check_module_specifiers in [fn for fn, _l in sweep_frontend.get_all_checks()]
