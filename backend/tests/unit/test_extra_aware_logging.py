"""
The ExtraAwareFormatter — the `extra=` context must reach the log.

THE FAILURE THIS PINS. A real, reproducible failure — "the user
cannot talk to Bob" — could NOT be diagnosed from `app.log`, because the one
record that knew the cause had been written without it:

    ❌ LLM STREAM FAILED TO OPEN

`log_stream_open_failure` attaches `error`, `error_type` and `traceback` through
`extra=`, and the format string rendered only `%(message)s`, so the context was
attached and then discarded. The line above is all a reader got.

Two things are tested, and the second matters as much as the first:
  1. an `extra=` field APPEARS in the formatted line;
  2. a record with NO extras is rendered EXACTLY as before — the fix must not
     decorate the ~99% of lines that carry nothing, or the log becomes noise and
     the fix gets reverted.
"""

from __future__ import annotations

import logging

from app.core.logging_config import ExtraAwareFormatter


def _fmt(record: logging.LogRecord) -> str:
    f = ExtraAwareFormatter(fmt="%(levelname)s | %(name)s | %(message)s")
    return f.format(record)


def _record(**extra: object) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="app.test", level=logging.ERROR, pathname=__file__,
        lineno=1, msg="boom", args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


# ── it FIRES ────────────────────────────────────────────────────────────────


def test_an_error_field_reaches_the_line() -> None:
    """The whole point: the cause is in the line, not just attached to it."""
    out = _fmt(_record(error="Connection refused", error_type="ConnectError"))
    assert "error=Connection refused" in out
    assert "error_type=ConnectError" in out


def test_the_stream_open_failure_shape_is_legible() -> None:
    """The exact record that used to be a dead end, reproduced."""
    out = _fmt(_record(
        session_id=54,
        provider="llama",
        # A GENERIC placeholder, never a real home directory — the
        # no-absolute-paths rule caught this file once already, and the double
        # slash is the property under test, not the path itself.
        model="openai//srv/models/a-local-model.gguf",
        error="Timeout opening stream",
        error_type="TimeoutError",
    ))
    assert "session_id=54" in out
    assert "provider=llama" in out
    assert "error=Timeout opening stream" in out
    # and the message itself is still there, first
    assert out.startswith("ERROR | app.test | boom")


def test_a_multiline_traceback_keeps_its_own_lines() -> None:
    """A traceback must not be flattened into one enormous line — the log has
    to stay scannable, or nobody reads it."""
    tb = "Traceback (most recent call last):\n  File 'x.py', line 1\nTimeoutError: nope"
    out = _fmt(_record(traceback=tb))
    lines = out.splitlines()
    assert lines[0] == "ERROR | app.test | boom"
    assert any("Traceback (most recent call last):" in l for l in lines)
    assert any("TimeoutError: nope" in l for l in lines)
    assert all(l.startswith("    ") for l in lines[1:])


# ── it STAYS QUIET ──────────────────────────────────────────────────────────


def test_a_record_with_no_extras_is_unchanged() -> None:
    """THE STAYS-QUIET CASE. A formatter that decorates every line turns a
    readable log into noise, and the fix gets reverted."""
    out = _fmt(_record())
    assert out == "ERROR | app.test | boom"
    # The format itself carries TWO separators; an extra would add a THIRD.
    # (The first version of this asserted `"|" not in out` — nonsense, since the
    # format's own separators are always there. The test was wrong, not the code.)
    assert out.count("|") == 2, "no separator was added for a record with no extras"


def test_a_standard_attribute_is_not_mistaken_for_an_extra() -> None:
    """`module`, `lineno`, `funcName` etc. are on EVERY record — reproducing
    them on every line would be absurd, and it is the obvious failure mode of
    an implementation that forgets which fields are standard."""
    out = _fmt(_record())
    for standard in ("lineno", "module", "funcName", "args", "levelname"):
        assert standard not in out, f"{standard} was rendered as an extra"


def test_it_never_raises_on_an_unprintable_value() -> None:
    """A formatter that throws turns a logged failure into a logging failure,
    which is strictly worse than the missing detail it was fixing."""
    class Hostile:
        def __str__(self) -> str:
            raise RuntimeError("I hate being printed")

    out = _fmt(_record(error=Hostile()))
    assert "<unprintable>" in out
    assert out.startswith("ERROR | app.test | boom")


def test_a_private_key_is_not_rendered() -> None:
    """`_`-prefixed attributes are logging's internals."""
    out = _fmt(_record(_secret_internal="should not appear"))
    assert "should not appear" not in out
