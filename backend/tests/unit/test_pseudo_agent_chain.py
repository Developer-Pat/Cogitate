"""The pseudo-agent chain treats an empty completion as a failure, not an answer.

WHY THIS IS A BEHAVIOUR CONTRACT AND NOT A DETAIL: an empty completion is the
shape a reasoning model produces when its thinking consumes a small max_tokens
budget — the call reports healthy and the content comes back blank. The chain
used to return that as SUCCESS, so a fan-out writing 173 descriptions would have
written blanks and reported success for every one of them. The failure mode is
silent by construction, which is why the contract is written down here.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.pseudo_agents.spec import (
    ChainStep,
    PseudoAgentError,
    PseudoAgentSpec,
    invoke,
)


class _FakeResponse:
    """The slice of a langchain response the chain reads."""

    def __init__(self, content: Any) -> None:
        self.content = content
        self.usage_metadata = {"input_tokens": 3, "output_tokens": 7, "total_tokens": 10}


@pytest.fixture
def chain_llm(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], dict[str, Any]]:
    """Patch the client factory; return (the models called, the canned answers).

    The fake reads the MODEL off the step, so a test can give each step of the
    chain its own answer — which is the only way to prove a fall-through: the
    second step's reply must be the one that comes back.
    """
    calls: list[str] = []
    answers: dict[str, Any] = {}

    def fake_get_llm_from_config(cfg: Any, **kwargs: Any) -> Any:
        model = (cfg.config or {}).get("default_model", "")

        class _FakeLLM:
            def invoke(self, prompt: str) -> _FakeResponse:
                calls.append(model)
                answer = answers.get(model, "")
                if isinstance(answer, Exception):
                    raise answer
                return _FakeResponse(answer)

        return _FakeLLM()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory.get_llm_from_config", fake_get_llm_from_config
    )
    return calls, answers


def _step(model: str) -> ChainStep:
    return ChainStep(provider="fake", model=model, has_api_key=False)


def _spec(*models: str, allow_empty: bool = False) -> PseudoAgentSpec:
    return PseudoAgentSpec(
        name="test-chain",
        system_prompt="Answer.",
        chain=tuple(_step(m) for m in models),
        allow_empty=allow_empty,
    )


# ── IT FIRES: empty is a failure ────────────────────────────────────────────


def test_an_empty_answer_falls_through_to_the_next_step(chain_llm) -> None:
    calls, answers = chain_llm
    answers["first"] = ""
    answers["second"] = "the real answer"

    result = invoke(_spec("first", "second"), "prompt")

    assert result.text == "the real answer"
    assert result.served_by == "fake/second"
    assert result.degraded is True
    assert calls == ["first", "second"], "the empty step must still be TRIED"


def test_a_whitespace_only_answer_is_empty_too(chain_llm) -> None:
    calls, answers = chain_llm
    answers["first"] = "   \n\t "
    answers["second"] = "the real answer"

    result = invoke(_spec("first", "second"), "prompt")

    assert result.text == "the real answer"
    assert result.served_by == "fake/second"


def test_a_none_content_is_empty_too(chain_llm) -> None:
    _, answers = chain_llm
    answers["first"] = None
    answers["second"] = "the real answer"

    assert invoke(_spec("first", "second"), "prompt").served_by == "fake/second"


def test_the_empty_attempt_is_recorded_with_its_reason(chain_llm) -> None:
    """The provenance must NAME the empty, or a degraded run cannot be audited."""
    _, answers = chain_llm
    answers["first"] = ""
    answers["second"] = "the real answer"

    result = invoke(_spec("first", "second"), "prompt")

    assert result.attempts[0]["ok"] is False
    assert result.attempts[0]["error"] == "empty content"
    assert result.attempts[1]["ok"] is True


def test_a_chain_of_empties_raises(chain_llm) -> None:
    """The module's stated contract: all-failed RAISES, and empty counts."""
    calls, answers = chain_llm
    answers["first"] = ""
    answers["second"] = "  "

    with pytest.raises(PseudoAgentError) as excinfo:
        invoke(_spec("first", "second"), "prompt")

    assert "fake/first" in str(excinfo.value)
    assert calls == ["first", "second"], "every step is tried before giving up"


# ── IT STAYS QUIET: a real answer is not second-guessed ─────────────────────


def test_a_non_empty_answer_short_circuits_the_chain(chain_llm) -> None:
    calls, answers = chain_llm
    answers["first"] = "ok"
    answers["second"] = "never asked for"

    result = invoke(_spec("first", "second"), "prompt")

    assert result.text == "ok"
    assert result.served_by == "fake/first"
    assert result.degraded is False
    assert calls == ["first"], "the fallback must not be called at all"


def test_an_exception_still_moves_the_chain_along(chain_llm) -> None:
    """The sibling path — the guard must not have displaced it."""
    _, answers = chain_llm
    answers["first"] = RuntimeError("provider exploded")
    answers["second"] = "the real answer"

    result = invoke(_spec("first", "second"), "prompt")

    assert result.text == "the real answer"
    assert result.attempts[0]["error"].startswith("provider exploded")


