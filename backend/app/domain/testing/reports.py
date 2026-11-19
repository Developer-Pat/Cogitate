"""
The test RUN reader — what `scripts/testing/run_tests.py` leaves behind.

THE USER-TESTING PAGE. The page shows runs; this is how they are read.

**The page does not own the runs.** The runner writes them into the locator's
`data/test-runs/`; this module READS that directory. No repository, no rolling,
no retention — that is the user-space boundary (design §1).

ONE RUN, ONE FOLDER, THREE ARTIFACTS, and each is read for what it is good at:

    events.jsonl   the envelope: who ran what, when, and how it ended. Written
                   as the run happens, so it is also the only source that can
                   describe a run that is STILL RUNNING.
    report.xml     pytest's JUnit XML: the per-test outcomes and the skip
                   messages. A schema a tool emits on purpose, instead of
                   prose reverse-engineered with regular expressions.
    report.md      the developer's hard copy, and the FALLBACK: a run killed
                   before pytest finished has no XML, but the markdown still
                   holds what happened up to the kill.

**Read defensively at every layer.** A run is a directory of files that may be
half-written, and a truncated run must read as truncated — never as missing.
A run whose artifacts cannot be parsed is still returned, with `parsed: False`
and a note, because a run that exists but reads as absent is worse than one that
reads as odd.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Paths
from app.domain.testing.run_lock import read_lock

#: `74 passed, 1 warning, 2 errors in 19.47s` — pytest's summary line, used only
#: by the markdown fallback.
#: Counts are matched INDIVIDUALLY, because their order and membership vary
#: (skipped/xfailed may be absent; warnings may not be). A positional parse
#: would silently mis-read the moment pytest omits one.
#: pytest appends a human duration to LONG runs — `in 136.29s (0:02:16)` — and
#: not to short ones. A pattern that required the line to END after `in Xs`
#: silently read every long run as having no counts at all (three historical
#: reports came back empty until this was caught).
_SUMMARY_RE = re.compile(
    r"^(?P<counts>(?:\d+ [a-z]+(?:, )?)+?)"
    r"(?: in (?P<seconds>[\d.]+)s)?"
    r"(?:\s*\([\d:]+\))?"
    r"\s*$"
)
_COUNT_RE = re.compile(r"(\d+) ([a-z]+)")

#: `group: api  parallel: True  files: 14`
_HEADER_RE = re.compile(
    r"^group:\s*(?P<group>\S+)\s+parallel:\s*(?P<parallel>\S+)\s+files:\s*(?P<files>\d+)"
)
_BACKEND_RE = re.compile(r"^backend:\s*(?P<backend>.+?)\s*$")
_TITLE_RE = re.compile(r"^# Test run — (?P<ts>\S+)")
_ELAPSED_RE = re.compile(r"^ELAPSED:\s*(?P<elapsed>\S+)\s+EXIT:\s*(?P<exit>\d+)")

#: `SKIPPED [1] tests/x.py:12: the reason`  /  `FAILED tests/x.py::test_y - AssertionError`
_SKIP_RE = re.compile(r"^SKIPPED\s*\[\d+\]\s*(?P<where>[^:]+):(?P<reason>.*)$")
_FAILED_RE = re.compile(r"^(?P<kind>FAILED|ERROR)\s+(?P<where>\S+)(?:\s+-\s+(?P<why>.*))?$")

#: How much of a run's event stream the LIST view reads: the envelope is at the
#: two ends, and a full run's stream is a line per test (megabytes by the end).
_HEAD_BYTES = 4096
_TAIL_BYTES = 8192


@dataclass
class RunFacts:
    """One run, as far as its artifacts can be read."""

    name: str
    timestamp: str = ""
    group: str = ""
    parallel: bool = False
    files: int = 0
    backend: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    duration_s: float | None = None
    elapsed: str = ""
    exit_code: int | None = None
    running: bool = False
    failures: list[dict[str, str]] = field(default_factory=list)
    skips: list[dict[str, str]] = field(default_factory=list)
    parsed: bool = False
    note: str | None = None
    #: True when this run's own selection was the page's exercise and nothing
    #: else. It is a deliberately red run, and the history has to say so or a
    #: person scanning runs reads a fixture's failure as the suite's.
    self_test: bool = False
    #: WHAT THIS RUN SELECTED, provably: how many files, and a short hash of the
    #: sorted list. Empty/0 for a run that recorded neither (older than the field),
    #: which is what makes "the same selection" answerable rather than assumed.
    selection_count: int = 0
    selection_fingerprint: str = ""


def _runs_dir() -> Path:
    """The runs dir, resolved per call so a relocated root is honoured."""
    return Path(Paths.test_runs_dir)


def resolve_run_dir(directory: Path, name: str) -> Path | None:
    """`directory/name`, CONTAINED — or None when it is not there.

    ONE containment check for every module that turns a NAME into a directory, and
    the name arrives from a URL. `../` must not walk out, and the check runs on the
    RESOLVED path so a symlink cannot do it either. The run reader, the trash and
    Save all need this rule; three copies of it would be three chances to get it
    wrong, and the copy that drifts is the one nobody re-tests.
    """
    candidate = (directory / name).resolve()
    if candidate.parent != directory.resolve() or not candidate.is_dir():
        return None
    return candidate


#: The page's own exercise lives here, and a run's selection records it
#: backend-relative — `selftest/test_page_exercise.py`.
_SELFTEST_PREFIX = "selftest/"


def _is_self_test(start: dict[str, Any]) -> bool:
    """True when a run's OWN SELECTION was the page's exercise, and nothing else.

    Read from the selection the runner recorded rather than guessed from a name:
    a run of the fixture is identified by what it RAN. A mixture is not one — a
    run of the fixture plus part of the suite is a different thing, and labelling
    it a self-test would be the kind of convenient name this page exists to avoid.

    A run with no recorded selection (older than the field, or truncated) answers
    False: not knowing is a reason to say nothing, not to guess.
    """
    selection = start.get("selection")
    if not isinstance(selection, list) or not selection:
        return False
    return all(
        isinstance(entry, str) and entry.startswith(_SELFTEST_PREFIX)
        for entry in selection
    )


def _tail_lines(path: Path, n: int) -> list[str]:
    """The last `n` lines, without reading the whole file."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - _TAIL_BYTES))
            chunk = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    if size > _TAIL_BYTES and lines:
        lines = lines[1:]  # the first line of a tail read is usually partial
    return lines[-n:]


