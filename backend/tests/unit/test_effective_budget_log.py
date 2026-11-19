"""C.1 — the budget is WRITTEN by the resolver, and the log says what was sent.

The whole arc started from one line: the request log printed
`parameters={'max_tokens': 2000}` (the agent's DECLARED value) while a hybrid
pass 1 put 1024 on the wire. B.4 logged the sent value beside the resolver's
opinion of it; C.1 makes the resolver the writer, so the two cannot disagree.
The tests here check both halves of that: the request carries the resolved
number, and the line names it with its reason.

The log-only form (`log_effective_budget`) keeps its own tests in
`tests/unit/cognitive_pipeline/test_output_budget.py`. The request-start line
half of this file is unchanged.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from app.api.v1.chat.logging_service import ChatLoggingService
from app.api.v1.chat.router import (
    _apply_output_budget,
    _output_budget_path,
)
from app.services.cognitive_pipeline.output_budget import (
    PATH_DEFAULT,
    PATH_DEEP,
    PATH_FAST,
    PATH_PASS1,
    log_effective_budget,
)

LOGGER = "app.services.cognitive_pipeline.output_budget"

# Bob's row (agents.id=19) and the strings the app builds from it.
BOB_MODEL = "openrouter/inclusionai/ling-3.0-flash"
# G-I: the sampling parameters, and the DECLARATION in the agent's own spec.
BOB_PARAMETERS = {"temperature": 0.7, "top_p": 0.9}
BOB_SPEC = {"max_output": 2000}


def _context(runtime_config=None) -> SimpleNamespace:
    return SimpleNamespace(
        agent=SimpleNamespace(
            id=19, name="Bob", parameters=dict(BOB_PARAMETERS), llm_spec=dict(BOB_SPEC)
        ),
        model=BOB_MODEL,
        runtime_config=runtime_config,
        session_id=47,
    )


def _lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records]


class TestTheBudgetIsWrittenAndLogged:
    def test_hybrid_pass_1_writes_and_logs_the_declared_budget(self, caplog):
        """The anchor: 2000 declared, 2000 sent (C.2 — it used to be 1024)."""
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_PASS1)
        assert request["max_tokens"] == 2000
        assert any(
            "max_tokens_sent=2000 reason=declared declared=2000 path=pass1" in line
            for line in _lines(caplog)
        )

    def test_the_deep_pass_writes_and_logs_its_minimum(self, caplog):
        """2000 declared, 4096 sent — the pass's own minimum (C.3)."""
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_DEEP)
        assert request["max_tokens"] == 4096
        assert any(
            "max_tokens_sent=4096 reason=deep_min declared=2000 path=deep" in line
            for line in _lines(caplog)
        )

    def test_the_fast_path_writes_and_logs_the_policy_constant(self, caplog):
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_FAST)
        assert request["max_tokens"] == 512
        assert any(
            "max_tokens_sent=512 reason=fast_policy declared=2000 path=fast" in line
            for line in _lines(caplog)
        )

    def test_the_ordinary_turn_writes_the_declared_value(self, caplog):
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_DEFAULT)
        assert request["max_tokens"] == 2000
        assert any(
            "max_tokens_sent=2000 reason=declared declared=2000 path=default" in line
            for line in _lines(caplog)
        )

    def test_a_runtime_override_names_itself(self, caplog):
        """Writer #4 — wired, empty, reachable: it must speak through the resolver."""
        override = SimpleNamespace(max_tokens=8192)
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(runtime_config=override), request, PATH_DEFAULT)
        assert request["max_tokens"] == 8192
        # `declared` is the AGENT's own number even when an override is in play:
        # the line then tells the whole story (2000 stored, 8192 overridden).
        assert any(
            "max_tokens_sent=8192 reason=runtime_override declared=2000" in line
            for line in _lines(caplog)
        )

    def test_an_undeclared_agent_logs_no_declaration(self, caplog):
        context = _context()
        context.agent.llm_spec.pop("max_output")
        request: dict = {}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(context, request, PATH_DEFAULT)
        assert request["max_tokens"] == 4096
        assert any(
            "max_tokens_sent=4096 reason=no_declared_budget declared=none" in line
            for line in _lines(caplog)
        )

    def test_the_log_line_refuses_to_invent_a_budget(self, caplog):
        """The log-only form: nothing was sent, so the line claims nothing.

        No chat path reaches this state any more — C.1 is what makes that true
        — but the line's own contract still has to hold for any caller.
        """
        with caplog.at_level(logging.INFO, logger=LOGGER):
            log_effective_budget(None, 2000, 2000, "declared", path=PATH_DEFAULT)
        assert any("max_tokens_sent=none" in line for line in _lines(caplog))


