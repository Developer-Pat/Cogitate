"""
The test catalog and the report parser — the user-testing page's data substrate.

THE USER-TESTING PAGE. Two things are being pinned here:

1. **The derivation classifies correctly AND does not over-classify.** The
   catalog reads descriptions, clusters, time classes and conditions out of the
   test tree. A derivation that mis-reads is worse than none, because the page
   then states something false with a straight face — so each rule gets a case
   that it fires on and a case it must stay quiet about.

2. **The report parser reads the real format, including its variations.** The
   parser was written against reports on disk and one real bug was found this
   way: pytest appends a human duration (`in 136.29s (0:02:16)`) to LONG runs
   and not to short ones, so a pattern expecting the line to end after `in Xs`
   read every long run as having no counts at all. The tests below cover both
   shapes so that cannot come back.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.domain.testing import catalog as catalog_mod
from app.domain.testing.catalog import (
    MEDIUM,
    SHORT,
    TAB_CONDITIONAL,
    TAB_QUARANTINE,
    TAB_RUNNABLE,
    VARIABLE,
    _cluster_for,
    _first_line,
    _label_for,
    _time_class_for,
)
from app.domain.testing.reports import parse_report


# ── the description: read from the docstring, never invented ────────────────


def test_description_is_the_docstrings_first_line() -> None:
    """The catalog's prose is the module docstring — that is the whole reason
    there is nothing to keep in sync by hand."""
    doc = "The shutdown contract tests.\n\nMore detail here.\n"
    assert _first_line(doc) == "The shutdown contract tests."


def test_description_skips_leading_blank_lines() -> None:
    assert _first_line("\n\n   The real first line.\n") == "The real first line."


def test_a_missing_docstring_is_empty_not_invented() -> None:
    """An absent description must read as ABSENT. The page shows 'no docstring'
    rather than a plausible-sounding guess, because a guess is a lie."""
    assert _first_line(None) == ""
    assert _first_line("") == ""
    assert _first_line("   \n  \n") == ""


def test_a_long_first_line_is_truncated_not_wrapped() -> None:
    long = "x" * 300
    out = _first_line(long)
    assert len(out) <= 120
    assert out.endswith("…")


# ── the cluster: derived from the path, mechanically ────────────────────────


def test_a_flat_unit_file_takes_its_domain_from_its_name() -> None:
    """`unit/` is the catch-all — 81 files with no subdirectory, each carrying
    its domain in its name. Without this the whole flat set collapses into one
    81-file cluster, which groups nothing."""
    assert _cluster_for(("unit", "test_agent_kits.py"), "test_agent_kits.py") == "unit/agent"


def test_a_file_in_a_subdirectory_takes_the_directory() -> None:
    assert (
        _cluster_for(("unit", "tools", "test_x.py"), "test_x.py") == "unit/tools"
    )


def test_a_non_flat_group_keeps_its_directory() -> None:
    """`workflows/` is already a coherent domain, so its files are NOT split by
    name — 28 files would become 28 clusters, which is the same as no grouping."""
    assert _cluster_for(("workflows", "test_ab_join.py"), "test_ab_join.py") == "workflows"


def test_a_root_level_file_gets_a_name_not_an_empty_string() -> None:
    """Caught live: `"/".join(())` is `""`, which produced an unnamed cluster
    holding two files. A blank label in the UI is a bug, not a cosmetic issue."""
    assert _cluster_for(("test_health.py",), "test_health.py") == "tests (root)"
    assert _cluster_for(("test_health.py",), "test_health.py") != ""


def test_cluster_labels_are_mechanical() -> None:
    assert _label_for("unit/cognitive_pipeline") == "Cognitive Pipeline"
    assert _label_for("workflows") == "Workflows"


# ── the time class: a DEPENDENCY class, never a stopwatch ───────────────────


def test_a_pure_logic_test_is_short() -> None:
    assert _time_class_for("def test_x(): assert 1 == 1", []) == SHORT


@pytest.mark.parametrize(
    "signal",
    ["from sqlalchemy import select", "import aiosqlite", "AsyncSession",
     "from fastapi.testclient import TestClient", "tmp_path"],
)
def test_local_io_raises_the_class_to_medium(signal: str) -> None:
    """Evidence of the WORK, not merely an import of a library. Each of these
    means the test really touches the database, the app, or the filesystem."""
    assert _time_class_for(f"def test_x():\n    {signal}", []) == MEDIUM


def test_importing_pathlib_does_NOT_make_a_test_medium() -> None:
    """THE OVER-CLASSIFICATION CASE, and it was a real bug: `pathlib` was
    initially a signal, and since nearly every test imports it, 122 of 169 files
    came back `medium` — a class that then says nothing. The evidence for file
    work is the FIXTURE (`tmp_path`), which only appears when a test really
    touches the filesystem."""
    assert _time_class_for("import pathlib\ndef test_x(): pass", []) == SHORT


def test_an_external_marker_beats_every_other_signal() -> None:
    """A file that talks to a service is `variable` no matter what else it
    imports — the network dominates, so our CPU is irrelevant."""
    src = "from sqlalchemy import select\nAsyncSession\n"
    assert _time_class_for(src, ["external"]) == VARIABLE


def test_markers_are_read_from_the_AST_not_the_text() -> None:
    """THE LOOKALIKE GUARD, and it was a real bug: a regex over the source
    matched markers inside STRING LITERALS — this project's own gate test holds
    `'@pytest.mark.external("nonsense-service")'` as test DATA, and the catalog
    reported that file as needing a service called "nonsense-service"."""
    import ast as _ast

    from app.domain.testing.catalog import _markers_from_ast

    src = (
        'MARKER_TEXT = \'@pytest.mark.external("nonsense-service")\'\n'
        'def test_x():\n'
        '    assert "@pytest.mark.backend" in MARKER_TEXT\n'
    )
    names, deps = _markers_from_ast(_ast.parse(src))
    assert names == set(), f"a string literal was read as a marker: {names}"
    assert deps == set(), f"a string literal yielded a dependency: {deps}"


def test_real_markers_are_read_from_decorators_and_pytestmark() -> None:
    """The two shapes pytest actually honours, both recognised."""
    import ast as _ast

    from app.domain.testing.catalog import _markers_from_ast

    src = (
        'import pytest\n'
        'pytestmark = pytest.mark.external("ollama")\n'
        '@pytest.mark.backend\n'
        'def test_x(): pass\n'
    )
    names, deps = _markers_from_ast(_ast.parse(src))
    assert names == {"backend", "external"}
    assert deps == {"ollama"}


# ── the report parser: the real format, and its variations ──────────────────


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "test-run-20260101-000000.md"
    p.write_text(textwrap.dedent(body))
    return p


def test_a_short_run_summary_parses(tmp_path: Path) -> None:
    p = _write(tmp_path, """\
        # Test run — 20260101-000000
        group: api  parallel: True  files: 14
        backend: healthy

        74 passed, 1 warning, 2 errors in 19.47s

        ---
        ELAPSED: 31.2s  EXIT: 1
    """)
    r = parse_report(p)
    assert r.parsed
    assert r.group == "api"
    assert r.parallel is True
    assert r.counts["passed"] == 74
    assert r.counts["errors"] == 2
    assert r.duration_s == pytest.approx(19.47)
    assert r.exit_code == 1
    assert r.backend == "healthy"


def test_a_long_run_with_the_human_duration_suffix_parses(tmp_path: Path) -> None:
    """THE REGRESSION CASE. pytest appends `(0:02:16)` to long runs only, and a
    pattern expecting the line to end after `in Xs` read every long run as
    having NO counts — three historical reports came back empty before this was
    caught."""
    p = _write(tmp_path, """\
        # Test run — 20260101-000000
        group: all  parallel: True  files: 138
        backend: healthy

        1140 passed, 7 skipped, 40 warnings in 136.29s (0:02:16)

        ---
        ELAPSED: 147.0s  EXIT: 0
    """)
    r = parse_report(p)
    assert r.parsed
    assert r.counts["passed"] == 1140
    assert r.counts["skipped"] == 7
    assert r.duration_s == pytest.approx(136.29)
    assert r.exit_code == 0


def test_skips_are_kept_WITH_their_reasons(tmp_path: Path) -> None:
    """The point of the whole page: a skip is EVIDENCE when it carries why.
    'Needs Ollama' is actionable where a bare count is not."""
    p = _write(tmp_path, """\
        # Test run — 20260101-000000
        group: live  parallel: False  files: 3
        backend: healthy

        SKIPPED [1] tests/unit/test_x.py:42: Ollama not reachable — the live test needs local embeddings

        2 passed in 1.00s

        ---
        ELAPSED: 2.0s  EXIT: 0
    """)
    r = parse_report(p)
    assert len(r.skips) == 1
    assert "Ollama not reachable" in r.skips[0]["reason"]
    assert r.skips[0]["where"] == "tests/unit/test_x.py"


def test_failures_are_captured_with_their_reason(tmp_path: Path) -> None:
    p = _write(tmp_path, """\
        # Test run — 20260101-000000
        group: unit  parallel: True  files: 9
        backend: healthy

        FAILED tests/unit/test_y.py::test_z - AssertionError: nope

        1 failed, 8 passed in 3.00s

        ---
        ELAPSED: 4.0s  EXIT: 1
    """)
    r = parse_report(p)
    assert len(r.failures) == 1
    assert r.failures[0]["kind"] == "FAILED"
    assert "AssertionError" in r.failures[0]["why"]


def test_an_unrecognisable_report_is_flagged_NOT_silently_empty(tmp_path: Path) -> None:
    """A sweep report has no `# Test run —` header. It must come back
    `parsed: False` WITH a note, never as an empty-but-normal-looking run —
    a report that exists and reads as missing is worse than one that reads odd."""
    p = _write(tmp_path, """\
        # Sweep — backend — 20260101-000000

        some sweep output
    """)
    r = parse_report(p)
    assert r.parsed is False
    assert r.note is not None
    assert "summary" in r.note


def test_an_unreadable_file_returns_a_note_rather_than_raising(tmp_path: Path) -> None:
    r = parse_report(tmp_path / "does-not-exist.md")
    assert r.parsed is False
    assert r.note is not None


# ── the catalog's own contract ──────────────────────────────────────────────


def test_real_tests_dir_yields_a_catalog_covering_every_file() -> None:
    """Against the ACTUAL tree. Every file lands in exactly one cluster, and the
    totals agree with what was counted independently (169 files at the time of
    writing) — so a silent regression in the walk shows up here."""
    c = catalog_mod.build_catalog()
    if not c["available"]:
        pytest.skip("no test tree in this build")
    assert c["totals"]["files"] > 100
    assert c["totals"]["tests"] > 1000
    assert all(t["cluster"] for t in c["tests"]), "a cluster key must never be blank"
    # Each file appears once.
    paths = [t["path"] for t in c["tests"]]
    assert len(paths) == len(set(paths))
