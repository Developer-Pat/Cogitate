"""The DIFF and SAVE endpoints — what changed, and keeping a copy.

Three things here are worth more than the average route test:

- **The fingerprint is what makes "the same selection" a fact.** Two runs of
  different selections must NOT be compared, however recent the other one is: a
  diff against an unrelated run reports a hundred "removed" tests as if something
  had happened. The tests build runs whose fingerprints differ by one character.
- **Save COPIES.** The run stays in the runs dir — the page's history is unchanged
  — and the copy has to be a complete one (all three artifacts).
- **Save never overwrites, and never writes into the page's own state.** An
  existing copy at the destination is refused by name, and the runs dir and the
  trash are not destinations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Paths
from app.domain.testing.reports import list_reports
from app.domain.testing.run_lock import acquire, release


def a_run(
    runs_dir: Path,
    name: str,
    *,
    fingerprint: str = "aaaaaaaaaaaa",
    exit_code: int | None = 0,
    selection_count: int = 3,
    outcomes: dict[str, str] | None = None,
    mtime: float | None = None,
) -> Path:
    """A run folder with an envelope, and (optionally) per-test results.

    `outcomes` is the shape the JUnit reader produces: `{nodeid: outcome}` — so a
    test CAN describe a run precisely enough for a diff without inventing a new
    format.
    """
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)

    start: dict[str, object] = {
        "t": "run_start", "id": name, "kind": "pytest", "group": "unit",
        "files": selection_count, "parallel": True, "backend": "healthy",
        "selection_count": selection_count,
    }
    if fingerprint:
        start["selection_fingerprint"] = fingerprint
    lines = [json.dumps(start)]
    if outcomes is not None:
        for nodeid, outcome in outcomes.items():
            lines.append(json.dumps(
                {"t": "test", "nodeid": nodeid, "outcome": outcome}
            ))
    lines.append(json.dumps({"t": "summary", "counts": {}, "duration_s": 1.0}))
    if exit_code is not None:
        lines.append(json.dumps({"t": "run_end", "exit": exit_code, "elapsed_s": 2.0}))
    (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if outcomes is not None:
        cases = []
        for nodeid, outcome in outcomes.items():
            cls, _, test = nodeid.rpartition("::")
            if outcome == "passed":
                cases.append(f'<testcase classname="{cls}" name="{test}" time="0.1"/>')
            elif outcome == "skipped":
                cases.append(
                    f'<testcase classname="{cls}" name="{test}" time="0.1">'
                    f'<skipped message="not today"/></testcase>'
                )
            else:
                tag = "failure" if outcome == "failed" else "error"
                cases.append(
                    f'<testcase classname="{cls}" name="{test}" time="0.1">'
                    f'<{tag} message="boom">{outcome} here</{tag}></testcase>'
                )
        (run_dir / "report.xml").write_text(
            '<testsuites><testsuite name="pytest" tests="%d">%s</testsuite></testsuites>'
            % (len(cases), "".join(cases)),
            encoding="utf-8",
        )
    (run_dir / "report.md").write_text(f"# Test run — {name}\ngroup: unit\n", encoding="utf-8")

    if mtime is not None:
        # The baseline is chosen by mtime, so a test has to be able to say WHEN a
        # run was written rather than depending on the order two writes landed.
        import os
        os.utime(run_dir, (mtime, mtime))
    return run_dir


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "test-runs"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Paths, "test_runs_dir", target)
    monkeypatch.setattr(Paths, "root", tmp_path)
    return target


@pytest.fixture
def saving_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The locator's save destination, and a trash the refusal check can see."""
    destination = tmp_path / "test-reports"
    monkeypatch.setattr(Paths, "test_reports_dir", destination)
    monkeypatch.setattr(Paths, "trash_dir", tmp_path / "trash")
    return destination


# ── the diff ─────────────────────────────────────────────────────────────────


async def test_the_diff_compares_against_the_last_GREEN_run_of_the_SAME_selection(
    runs_dir: Path,
) -> None:
    """Three runs of one selection, and the middle one is the baseline."""
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", exit_code=0, mtime=1_000,
          outcomes={"tests/x.py::t_a": "passed", "tests/x.py::t_b": "passed"})
    a_run(runs_dir, "20260102-000000", exit_code=1, mtime=2_000,
          outcomes={"tests/x.py::t_a": "failed", "tests/x.py::t_b": "passed"})
    # The target is green on t_a again and has broken t_b — so the ONE thing that
    # changed is a regression, and the baseline has to be run 1, not run 2.
    a_run(runs_dir, "20260103-000000", exit_code=1, mtime=3_000,
          outcomes={"tests/x.py::t_a": "passed", "tests/x.py::t_b": "failed"})

    diff = await get_run_diff("20260103-000000")

    # NOT the most recent run (that one is the target) and NOT the red one.
    assert diff["baseline"] == "20260101-000000"
    assert diff["reason"] is None
    assert diff["newly_failing"] == ["tests/x.py::t_b"]
    assert diff["fixed"] == []
    assert diff["added"] == []
    assert diff["removed"] == []