class TestASecondWriterIsNoticed:
    """The default path's number may only ever be the resolver's (C.1).

    The paths that carry a POLICY (fast, pass 1, the deep pass) replace the
    declared number on purpose — that is the resolver's own decision, made once
    by the resolver itself. On the default path there is no such policy, so a
    request that arrives carrying a different number means something else wrote
    it, and that is worth a warning.
    """

    def test_a_default_path_request_is_corrected_and_shouted_about(self, caplog):
        request = {"max_tokens": 6144}  # nobody's declaration, nobody's policy
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_DEFAULT)
        assert request["max_tokens"] == 2000
        assert any("BUDGET OVERWRITTEN" in line for line in _lines(caplog))

    def test_a_path_policy_may_replace_the_number_quietly(self, caplog):
        """`fast` replaces the declared number BY POLICY — that is the resolver's
        own decision, not a second writer, so nothing is shouted about."""
        request = {"max_tokens": 2000}
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _apply_output_budget(_context(), request, PATH_FAST)
        assert request["max_tokens"] == 512
        assert not any("BUDGET OVERWRITTEN" in line for line in _lines(caplog))


class TestTheReasonIsTheResolvers:
    def test_every_path_reason_is_one_of_the_named_writers(self, caplog):
        cases = [
            (PATH_DEFAULT, "declared"),
            (PATH_FAST, "fast_policy"),
            (PATH_PASS1, "declared"),
            (PATH_DEEP, "deep_min"),
        ]
        with caplog.at_level(logging.INFO, logger=LOGGER):
            for path, _ in cases:
                _apply_output_budget(_context(), {}, path)
        logged = "\n".join(_lines(caplog))
        for path, reason in cases:
            assert f"reason={reason}" in logged, f"{path} did not name its reason"

    def test_the_executor_strategy_picks_the_path(self):
        assert _output_budget_path("fast") == PATH_FAST
        assert _output_budget_path("hybrid") == PATH_PASS1
        assert _output_budget_path("default") == PATH_DEFAULT
        assert _output_budget_path(None) == PATH_DEFAULT
        assert _output_budget_path("stub") == PATH_DEFAULT


class TestTheRequestStartLineNoLongerClaimsTheBudget:
    """The service duck-types a ChatContext or a plain dict — these use dicts."""

    LOGGER = "app.api.v1.chat.logging_service"

    @staticmethod
    def _context(**overrides) -> dict:
        context = {
            "session_id": 47, "agent_id": 19, "agent_name": "Bob",
            "provider": "openrouter", "model": BOB_MODEL, "messages_count": 1,
            "messages_preview": "hi", "tools_count": 0, "tools": [],
            "parameters": dict(BOB_PARAMETERS),
            # G-I: the declaration rides the AGENT — the line reads it there.
            "agent": SimpleNamespace(id=19, llm_spec=dict(BOB_SPEC)),
        }
        context.update(overrides)
        return context

    def _record(self, caplog):
        return next(r for r in caplog.records if r.getMessage() == "📡 LLM REQUEST START")

    def test_the_declared_value_is_labelled_as_declared(self, caplog):
        with caplog.at_level(logging.INFO, logger=self.LOGGER):
            ChatLoggingService().log_request_start(self._context())
        assert self._record(caplog).declared_max_tokens == 2000

    def test_an_undeclared_agent_reports_no_declaration(self, caplog):
        """The complement: no spec, no number claimed."""
        with caplog.at_level(logging.INFO, logger=self.LOGGER):
            ChatLoggingService().log_request_start(
                self._context(agent=SimpleNamespace(id=19, llm_spec={}))
            )
        assert self._record(caplog).declared_max_tokens is None

    def test_the_parameters_field_carries_no_budget(self, caplog):
        """The misleading field: the number can no longer hide inside it."""
        with caplog.at_level(logging.INFO, logger=self.LOGGER):
            ChatLoggingService().log_request_start(self._context())
        record = self._record(caplog)
        assert "max_tokens" not in record.parameters
        assert record.parameters == {"temperature": 0.7, "top_p": 0.9}

    def test_a_context_without_parameters_still_logs(self, caplog):
        with caplog.at_level(logging.INFO, logger=self.LOGGER):
            ChatLoggingService().log_request_start(
                self._context(parameters=None, agent=SimpleNamespace(id=19, llm_spec={}))
            )
        record = self._record(caplog)
        assert record.declared_max_tokens is None and record.parameters == {}
