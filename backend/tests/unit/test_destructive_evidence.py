"""The destructive-evidence journal line tests.

THE GAP THIS CLOSES: the access journal is deliberately minimal — it
proves a request HAPPENED and says nothing about what it destroyed. That
cost real time: a bulk delete of eight sessions left only

    POST /api/v1/sessions/bulk-delete 200

so the journal answered "did it happen" and not "what went", and the
answer had to be recovered from app.log by hand. Destructive endpoints
now write their own line, naming the ids.

Two things these tests pin: the line reaches the journal with the ids in
it, and evidence can never FAIL a delete that otherwise succeeded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import access_evidence


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Point the journal at a temp file for the duration of a test."""
    path = tmp_path / "access.log"
    monkeypatch.setattr(access_evidence, "_ACCESS_FILE", path)
    return path


def test_records_the_ids_that_were_destroyed(journal):
    access_evidence.record_destructive_evidence(
        "/api/v1/sessions/bulk-delete",
        f"deleted=3 ids={access_evidence.format_ids([27, 26, 25])}",
    )

    line = journal.read_text().strip()
    assert access_evidence.DESTRUCTIVE_MARKER in line
    assert "/api/v1/sessions/bulk-delete" in line
    assert "deleted=3" in line
    for sid in ("27", "26", "25"):
        assert sid in line


def test_line_is_appended_not_truncated(journal):
    journal.write_text("an earlier request line\n")
    access_evidence.record_destructive_evidence("/x", "deleted=1 ids=[1]")

    lines = journal.read_text().splitlines()
    assert len(lines) == 2
    assert lines[0] == "an earlier request line"


def test_format_ids_lists_them_all_when_short():
    assert access_evidence.format_ids([3, 1, 2]) == "[3, 1, 2]"
    assert access_evidence.format_ids([]) == "[]"


def test_format_ids_truncation_is_EXPLICIT():
    """A clear-all can name thousands — the cap must SAY it capped.

    A silently truncated evidence line is worse than no line: it looks
    complete and would let a wrong count be believed.
    """
    ids = list(range(1, 201))
    rendered = access_evidence.format_ids(ids)

    assert rendered.startswith("[1, 2, 3")
    assert "+150 more]" in rendered, "the omitted count must be stated"
    assert len(rendered) < 600


def test_evidence_failure_never_raises(tmp_path, monkeypatch):
    """The journal must not be able to fail a delete that succeeded."""
    # make the write blow up: point at a path whose parent is a FILE
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setattr(
        access_evidence, "_ACCESS_FILE", blocker / "child" / "access.log"
    )

    # must not raise
    access_evidence.record_destructive_evidence("/x", "deleted=1")


def test_the_four_session_wipes_are_wired():
    """Guard the call sites: a new destructive endpoint must add one.

    Not a behaviour test — a tripwire. If someone adds a session-wiping
    route without the evidence call, this fails and says why.
    """
    import inspect

    from app.api.v1.sessions import router as sessions_router

    src = inspect.getsource(sessions_router)
    # every destructive session route
    for route in (
        # the `:int` converter is what makes this route REACHABLE: declared as a
        # plain `{session_id}` it sits after `/{session_id}` and the literal
        # paths (`/all`) 422 through it instead of matching.
        'delete("/{session_id:int}"',
        'post("/bulk-delete"',
        'delete(""',
        'delete("/all"',
    ):
        assert route in src, f"route {route} moved — update this test"

    assert src.count("record_destructive_evidence(") >= 4, (
        "a destructive route is missing its evidence call"
    )