async def test_the_diff_names_added_removed_newly_failing_and_fixed(runs_dir: Path) -> None:
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", exit_code=0, mtime=1_000, outcomes={
        "tests/x.py::t_keep": "passed",
        "tests/x.py::t_broke": "passed",
        "tests/x.py::t_gone": "passed",
        "tests/x.py::t_was_failing": "failed",
    })
    a_run(runs_dir, "20260102-000000", exit_code=1, mtime=2_000, outcomes={
        "tests/x.py::t_keep": "passed",
        "tests/x.py::t_broke": "failed",
        "tests/x.py::t_was_failing": "passed",
        "tests/x.py::t_new": "failed",
    })

    diff = await get_run_diff("20260102-000000")

    assert diff["baseline"] == "20260101-000000"
    assert diff["added"] == ["tests/x.py::t_new"]
    assert diff["removed"] == ["tests/x.py::t_gone"]
    # t_new FAILS but is new: it belongs to `added`, not to the regression list.
    assert diff["newly_failing"] == ["tests/x.py::t_broke"]
    assert diff["fixed"] == ["tests/x.py::t_was_failing"]


async def test_a_NEW_failing_test_is_ADDED_and_not_a_regression(runs_dir: Path) -> None:
    """One finding, stated once — the lists answer different questions."""
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", exit_code=0, mtime=1_000,
          outcomes={"tests/x.py::t_old": "passed"})
    a_run(runs_dir, "20260102-000000", exit_code=1, mtime=2_000,
          outcomes={"tests/x.py::t_old": "passed", "tests/x.py::t_brand_new": "failed"})

    diff = await get_run_diff("20260102-000000")

    assert diff["added"] == ["tests/x.py::t_brand_new"]
    assert diff["newly_failing"] == []
    assert diff["removed"] == [] and diff["fixed"] == []


async def test_a_test_that_DISAPPEARED_is_removed_and_not_fixed(runs_dir: Path) -> None:
    """A removed test that was failing is gone, not repaired."""
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", exit_code=0, mtime=1_000,
          outcomes={"tests/x.py::t_kept": "passed", "tests/x.py::t_dropped": "failed"})
    a_run(runs_dir, "20260102-000000", exit_code=1, mtime=2_000,
          outcomes={"tests/x.py::t_kept": "failed"})

    diff = await get_run_diff("20260102-000000")

    assert diff["removed"] == ["tests/x.py::t_dropped"]
    assert diff["fixed"] == []
    assert diff["newly_failing"] == ["tests/x.py::t_kept"]


async def test_a_DIFFERENT_selection_is_NOT_a_baseline(runs_dir: Path) -> None:
    """However recent it is: comparing across selections would invent change."""
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", fingerprint="bbbbbbbbbbbb", exit_code=0,
          mtime=1_000, outcomes={"tests/y.py::t_a": "passed"})
    a_run(runs_dir, "20260102-000000", fingerprint="aaaaaaaaaaaa", exit_code=1,
          mtime=2_000, outcomes={"tests/x.py::t_a": "failed"})

    diff = await get_run_diff("20260102-000000")

    assert diff["baseline"] is None
    assert "no green run of the same selection" in diff["reason"]
    assert diff["added"] == [] and diff["removed"] == []
    assert diff["newly_failing"] == []


async def test_a_run_with_NO_fingerprint_says_why_it_cannot_be_compared(
    runs_dir: Path,
) -> None:
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", fingerprint="", exit_code=1,
          outcomes={"tests/x.py::t_a": "failed"})

    diff = await get_run_diff("20260101-000000")
    assert diff["baseline"] is None
    assert "recorded no selection fingerprint" in diff["reason"]


async def test_a_run_with_NO_per_test_results_says_so(runs_dir: Path) -> None:
    """A killed run has no XML: the baseline is named, and the reason too."""
    from app.api.v1.testing.router import get_run_diff

    a_run(runs_dir, "20260101-000000", exit_code=0, mtime=1_000,
          outcomes={"tests/x.py::t_a": "passed"})
    a_run(runs_dir, "20260102-000000", exit_code=None, mtime=2_000, outcomes=None)

    diff = await get_run_diff("20260102-000000")
    assert diff["baseline"] == "20260101-000000"
    assert "no per-test results" in diff["reason"]


