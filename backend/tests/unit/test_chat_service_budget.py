"""The non-chat writers call the resolver too (the token-limit arc, C.1).

The study (`local/token-limits/study.md` §3) counted the STREAMING path's seven
writers. Two more live writers were found when C's code was read, and the phase
ruling was to fold them in rather than leave them: the `ChatService` (reached by
the workflow distributor's "hand it a task") and the `/chat/delegate` endpoint
(the conduit's delegation target). Both build a request whose budget came
straight from `agent.parameters` — no floor — so a thinking model delegated to
answered nothing at all.

`ChatService` routes through `_output_budget`, which is what this file tests: the
number comes from the resolver, and `None` still means "nothing declared, send
none" (the meaning `CompletionRequest(max_tokens=None)` already had).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from app.domain.chat.services import _output_budget

LOGGER = "app.domain.chat.services"

BOB_MODEL = "inclusionai/ling-3.0-flash"
THINKING_MODEL = "deepseek/deepseek-v4-flash"


def _agent(model: str = BOB_MODEL, declared: int | None = 2000) -> SimpleNamespace:
    """Bob's row with the declaration in his OWN spec (G-I's one slot)."""
    spec: dict = {}
    if declared is not None:
        spec["max_output"] = declared
    return SimpleNamespace(
        id=19, name="Bob", model=model,
        parameters={"temperature": 0.7, "top_p": 0.9}, llm_spec=spec,
    )


def _lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records]


class TestChatServiceUsesTheResolver:
    def test_the_agents_declaration_is_the_budget(self, caplog):
        with caplog.at_level(logging.INFO, logger=LOGGER):
            assert _output_budget(_agent()) == 2000
        assert any("reason=declared" in line for line in _lines(caplog))

    def test_an_undeclared_agent_sends_none(self, caplog):
        """`max_tokens=None` is this surface's existing "let the provider decide"."""
        with caplog.at_level(logging.INFO, logger=LOGGER):
            assert _output_budget(_agent(declared=None)) is None
        assert not _lines(caplog), "nothing was decided, so nothing should be logged"

    def test_a_thinking_model_gets_its_floor(self):
        """The bug this closed: the delegated turn ran on 2000 with no floor."""
        assert _output_budget(_agent(THINKING_MODEL)) == 16000

    def test_the_runtime_override_wins(self):
        override = SimpleNamespace(max_tokens=8192)
        assert _output_budget(_agent(), override) == 8192

    def test_the_override_alone_still_logs_its_reason(self, caplog):
        override = SimpleNamespace(max_tokens=8192)
        with caplog.at_level(logging.INFO, logger=LOGGER):
            assert _output_budget(_agent(declared=None), override) == 8192
        assert any("reason=runtime_override" in line for line in _lines(caplog))
