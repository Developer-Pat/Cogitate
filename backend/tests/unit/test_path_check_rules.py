"""The path gate's raw-open rule, exercised — and the tree asserted against it.

WHY THIS TEST EXISTS
--------------------
`check_path_arithmetic` is a GATE: it blocks a commit and the sweep reads its
findings. A gate whose rules are never exercised has one failure mode that
matters — it keeps reporting clean after the shape it was written for changes.

That is not hypothetical. The raw-open rule looked for the literals `cogitate.db`
and `_shared`, so it reported clean over a locator FIELD DEFAULT opened as a raw
sqlite3 connection: `executor.log_usage` resolved `Paths.shared_db` that way — a
fixed path that ignores DATABASE_URL — and wrote 244 usage rows naming a fixture
agent into the operator's LIVE database, from inside the test suite, over weeks.

So this test pins BOTH halves of the rule: the shapes it must catch, and the
sanctioned forms it must leave alone (`Paths.from_settings(...)`, the
`_shared_db_path()` helper, a per-agent database, a path the caller owns). The
samples live in a data file for the reason stated there: a .py test containing the
sample lines would be flagged by the rule it tests.

The last test asserts the rule over the real tree, so the gate the commit hook
runs and the gate the suite runs cannot disagree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The repo root comes from the Paths locator, never a __file__ crawl — re-deriving
# it by hand is the phantom-path class the gate this module tests exists to stop.
sys.path.insert(0, "backend")
sys.path.insert(0, "scripts/core")

from app.core.config import Paths  # noqa: E402
from sweep import backend as sweep_backend  # noqa: E402

_SAMPLES = Paths.root / "backend" / "tests" / "meta" / "path_rule_samples.txt"


def _cases() -> list[tuple[bool, str, str]]:
    cases: list[tuple[bool, str, str]] = []
    for raw in _SAMPLES.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        verdict, code, why = (part.strip() for part in line.split("::", 2))
        cases.append((verdict == "flag", code, why))
    return cases


_CASES = _cases()


def test_the_samples_say_something():
    """A rule exercised against an empty file passes for the wrong reason."""
    assert len(_CASES) >= 10
    assert any(flag for flag, _, _ in _CASES), "no sample expects a flag"
    assert any(not flag for flag, _, _ in _CASES), "no sample expects to pass"


@pytest.mark.parametrize("expected,code,why", _CASES, ids=[c[2][:40] for c in _CASES])
def test_the_raw_open_rule(expected: bool, code: str, why: str):
    got = bool(sweep_backend.SHARED_DB_RAW_OPEN.search(code))
    assert got is expected, f"{why}\n  expected flag={expected}, got flag={got}\n  line: {code}"


def test_the_samples_cannot_be_flagged_by_their_own_rule():
    """The premise of where the samples live — the gate reads .py files only."""
    assert _SAMPLES.suffix != ".py"


def test_the_tree_passes_the_gate():
    """The rule over the real tree: what the commit hook enforces, enforced here."""
    code, output = sweep_backend.check_path_arithmetic()
    assert code == 0, output