async def test_a_diff_for_an_unknown_run_is_a_404(runs_dir: Path) -> None:
    from fastapi import HTTPException

    from app.api.v1.testing.router import get_run_diff

    with pytest.raises(HTTPException) as caught:
        await get_run_diff("19990101-000000")
    assert caught.value.status_code == 404


# ── save ─────────────────────────────────────────────────────────────────────


async def test_SAVE_copies_the_run_and_leaves_it_in_place(
    runs_dir: Path, saving_dirs: Path, tmp_path: Path,
) -> None:
    """A COPY: the page's history is untouched and the copy is complete."""
    from app.api.v1.testing.router import save_a_run

    original = a_run(runs_dir, "20260101-000000", outcomes={"tests/x.py::t_a": "passed"})
    before = sorted(p.name for p in original.iterdir())

    answer = await save_a_run("20260101-000000", None)

    assert answer["saved"] is True
    assert answer["saved_to"] == "test-reports/20260101-000000"
    assert sorted(answer["files"]) == before
    copied = saving_dirs / "20260101-000000"
    assert sorted(p.name for p in copied.iterdir()) == before
    assert original.is_dir()                                  # still the page's
    assert [r["name"] for r in list_reports()] == ["20260101-000000"]


async def test_save_goes_to_the_LOCATOR_default_and_a_relative_path_to_the_root(
    runs_dir: Path, saving_dirs: Path, tmp_path: Path,
) -> None:
    from app.api.v1.testing.router import SaveRequest, save_a_run

    a_run(runs_dir, "20260101-000000", outcomes={"tests/x.py::t_a": "passed"})

    default = await save_a_run("20260101-000000", None)
    assert default["saved_to"] == "test-reports/20260101-000000"

    a_run(runs_dir, "20260102-000000", outcomes={"tests/x.py::t_a": "passed"})
    relative = await save_a_run("20260102-000000", SaveRequest(destination="kept/runs"))
    # Relative means relative to the PROJECT, not to the server's own cwd.
    assert relative["saved_to"] == "kept/runs/20260102-000000"
    assert (tmp_path / "kept" / "runs" / "20260102-000000").is_dir()


async def test_save_NEVER_overwrites_an_existing_copy(
    runs_dir: Path, saving_dirs: Path,
) -> None:
    """A save that silently replaced an earlier one would not be a save."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import save_a_run

    a_run(runs_dir, "20260101-000000", outcomes={"tests/x.py::t_a": "passed"})
    await save_a_run("20260101-000000", None)
    (saving_dirs / "20260101-000000" / "NOTE.txt").write_text("mine", encoding="utf-8")

    with pytest.raises(HTTPException) as caught:
        await save_a_run("20260101-000000", None)
    assert caught.value.status_code == 409
    assert "already saved" in str(caught.value.detail)
    # The earlier copy is untouched — including the file somebody added to it.
    assert (saving_dirs / "20260101-000000" / "NOTE.txt").read_text() == "mine"


async def test_saving_the_RUNNING_run_is_refused_with_the_locks_sentence(
    runs_dir: Path, saving_dirs: Path,
) -> None:
    """A copy of artifacts that are being written is a torn copy."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import save_a_run

    a_run(runs_dir, "20260101-000000", exit_code=None, outcomes=None)
    acquire(runs_dir, "20260101-000000", origin="page")
    try:
        with pytest.raises(HTTPException) as caught:
            await save_a_run("20260101-000000", None)
        assert caught.value.status_code == 409
        assert "20260101-000000" in str(caught.value.detail)
    finally:
        release(runs_dir, "20260101-000000")


async def test_a_destination_inside_the_pages_OWN_state_is_refused(
    runs_dir: Path, saving_dirs: Path, tmp_path: Path,
) -> None:
    """The runs dir and the trash are state, not a filing cabinet."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import SaveRequest, save_a_run

    a_run(runs_dir, "20260101-000000", outcomes={"tests/x.py::t_a": "passed"})
    for bad in (str(runs_dir), str(tmp_path / "trash")):
        with pytest.raises(HTTPException) as caught:
            await save_a_run("20260101-000000", SaveRequest(destination=bad))
        assert caught.value.status_code == 400
        assert "cannot save into" in str(caught.value.detail)


async def test_saving_an_unknown_run_is_a_404(runs_dir: Path, saving_dirs: Path) -> None:
    from fastapi import HTTPException

    from app.api.v1.testing.router import save_a_run

    with pytest.raises(HTTPException) as caught:
        await save_a_run("19990101-000000", None)
    assert caught.value.status_code == 404