def _read_events(path: Path) -> dict[str, Any]:
    """The run's envelope: `run_start`, `summary`, `run_end`.

    Only the two ends of the file are read. The middle is one line per test —
    the point of it is that a TAILER reads it live; nothing that lists runs
    needs megabytes of it in memory.
    """
    out: dict[str, Any] = {}
    try:
        with open(path, "rb") as f:
            head = f.read(_HEAD_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return out
    for line in head.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("t") == "run_start":
            out["start"] = event
            break
    for line in reversed(_tail_lines(path, 8)):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("t")
        if kind == "run_end" and "end" not in out:
            out["end"] = event
        elif kind == "summary" and "summary" not in out:
            out["summary"] = event
    return out


def parse_report(path: Path) -> RunFacts:
    """The FALLBACK parser: the developer's hard copy, read as prose.

    Used only when a run has no events and no XML (a run made before the
    structured artifacts existed, or one killed so early that neither was
    written). Everything here is best-effort by nature — the primary sources
    are structured, and a markdown read is a guess at prose.

    It sets its own verdict (`parsed`) and its own note, because "nothing was
    recognisable" is a fact about THIS file: a sweep report has no
    `# Test run —` header, and it must come back `parsed: False` WITH a note
    rather than as an empty-but-normal-looking run.
    """
    r = RunFacts(name="")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        r.note = f"could not be read: {exc}"
        return r

    for line in text.splitlines():
        if not r.timestamp:
            m = _TITLE_RE.match(line)
            if m:
                r.timestamp = m.group("ts")
                continue
        if not r.group:
            m = _HEADER_RE.match(line)
            if m:
                r.group = m.group("group")
                r.parallel = m.group("parallel").lower() in ("true", "1", "yes")
                r.files = int(m.group("files"))
                continue
        if not r.backend:
            m = _BACKEND_RE.match(line)
            if m:
                r.backend = m.group("backend")
                continue
        m = _ELAPSED_RE.match(line)
        if m:
            r.elapsed, r.exit_code = m.group("elapsed"), int(m.group("exit"))
            continue
        m = _SKIP_RE.match(line)
        if m:
            r.skips.append({"where": m.group("where").strip(),
                            "reason": m.group("reason").strip()})
            continue
        m = _FAILED_RE.match(line)
        if m:
            r.failures.append({"kind": m.group("kind"),
                               "where": m.group("where"),
                               "why": (m.group("why") or "").strip()})
            continue
        # The summary line is the LAST line that matches; keep overwriting so a
        # mid-run echo cannot win over the real one.
        counts, secs = _parse_summary(line)
        if counts:
            r.counts, r.duration_s = counts, secs

    r.parsed = bool(r.counts or r.exit_code is not None)
    if not r.parsed:
        # Honest, not empty: the file exists, its content was not recognisable.
        # A truncated or in-flight run lands here, and saying so beats a blank.
        r.note = "no pytest summary found — truncated, in flight, or crashed early"
    return r


def _parse_summary(line: str) -> tuple[dict[str, int], float | None]:
    """Pull the counts and the duration out of pytest's summary line."""
    m = _SUMMARY_RE.match(line.strip())
    if not m:
        return {}, None
    counts = {word: int(n) for n, word in _COUNT_RE.findall(m.group("counts"))}
    secs = float(m.group("seconds")) if m.group("seconds") else None
    return counts, secs


def _local(tag: str) -> str:
    """A tag's name without its namespace.

    ElementTree's `{*}tag` wildcard does NOT match tags that carry no namespace
    — `iter("{*}testcase")` returns nothing against pytest's own XML. That
    failure is silent (all-zero counts, no error), so namespaces are stripped
    here instead: pytest emits none today, and a parser that assumed that would
    quietly report a green run the day one appeared.
    """
    return tag.rsplit("}", 1)[-1]


def _read_junit(path: Path) -> dict[str, Any]:
    """The per-test outcomes, from pytest's own JUnit XML.

    Returns counts, the failures (with their messages) and the skips (with their
    REASONS — the whole point: a skipped test is evidence, and evidence that does
    not say why is not actionable). An unreadable, absent or unrecognised XML
    returns EMPTY, never zeros: a caller must be able to tell "nothing to read"
    from "a run in which nothing happened".
    """
    out: dict[str, Any] = {}
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return out
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failures: list[dict[str, str]] = []
    skips: list[dict[str, str]] = []
    #: Every test's outcome, by the same `where` the FAILED list uses. The diff
    #: needs the WHOLE set (a test that passed in one run and is missing from the
    #: next is the interesting part), and this parse is already walking every
    #: testcase, so the map costs nothing extra to build.
    outcomes: dict[str, str] = {}
    total_time = 0.0
    seen_suite = seen_case = False
    for elem in root.iter():
        name = _local(elem.tag)
        if name == "testsuite":
            seen_suite = True
            try:
                total_time += float(elem.attrib.get("time") or 0.0)
            except ValueError:
                pass
        elif name == "testcase":
            seen_case = True
            where = (elem.attrib.get("classname", "") + "::"
                     + elem.attrib.get("name", "")).lstrip(":")
            node = {_local(c.tag): c for c in elem}
            if "skipped" in node:
                counts["skipped"] += 1
                outcomes[where] = "skipped"
                skips.append({"where": where,
                              "reason": (node["skipped"].attrib.get("message")
                                         or (node["skipped"].text or "")).strip()[:300]})
            elif "failure" in node or "error" in node:
                key = "failed" if "failure" in node else "errors"
                counts[key] += 1
                outcomes[where] = "failed" if "failure" in node else "error"
                hit = node["failure" if "failure" in node else "error"]
                failures.append({
                    "kind": "FAILED" if "failure" in node else "ERROR",
                    "where": where,
                    "why": (hit.attrib.get("message") or (hit.text or "")).strip()[:300],
                })
            else:
                counts["passed"] += 1
                outcomes[where] = "passed"
    if not (seen_case or seen_suite):
        return {}
    out["counts"] = counts
    out["failures"] = failures
    out["skips"] = skips
    out["outcomes"] = outcomes
    out["duration_s"] = round(total_time, 2) if total_time else None
    return out


def _read_run(run_dir: Path, with_detail: bool) -> RunFacts:
    """One run folder, read from its artifacts — envelope, XML, then markdown."""
    r = RunFacts(name=run_dir.name, timestamp=run_dir.name)

    events = _read_events(run_dir / "events.jsonl")
    start = events.get("start") or {}
    if start:
        r.group = str(start.get("group") or "")
        r.parallel = bool(start.get("parallel"))
        r.files = int(start.get("files") or 0)
        r.backend = str(start.get("backend") or "")
        r.self_test = _is_self_test(start)
        r.selection_count = int(start.get("selection_count") or 0)
        r.selection_fingerprint = str(start.get("selection_fingerprint") or "")
    end = events.get("end") or {}
    if end:
        r.exit_code = end.get("exit") if isinstance(end.get("exit"), int) else None
        elapsed = end.get("elapsed_s")
        r.elapsed = f"{elapsed}s" if elapsed is not None else ""
        r.running = False
    elif start:
        # A `run_start` with no `run_end`: the run is going, OR it died without a
        # word. The LOCK tells the two apart — it is the runner's own record of
        # who is running — so a killed run is never described as still running.
        live_lock = read_lock(run_dir.parent)
        still_going = (live_lock is not None and live_lock.id == run_dir.name
                       and live_lock.alive())
        r.running = still_going
        r.note = ("still running — no end event yet" if still_going
                  else "stopped without an end event (the run was killed)")
    summary = events.get("summary") or {}
    if summary.get("counts"):
        r.counts = {k: int(v) for k, v in summary["counts"].items() if v}
    if summary.get("duration_s"):
        r.duration_s = float(summary["duration_s"])

    # THE LIST VIEW IS CHEAP ON PURPOSE. The event envelope already carries the
    # counts, so listing runs does not parse a JUnit file per run (a full run's
    # XML is megabytes). The XML is read for the DETAIL view, or when the
    # envelope had nothing to say.
    xml = _read_junit(run_dir / "report.xml") if (with_detail or not r.counts) else {}
    if xml:
        # The XML is the per-test truth: it can name every test, which a count
        # never can. Its counts also survive a run whose plugin never ran.
        if not r.counts:
            r.counts = {k: v for k, v in xml["counts"].items() if v}
        if r.duration_s is None:
            r.duration_s = xml.get("duration_s")
        if with_detail:
            r.failures, r.skips = xml["failures"], xml["skips"]

    md = run_dir / "report.md"
    if md.is_file():
        prose = parse_report(md)
        # Fill only what the structured sources did not answer.
        r.group = r.group or prose.group
        r.files = r.files or prose.files
        r.backend = r.backend or prose.backend
        r.parallel = r.parallel or prose.parallel
        if r.exit_code is None:
            r.exit_code = prose.exit_code
        if not r.elapsed:
            r.elapsed = prose.elapsed
        if not r.counts:
            r.counts = prose.counts
            r.duration_s = r.duration_s or prose.duration_s
        if with_detail and not r.failures and not r.skips:
            # No XML (killed before pytest wrote it): the markdown's FAILED and
            # SKIPPED lines are the only record, and they are still records.
            r.failures, r.skips = prose.failures, prose.skips

    r.parsed = bool(r.counts or r.exit_code is not None)
    if not r.parsed and not r.note:
        r.note = "no results found — truncated, in flight, or crashed early"
    return r


def _as_dict(r: RunFacts, mtime: float, detail: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": r.name,
        "timestamp": r.timestamp,
        "group": r.group,
        "parallel": r.parallel,
        "files": r.files,
        "backend": r.backend,
        "counts": r.counts,
        "duration_s": r.duration_s,
        "elapsed": r.elapsed,
        "exit_code": r.exit_code,
        "running": r.running,
        "parsed": r.parsed,
        # The history has to distinguish a deliberately red run from a real
        # failure — see `_is_self_test`.
        "self_test": r.self_test,
        # What the run SELECTED. The diff reads this; the page shows the count.
        "selection_count": r.selection_count,
        "selection_fingerprint": r.selection_fingerprint,
        "mtime": mtime,
    }
    if detail:
        out["failures"] = r.failures
        out["skips"] = r.skips
        out["note"] = r.note
    else:
        # Counts, not lists: the list view says how many, and the detail view is
        # where a failure's message and a skip's reason are read.
        out["failures"] = (r.counts.get("failed", 0) + r.counts.get("errors", 0)
                           if r.counts else len(r.failures))
        out["skips"] = r.counts.get("skipped", 0) if r.counts else len(r.skips)
    return out


def list_reports(limit: int = 50) -> list[dict[str, Any]]:
    """The runs on disk, newest first.

    Ordered by the directory's mtime rather than its name: the name carries the
    runner's timestamp, but a run copied or restored would sort wrongly by name
    while its mtime still tells the truth about when it was written.
    """
    runs_dir = _runs_dir()
    if not runs_dir.is_dir():
        return []
    dirs = [d for d in runs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for d in dirs:
        if len(out) >= limit:
            break
        out.append(_as_dict(_read_run(d, with_detail=False), d.stat().st_mtime, False))
    return out


def read_report(name: str) -> dict[str, Any] | None:
    """One run in full, including its failure and skip detail.

    Returns None if the name is not a run in the runs dir. The name is resolved
    and CONTAINED — a caller cannot walk out of the runs dir with `../`, which
    matters because this name arrives from a URL.
    """
    candidate = resolve_run_dir(_runs_dir(), name)
    if candidate is None:
        return None
    return _as_dict(_read_run(candidate, with_detail=True),
                    candidate.stat().st_mtime, True)


def run_outcomes(name: str) -> dict[str, str] | None:
    """EVERY test's outcome for one run, or None when it has no per-test record.

    The DIFF's reader. The run DETAIL wants the failures and the skips; the diff
    wants the whole set, because "this test is gone" is as interesting as "this
    test broke" — and a set is what set arithmetic needs.

    None means NO JUnit XML: a run killed before pytest wrote it, or one that
    never got that far. That is not "a run in which nothing happened", and the
    caller has to be able to tell the two apart. The name is contained, exactly
    as `read_report` contains it.
    """
    candidate = resolve_run_dir(_runs_dir(), name)
    if candidate is None:
        return None
    xml = _read_junit(candidate / "report.xml")
    if not xml:
        return None
    # Typed here rather than returned straight off the mapping: `_read_junit` answers
    # with a loose shape, and the caller deserves the one it asked for.
    outcomes: dict[str, str] = xml["outcomes"]
    return outcomes
