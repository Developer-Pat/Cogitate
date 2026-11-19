"""
The DIFF — what CHANGED since the last comparable run.

THE QUESTION THIS ANSWERS. *"Why did this fail?"* is much easier with what changed
than with the failure alone (the design's §8). The comparison is against the last
**green** run that ran the **same selection** — and "the same selection" is a FACT
here rather than a guess: the runner records a count and a fingerprint of its
sorted selection (`scripts/testing/run_tests.py`, `_fingerprint`), so a run whose
selection changed cannot be mistaken for a baseline.

WHAT IT REFUSES TO DO: it never falls back to "whatever ran last". A diff against
an unrelated selection would be worse than no diff — it would report a hundred
"removed" tests as if something had happened. When there is no comparable green
run, the answer SAYS SO, with the reason, and the lists stay empty.

WHAT "ADDED" AND "REMOVED" MEAN, given the selection is identical: a test that
appeared or disappeared INSIDE those same files — a new test, a rename, or a
parametrization that changed. It is not "the suite grew": a different selection
would not have matched in the first place.

AND THE TWO LISTS DO NOT OVERLAP. `newly_failing` is a REGRESSION — a test both
runs ran, failing now and not before. A test that is new and failing appears in
`added` and is deliberately NOT repeated in `newly_failing`: those answer different
questions ("what appeared" vs "what broke"), and reporting one thing twice reads as
two findings. For the same reason a test that disappeared is `removed` and never
`fixed`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.testing import reports

#: How far back to look for a baseline. BOUNDED: the interesting baseline is the
#: recent green run of the same selection, and scanning a thousand folders to find
#: one is a cost nobody asked for.
LOOKBACK = 200

#: pytest's vocabulary for "this test did not pass", in the shape the XML reader
#: uses (`failed` for a failure, `error` for a setup/teardown error).
FAILING = {"failed", "error"}


@dataclass
class RunDiff:
    """What changed between a run and its baseline."""

    run: str
    #: The run's own selection fingerprint — empty for a run that recorded none.
    fingerprint: str = ""
    baseline: str | None = None
    #: Why there is no comparison, when there is none. Null once there is one.
    reason: str | None = None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    newly_failing: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    #: The baseline's counts, so the page can say what it was comparing against
    #: without a second request.
    baseline_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run": self.run,
            "fingerprint": self.fingerprint,
            "baseline": self.baseline,
            "reason": self.reason,
            "added": self.added,
            "removed": self.removed,
            "newly_failing": self.newly_failing,
            "fixed": self.fixed,
            "baseline_counts": self.baseline_counts,
        }


def diff_against_last_green(name: str) -> RunDiff | None:
    """The diff for one run. None when there is no such run — the caller 404s.

    Every other way of having no comparison comes back as a `reason`, because
    "there is nothing to compare against" is a fact the page must be able to state
    rather than render as an empty diff that looks like "nothing changed".
    """
    runs = reports.list_reports(limit=LOOKBACK)
    target = next((r for r in runs if r["name"] == name), None)
    if target is None:
        return None

    fingerprint = str(target.get("selection_fingerprint") or "")
    diff = RunDiff(run=name, fingerprint=fingerprint)

    if not fingerprint:
        diff.reason = (
            "this run recorded no selection fingerprint, so it cannot be matched "
            "to a comparable run"
        )
        return diff

    baseline = next(
        (
            r
            for r in runs
            if r["name"] != name
            and r.get("selection_fingerprint") == fingerprint
            # GREEN means exit 0 — pytest's own answer. A run that exited 0 with
            # failures is not possible; skips are not failures.
            and r.get("exit_code") == 0
            and r.get("mtime", 0) < target.get("mtime", 0)
        ),
        None,
    )
    if baseline is None:
        diff.reason = (
            "no green run of the same selection is on disk — this is the first run "
            "of it, or every earlier one failed"
        )
        return diff

    diff.baseline = baseline["name"]
    diff.baseline_counts = dict(baseline.get("counts") or {})

    before = reports.run_outcomes(baseline["name"])
    after = reports.run_outcomes(name)
    if before is None:
        diff.reason = "the baseline has no per-test results to compare against"
        return diff
    if after is None:
        diff.reason = "this run has no per-test results (it stopped before pytest wrote them)"
        return diff

    before_failing = {test for test, outcome in before.items() if outcome in FAILING}
    after_failing = {test for test, outcome in after.items() if outcome in FAILING}
    both = set(before) & set(after)

    diff.added = sorted(set(after) - set(before))
    diff.removed = sorted(set(before) - set(after))
    # REGRESSIONS ONLY: a test both runs ran, failing now and not before. A test
    # that is NEW and failing is reported in `added` — the lists answer different
    # questions ("what appeared" vs "what broke"), and double-reporting it would
    # read as two findings where there is one. For the same reason a test that
    # DISAPPEARED is `removed` and never `fixed`.
    diff.newly_failing = sorted((after_failing & both) - before_failing)
    diff.fixed = sorted((before_failing & both) - after_failing)
    return diff