def test_allow_empty_keeps_an_empty_answer(chain_llm) -> None:
    """The escape hatch: where "" is what the prompt asked for, it is a result."""
    calls, answers = chain_llm
    answers["first"] = ""
    answers["second"] = "never asked for"

    result = invoke(_spec("first", "second", allow_empty=True), "prompt")

    assert result.text == ""
    assert result.served_by == "fake/first"
    assert result.degraded is False
    assert calls == ["first"], "an accepted empty answer must not fall through"


def test_the_catalog_specs_default_to_rejecting_empty() -> None:
    """The specs the workflows actually run inherit the guard."""
    from app.domain.pseudo_agents.catalog import CATALOG

    for name, spec in CATALOG.items():
        assert spec.allow_empty is False, f"{name} would accept an empty answer"


# ── THE FLOOR RETRY (2026-09-26): an empty answer gets ONE more chance ──────


def _floor_fixture(
    monkeypatch: pytest.MonkeyPatch, answers_by_call: list[Any], exhaust_budget: bool = True
):
    """Patch the factory and record the BUDGET of every call.

    The `chain_llm` fixture records models only; the floor retry is a budget
    change on the SAME step, so the budget is what a test has to see.

    `exhaust_budget` models the SIGNAL the retry fires on: an empty answer whose
    reported output tokens hit the budget it was given (the tag survey's
    `ling-3.0-flash-sante` case, `out_tokens=4000` on a 4000 budget). With it
    False the empty is reported as cheap, which is the shape that must NOT be
    retried.
    """
    from app.services.cognitive_pipeline.reasoning_support import (
        REASONING_MAX_TOKENS_FLOOR,
    )

    seen: list[tuple[str, int | None]] = []
    queue = list(answers_by_call)

    def fake_get_llm_from_config(cfg: Any, **kwargs: Any) -> Any:
        model = (cfg.config or {}).get("default_model", "")
        budget = kwargs.get("max_tokens")

        class _FakeLLM:
            def invoke(self, prompt: str) -> _FakeResponse:
                seen.append((model, budget))
                answer = queue.pop(0) if queue else ""
                if isinstance(answer, Exception):
                    raise answer
                resp = _FakeResponse(answer)
                if not (answer or "").strip() and exhaust_budget:
                    resp.usage_metadata = {"input_tokens": 3, "output_tokens": budget,
                                           "total_tokens": 3 + (budget or 0)}
                return resp

        return _FakeLLM()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory.get_llm_from_config", fake_get_llm_from_config
    )
    return seen, REASONING_MAX_TOKENS_FLOOR


def test_an_empty_answer_is_retried_once_at_the_reasoning_floor(monkeypatch) -> None:
    """A thinking driver fed the spec budget answers with nothing; the retry gives it room.

    WHY A RETRY AND NOT A NAME LIST: `is_reasoning_model()` matches r1 / -r /
    deepseek-v4 by NAME, and the model that actually failed the tag survey
    (`inclusionai/ling-3.0-flash-sante:free`) matches none of them — so the
    empty completion is the only signal that generalises. The same step is
    retried, once, at the floor.
    """
    seen, floor = _floor_fixture(monkeypatch, ["", "the answer after room"])

    result = invoke(_spec("sante"), "prompt")

    assert result.text == "the answer after room"
    assert result.served_by == "fake/sante"
    assert seen == [("sante", 4000), ("sante", floor)], (
        "the same step, once at the spec budget and once at the floor"
    )
    assert result.attempts[0]["error"] == "empty content"
    assert result.attempts[1]["ok"] is True
    assert result.attempts[1]["retried_with_floor"] == floor


def test_the_floor_retry_happens_once_and_then_the_chain_gives_up(monkeypatch) -> None:
    """One retry, not a loop — and the cost still surfaces as a failure."""
    seen, floor = _floor_fixture(monkeypatch, ["", "", ""])

    with pytest.raises(PseudoAgentError):
        invoke(_spec("sante"), "prompt")

    assert [b for _, b in seen] == [4000, floor], "exactly one retry"
    assert len(seen) == 2


def test_no_retry_when_the_budget_is_already_the_floor(monkeypatch) -> None:
    """A spec already given room is not retried — the guard stays quiet."""
    seen, floor = _floor_fixture(monkeypatch, ["", "the second step answers"])
    spec = PseudoAgentSpec(
        name="test-chain",
        system_prompt="Answer.",
        chain=(_step("sante"), _step("backup")),
        max_tokens=floor,
    )

    result = invoke(spec, "prompt")

    assert result.text == "the second step answers"
    assert seen == [("sante", floor), ("backup", floor)]


def test_an_empty_that_did_not_eat_the_budget_falls_straight_through(monkeypatch) -> None:
    """The conservative half: a cheap empty is a refusal, not a starved answer.

    Firing the retry on EVERY empty would buy a second call for every broken
    step of a forty-row fan-out. Only an empty that consumed its whole budget
    is the reasoning-driver shape.
    """
    seen, floor = _floor_fixture(
        monkeypatch, ["", "the second step answers"], exhaust_budget=False
    )

    result = invoke(_spec("sante", "backup"), "prompt")

    assert result.text == "the second step answers"
    assert seen == [("sante", 4000), ("backup", 4000)], "no retry for a cheap empty"
