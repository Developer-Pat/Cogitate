"""A chain step NAMES A PROVIDER ROW; the row supplies the service.

A step used to re-state what the provider row already holds — `provider="deepseek"`,
`model="deepseek-v4-flash"`, `base_url="https://api.deepseek.com"` — three copies of one
row's answer, free to drift from it. A step now names the row (`provider_row`) and takes the
row's provider_type, base_url and configured model, with anything the step states itself
winning over it.

The resolution is asserted WITHOUT the database (a synthetic `rows` mapping goes straight
into `_step_service`), plus one test that drives the real `invoke` to prove the resolved
model is the one handed to the client factory.
"""

from __future__ import annotations

from typing import Any

from app.domain.pseudo_agents import spec as spec_mod
from app.domain.pseudo_agents.spec import (
    ChainStep,
    PseudoAgentSpec,
    _step_service,
    invoke,
)

ROWS = {
    "deepseek": {
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-flash",
    },
    "openrouter": {
        "provider_type": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-v4-flash",
    },
}


# ── the resolution itself ───────────────────────────────────────────────────


def test_a_step_naming_a_row_takes_its_whole_service_from_the_row():
    """Nothing but the row name: the endpoint and the model both come from it."""
    step = ChainStep(provider_row="deepseek")

    assert _step_service(step, ROWS) == ("deepseek", "https://api.deepseek.com", "deepseek-v4-flash")


def test_a_model_the_step_states_wins_over_the_row():
    """The free route pins its model precisely because the row's default is the paid one."""
    step = ChainStep(provider_row="openrouter", model="inclusionai/ling-3.0-flash-sante:free")

    provider_type, base_url, model = _step_service(step, ROWS)

    assert model == "inclusionai/ling-3.0-flash-sante:free"
    assert provider_type == "openrouter", "the row still supplies the rest"
    assert base_url == "https://openrouter.ai/api/v1"


def test_a_step_naming_no_row_uses_its_own_fields():
    """The rowless form — the local step, which the `llama` row cannot describe today."""
    step = ChainStep(provider="openai", model="", base_url="http://127.0.0.1:8080/v1")

    provider_type, base_url, model = _step_service(step, ROWS)

    assert (provider_type, base_url) == ("openai", "http://127.0.0.1:8080/v1")
    assert model == "", "no row and no stated model — nothing is invented"


def test_a_row_name_that_matches_nothing_does_not_invent_a_service():
    """A typo'd row name must fall back to the step's own fields, not to someone else's."""
    step = ChainStep(provider="groq", provider_row="grok")

    provider_type, base_url, model = _step_service(step, ROWS)

    assert provider_type == "groq"
    assert base_url is None
    assert model == ""


class _StubLLM:
    """The slice of a langchain client the chain uses."""

    def __init__(self, content: str = "an answer") -> None:
        self._content = content

    def invoke(self, prompt: str) -> "_FakeResponse":
        return _FakeResponse(self._content)


def test_the_rows_are_read_per_invocation_not_once_at_import(monkeypatch):
    """A chain is a module-level constant; a value read into it would be frozen forever."""
    reads: list[int] = []

    def counting_rows() -> dict[str, Any]:
        reads.append(1)
        return ROWS

    monkeypatch.setattr(spec_mod, "_provider_rows", counting_rows)
    monkeypatch.setattr(
        "app.domain.providers.llm_factory.get_llm_from_config", lambda cfg, **kw: _StubLLM()
    )

    spec = PseudoAgentSpec(
        name="row-test", system_prompt="Answer.", chain=(ChainStep(provider_row="deepseek"),)
    )
    invoke(spec, "prompt")
    invoke(spec, "prompt")

    assert len(reads) == 2, "the rows must be read per call, not captured at import"


# ── through the real call path ──────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = {"input_tokens": 3, "output_tokens": 7, "total_tokens": 10}


def test_a_row_named_step_sends_the_rows_model_to_the_client(monkeypatch):
    """The whole point: the model on the wire is the ROW's, not a copy in the chain."""
    calls: list[str] = []

    def fake_get_llm_from_config(cfg: Any, **kwargs: Any) -> Any:
        class _FakeLLM:
            def invoke(self, prompt: str) -> _FakeResponse:
                calls.append((cfg.config or {}).get("default_model", ""))
                return _FakeResponse("an answer")

        return _FakeLLM()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory.get_llm_from_config", fake_get_llm_from_config
    )
    monkeypatch.setattr(spec_mod, "_provider_rows", lambda: ROWS)

    result = invoke(
        PseudoAgentSpec(
            name="row-test",
            system_prompt="Answer.",
            chain=(ChainStep(provider_row="deepseek"),),
        ),
        "prompt",
    )

    assert calls == ["deepseek-v4-flash"], "the row's configured model is what went out"
    assert result.served_by == "deepseek/deepseek-v4-flash"
    assert result.attempts[0]["provider"] == "deepseek", (
        "the provenance names the row's provider_type, resolved at call time"
    )
