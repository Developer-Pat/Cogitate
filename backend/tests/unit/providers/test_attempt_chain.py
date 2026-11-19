"""The chain walk — one attempt at a time, every failure named (R3).

`capabilities.attempt_chain` is the app's ONE failover: the order comes from `resolve()`, the walk
happens here, and the caller supplies only "how to attempt one candidate". What these tests hold
still is what a degraded chain must leave behind:

* the answer came from the BACKUP when the primary failed, and the caller can say which backups it
  tried (`fell_back_to`) — the surface that warns the user reads that;
* **every failure is logged with its provider, its model and WHICH ATTEMPT it was** — the user's
  ruling (2026-09-30: *"a failure needs to be logged, including the backup service failure"*), and
  the reason this loop exists rather than one per surface;
* the LAST error is what the caller sees, and a chain that may not fail over raises the PRIMARY's
  (the `fallback_enabled=False` semantics — fail visibly, never silently mask);
* an empty chain is a programming error, not a quiet success.

No database, no LLM: the loop is session-free by design, so a fake `call` exercises it completely.
"""

from __future__ import annotations

import logging

import pytest

from app.domain.providers.capabilities import SOURCE_AGENT, ServiceCandidate, attempt_chain


def _chain(*specs: tuple[str, str]) -> tuple[ServiceCandidate, ...]:
    """An ordered chain, primary first (what a resolution hands the loop)."""
    return tuple(
        ServiceCandidate(ordinal=index, provider=provider, model=model, source=SOURCE_AGENT)
        for index, (provider, model) in enumerate(specs)
    )


def _call_that(*behaviours):
    """A `call` that yields the given results in order — an exception is raised."""
    calls: list[ServiceCandidate] = []
    pending = list(behaviours)

    async def _call(candidate: ServiceCandidate) -> str:
        calls.append(candidate)
        result = pending.pop(0)
        if isinstance(result, Exception):
            raise result
        return str(result)

    return _call, calls


@pytest.mark.anyio
async def test_the_primary_answering_never_touches_the_backups() -> None:
    """A healthy primary = one attempt, no failover — the loop's happy path."""
    call, calls = _call_that("primary answered")

    outcome = await attempt_chain(
        _chain(("deepseek", "deepseek-v4-flash"), ("llama", "local")), call=call, capability="chat"
    )

    assert outcome.response == "primary answered"
    assert [c.provider for c in calls] == ["deepseek"]
    assert outcome.failed_over is False
    assert outcome.fell_back_to == ()
    assert outcome.winner is not None and outcome.winner.role == "primary"


@pytest.mark.anyio
async def test_a_failing_primary_hands_the_answer_to_the_backup() -> None:
    """The degraded case: the backup answers, and the caller can name what it tried."""
    call, calls = _call_that(RuntimeError("primary down"), "backup answered")

    outcome = await attempt_chain(
        _chain(("deepseek", "deepseek-v4-flash"), ("llama", "local-model")),
        call=call,
        capability="chat",
    )

    assert outcome.response == "backup answered"
    assert [c.provider for c in calls] == ["deepseek", "llama"]
    assert outcome.failed_over is True
    assert outcome.fell_back_to == ("llama/local-model",)
    assert outcome.winner is not None and outcome.winner.role == "backup #1"
    assert [a.succeeded for a in outcome.attempts] == [False, True]
    assert "RuntimeError: primary down" in outcome.attempts[0].error


@pytest.mark.anyio
async def test_every_failure_is_logged_with_provider_model_and_ordinal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ruling: a failed attempt names the SERVICE, its MODEL and WHICH attempt it was."""
    call, _ = _call_that(RuntimeError("down"), RuntimeError("also down"), "third time lucky")

    with caplog.at_level(logging.ERROR):
        outcome = await attempt_chain(
            _chain(
                ("openrouter", "some/model"),
                ("deepseek", "deepseek-v4-flash"),
                ("llama", "local-model"),
            ),
            call=call,
            capability="chat",
        )

    assert outcome.response == "third time lucky"
    failures = [r for r in caplog.records if "FAILED" in r.getMessage()]
    assert len(failures) == 2, caplog.text
    first, second = failures
    # the SERVICE, its MODEL and the ORDINAL — the three things a failure statement can name
    assert first.getMessage().startswith("capability 'chat': attempt 0 (primary)")
    assert getattr(first, "provider") == "openrouter"
    assert getattr(first, "model") == "some/model"
    assert getattr(first, "ordinal") == 0
    assert getattr(second, "ordinal") == 1 and getattr(second, "provider") == "deepseek"
    assert getattr(second, "attempt_role") == "backup #1"


@pytest.mark.anyio
async def test_the_whole_chain_failing_raises_the_LAST_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No silent empty: the caller is handed the last failure, and the exhaustion is logged."""
    call, calls = _call_that(RuntimeError("first"), RuntimeError("second"), RuntimeError("last"))

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="last"):
            await attempt_chain(
                _chain(("deepseek", "m"), ("llama", "m"), ("openrouter", "m")),
                call=call,
                capability="chat",
            )

    assert len(calls) == 3
    assert any("the whole chain failed" in r.getMessage() for r in caplog.records), caplog.text


@pytest.mark.anyio
async def test_fallbacks_false_raises_the_primary_and_attempts_nothing_else() -> None:
    """`fallback_enabled=False` semantics: the primary's error, visibly, with no second attempt."""
    call, calls = _call_that(RuntimeError("provider down"), "never reached")

    with pytest.raises(RuntimeError, match="provider down"):
        await attempt_chain(
            _chain(("deepseek", "m"), ("llama", "m")),
            call=call,
            capability="chat",
            fallbacks=False,
        )

    assert [c.provider for c in calls] == ["deepseek"]


@pytest.mark.anyio
async def test_an_empty_chain_is_a_programming_error_not_a_quiet_success() -> None:
    """Nothing resolved → the caller must resolve or fail, never call the walk."""
    call, _ = _call_that("unused")

    with pytest.raises(ValueError, match="at least one candidate"):
        await attempt_chain((), call=call, capability="chat")
