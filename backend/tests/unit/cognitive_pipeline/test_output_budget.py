"""The resolver's own rows — B.2's table, moved by C.2 and C.3.

Phase B pinned the values the paths send (`min(declared, 512)` / `min(declared,
1024)` / the forced 4096) so C's diff could only be the rows someone meant to
change. **C.2 and C.3 moved all three**, and they are asserted here in their new
shape:

* `fast` runs on a named policy constant — the profile's promise, logged;
* hybrid pass 1 runs on the agent's DECLARED value (a first pass meant to lead
  somewhere must not run on a quarter budget, D1);
* the deep pass is `max(declared, 4096)`, so a raised declaration reaches it and
  the reasoning floor has the last word (D1's "the deep pass overwrites it
  anyway" is what made the old forced 4096 pointless).

The agent row used is Bob's, verbatim from the database (`agents.id=19`:
`inclusionai/ling-3.0-flash`, `{"temperature": 0.7, "max_tokens": 2000,
"top_p": 0.9}`, cognitive profile 8 = `chat-skill` → the `hybrid` executor).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.cognitive_pipeline.output_budget import (
    DEEP_MIN_BUDGET,
    FALLBACK_BUDGET,
    FAST_POLICY_BUDGET,
    PATH_DEFAULT,
    PATH_DEEP,
    PATH_FAST,
    PATH_PASS1,
    REASON_DECLARED,
    REASON_DEEP_MIN,
    REASON_FAST_POLICY,
    REASON_NO_DECLARATION,
    REASON_OVERRIDE,
    REASON_THINKING_FLOOR,
    REASON_THINKING_MANDATORY,
    REASON_WINDOW_CLAMP,
    WINDOW_CLAMP_FLOOR,
    declared_output_budget,
    declared_thinking,
    effective_budget_line,
    floor_budget,
    estimate_prompt_tokens,
    floors_for,
    log_effective_budget,
    resolve_output_budget,
)
from app.domain.chat.token_budget import estimate_tokens
from app.services.cognitive_pipeline.reasoning_support import (
    SOURCE_PROVIDER_CLAIM,
    ThinkingSignal,
)

# Bob's row, and the model strings the app actually builds.
BOB_MODEL = "openrouter/inclusionai/ling-3.0-flash"
THINKING_MODEL = "deepseek/deepseek-v4-flash"
THINKING_FLOOR = 16000


def _agent(declared: int | None = 2000) -> SimpleNamespace:
    """Bob's row: the declaration lives in his OWN spec (G-I's one slot)."""
    spec: dict = {}
    if declared is not None:
        spec["max_output"] = declared
    return SimpleNamespace(
        id=19, name="Bob", parameters={"temperature": 0.7, "top_p": 0.9}, llm_spec=spec
    )


class TestTheDeclaredValue:
    def test_the_agents_own_number_is_read(self):
        assert declared_output_budget(_agent(2000)) == 2000
        assert declared_output_budget(_agent(8192)) == 8192

    def test_an_undeclared_agent_reads_as_none(self):
        assert declared_output_budget(_agent(None)) is None
        assert declared_output_budget(SimpleNamespace(llm_spec=None)) is None
        assert declared_output_budget(SimpleNamespace()) is None
        assert declared_output_budget(None) is None

    def test_a_plain_spec_mapping_is_accepted(self):
        assert declared_output_budget({"llm_spec": {"max_output": 4096}}) == 4096

    def test_the_retired_homes_are_not_declarations(self):
        """G-I: the declaration is the spec. A row carrying only the old key or the
        old bare attribute is UNDECLARED — the writer-facing guard is the API's
        refusal, and this reader must not be a second interpreter of either field."""
        assert declared_output_budget(SimpleNamespace(parameters={"max_tokens": 1500})) is None
        assert declared_output_budget(SimpleNamespace(max_tokens=1500, session_id=1)) is None

    def test_a_non_numeric_value_reads_as_undeclared(self):
        assert declared_output_budget(_agent("many")) is None  # type: ignore[arg-type]


class TestThePaths:
    """Every path, at Bob's declared 2000 — the numbers the router sends today."""

    def test_the_ordinary_path_sends_the_declared_value(self):
        assert resolve_output_budget(_agent(), BOB_MODEL, path=PATH_DEFAULT) == (
            2000, REASON_DECLARED,
        )

    def test_the_fast_path_runs_on_the_policy_constant(self):
        """`fast` promises a short answer; the constant IS that promise (C.2)."""
        assert resolve_output_budget(_agent(), BOB_MODEL, path=PATH_FAST) == (
            FAST_POLICY_BUDGET, REASON_FAST_POLICY,
        )

    def test_hybrid_pass_1_runs_on_the_declared_budget(self):
        """The cap that silently quartered the first pass is gone (C.2)."""
        assert resolve_output_budget(_agent(), BOB_MODEL, path=PATH_PASS1) == (
            2000, REASON_DECLARED,
        )

    def test_the_deep_pass_keeps_its_own_minimum(self):
        """C.3: 4096 is a named minimum now, not an override of everything."""
        assert resolve_output_budget(_agent(), BOB_MODEL, path=PATH_DEEP) == (
            DEEP_MIN_BUDGET, REASON_DEEP_MIN,
        )

    def test_the_deep_pass_lets_a_larger_declaration_through(self):
        """8192 declared used to run at 4096; now it runs at 8192."""
        assert resolve_output_budget(_agent(8192), BOB_MODEL, path=PATH_DEEP) == (
            8192, REASON_DECLARED,
        )

    def test_the_default_path_is_the_declared_value(self):
        assert resolve_output_budget(_agent(), BOB_MODEL) == (2000, REASON_DECLARED)

    def test_an_unknown_path_is_refused(self):
        with pytest.raises(ValueError):
            resolve_output_budget(_agent(), BOB_MODEL, path="sideways")


class TestAnUndeclaredBudget:
    def test_the_router_fallback_is_what_runs(self):
        assert resolve_output_budget(_agent(None), BOB_MODEL) == (
            FALLBACK_BUDGET, REASON_NO_DECLARATION,
        )

    def test_the_fallback_runs_on_the_paths_with_no_policy_of_their_own(self):
        """Nothing declared: the fast policy still speaks, pass 1 does not (C.2)."""
        assert resolve_output_budget(_agent(None), BOB_MODEL, path=PATH_FAST)[0] == FAST_POLICY_BUDGET
        assert resolve_output_budget(_agent(None), BOB_MODEL, path=PATH_PASS1)[0] == FALLBACK_BUDGET


class TestTheRuntimeOverride:
    """D2: the per-session override stays, and it routes THROUGH the resolver."""

    def test_the_override_wins_over_the_declared_value(self):
        assert resolve_output_budget(_agent(2000), BOB_MODEL, override=8192) == (
            8192, REASON_OVERRIDE,
        )

    def test_pass_1_runs_on_the_declared_override(self):
        """The override is a declaration too, and pass 1 no longer quarters it."""
        assert resolve_output_budget(_agent(2000), BOB_MODEL, path=PATH_PASS1, override=8192) == (
            8192, REASON_OVERRIDE,
        )

    def test_the_deep_pass_leaves_the_declared_override_alone(self):
        """Pass 1 and the deep pass both run on a raised override now (C.3)."""
        assert resolve_output_budget(_agent(2000), BOB_MODEL, path=PATH_DEEP, override=8192) == (
            8192, REASON_OVERRIDE,
        )


class TestTheReasoningFloor:
    def test_the_name_pattern_is_the_trigger(self):
        assert floors_for(THINKING_MODEL)
        assert not floors_for(BOB_MODEL)

    def test_a_declared_thinking_driver_floors_too(self):
        """The F.3 seam — a declaration the name pattern cannot see."""
        assert floors_for(BOB_MODEL, thinking=True)

    def test_the_floor_raises_the_ordinary_path(self):
        assert resolve_output_budget(_agent(2000), THINKING_MODEL) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_the_floor_wins_over_the_fast_policy(self):
        """512 is eaten whole by thinking, so 16000 is sent (the ox-alpha dig)."""
        assert resolve_output_budget(_agent(2000), THINKING_MODEL, path=PATH_FAST) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_the_floor_raises_a_pass_1_below_it(self):
        assert resolve_output_budget(_agent(2000), THINKING_MODEL, path=PATH_PASS1) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_the_deep_pass_no_longer_drops_below_the_floor(self):
        """C.3's headline: the pass that used to run at 4096 now runs at 16000."""
        assert resolve_output_budget(_agent(2000), THINKING_MODEL, path=PATH_DEEP) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_a_budget_above_the_floor_is_left_alone(self):
        assert resolve_output_budget(_agent(20000), THINKING_MODEL) == (20000, REASON_DECLARED)

    def test_a_non_reasoning_model_passes_through(self):
        assert resolve_output_budget(_agent(2000), "openrouter/nvidia/nemotron-3")[0] == 2000

    def test_thinking_true_raises_an_unknown_family(self):
        assert resolve_output_budget(_agent(2000), BOB_MODEL, thinking=True) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )


class TestTheWindowClampsTheBudget:
    """E.2 — physics last: the only limit allowed to LOWER a budget we chose.

    The window is applied AFTER the path's policy and AFTER the reasoning floor,
    and only when BOTH the window and the prompt's size are known. Either number
    missing means no clamp — a missing measurement is not a limit (B.1's rule),
    which is what keeps an unrecorded driver behaving exactly as it did before E.
    """

    def test_a_budget_that_cannot_fit_is_lowered_to_the_allowance(self):
        assert resolve_output_budget(
            _agent(8192), BOB_MODEL, window=20000, prompt_tokens=15000,
        ) == (5000, REASON_WINDOW_CLAMP)

    def test_a_budget_that_fits_is_untouched(self):
        """The clamp is not a cap on the window: it only bites when it must."""
        assert resolve_output_budget(
            _agent(2000), BOB_MODEL, window=20000, prompt_tokens=500,
        ) == (2000, REASON_DECLARED)

    def test_an_absent_window_does_not_clamp(self):
        assert resolve_output_budget(
            _agent(2000), BOB_MODEL, window=None, prompt_tokens=99999,
        ) == (2000, REASON_DECLARED)

    def test_an_absent_prompt_estimate_does_not_clamp(self):
        """No measurement, no limit — even a window far too small for the budget."""
        assert resolve_output_budget(
            _agent(8192), BOB_MODEL, window=4096, prompt_tokens=None,
        ) == (8192, REASON_DECLARED)

    def test_the_window_outranks_the_reasoning_floor(self):
        """A driver whose window cannot hold the floor is replaced, not exceeded.

        The floor is a policy number; the window is physics (`roadmap.md` §2), and
        E.3 is what warns about this state at match time.
        """
        assert resolve_output_budget(
            _agent(2000), THINKING_MODEL, window=12000, prompt_tokens=4000,
        ) == (8000, REASON_WINDOW_CLAMP)

    def test_a_prompt_that_fills_the_window_leaves_the_sendable_minimum(self):
        """`max_tokens=0` is not sendable — the clamp stops at 1 and says so."""
        assert resolve_output_budget(
            _agent(2000), BOB_MODEL, window=8000, prompt_tokens=8000,
        ) == (WINDOW_CLAMP_FLOOR, REASON_WINDOW_CLAMP)
        assert resolve_output_budget(
            _agent(2000), BOB_MODEL, window=4000, prompt_tokens=9000,
        ) == (WINDOW_CLAMP_FLOOR, REASON_WINDOW_CLAMP)

    def test_the_clamp_is_logged_with_the_numbers_it_clamped_between(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="app.services.cognitive_pipeline.output_budget"):
            resolve_output_budget(_agent(8192), BOB_MODEL, window=20000, prompt_tokens=15000)

        assert "WINDOW CLAMP" in caplog.text
        assert "window=20000" in caplog.text
        assert "prompt_tokens=15000" in caplog.text
        assert "clamped=5000" in caplog.text
        assert "reason=window_clamp" in caplog.text


class TestThePromptEstimate:
    """What the clamp measures (`estimate_prompt_tokens`) — and when it measures nothing."""

    def test_no_messages_is_no_measurement(self):
        assert estimate_prompt_tokens(None) is None
        assert estimate_prompt_tokens([]) is None

    def test_a_prompt_is_measured_with_its_message_overhead(self):
        estimate = estimate_prompt_tokens([{"role": "user", "content": "hello world"}])
        assert estimate is not None and estimate >= estimate_tokens("hello world")

    def test_tool_schemas_count(self):
        """Their schemas are the part of a prompt that grows without the chat growing."""
        messages = [{"role": "user", "content": "hello"}]
        tools = [{"type": "function", "function": {"name": "web_search", "description": "x" * 400}}]

        without_tools = estimate_prompt_tokens(messages)
        with_tools = estimate_prompt_tokens(messages, tools)

        assert without_tools is not None and with_tools is not None
        assert with_tools > without_tools

    def test_junk_in_the_content_does_not_crash_the_estimate(self):
        assert estimate_prompt_tokens([{"role": "user", "content": None}]) is not None


class TestTheEffectiveBudgetLine:
    def test_the_line_names_the_sent_value_its_reason_and_the_declared_one(self):
        line = effective_budget_line(512, 2000, REASON_FAST_POLICY, PATH_FAST)
        assert line == (
            "max_tokens_sent=512 reason=fast_policy declared=2000 path=fast"
        )

    def test_an_undeclared_budget_prints_plainly(self):
        assert "declared=none" in effective_budget_line(4096, None, REASON_NO_DECLARATION, PATH_DEFAULT)

    def test_the_line_is_logged_with_the_model_and_session(self, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="app.services.cognitive_pipeline.output_budget"):
            log_effective_budget(
                512, 512, 2000, REASON_FAST_POLICY,
                path=PATH_FAST, model=BOB_MODEL, session_id=47,
            )
        assert any(
            "💰 EFFECTIVE OUTPUT BUDGET max_tokens_sent=512 reason=fast_policy "
            "declared=2000 path=fast" in r.message
            for r in caplog.records
        )

    def test_a_mismatch_is_shouted_about(self, caplog):
        """The tripwire, run on every real turn instead of only in a test."""
        import logging

        with caplog.at_level(logging.WARNING, logger="app.services.cognitive_pipeline.output_budget"):
            log_effective_budget(
                1024, 512, 2000, REASON_FAST_POLICY, path=PATH_FAST, model=BOB_MODEL,
            )
        assert any("BUDGET MISMATCH" in r.message for r in caplog.records)

    def test_a_match_is_not_shouted_about(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="app.services.cognitive_pipeline.output_budget"):
            log_effective_budget(
                FAST_POLICY_BUDGET, FAST_POLICY_BUDGET, 2000, REASON_FAST_POLICY, path=PATH_FAST,
            )
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestTheOneDeclarationSlot:
    """G-I — one declaration, in the agent's own `llm_spec.max_output`.

    F.1's two-slot order (the row's `parameters.max_tokens` outranking the spec's
    `max_output`) is gone. It produced a field that only adoption could write and a
    field the form wrote that meant something else; they are one field now. The class
    default arrives by COPY at adoption, so nothing here reads a package row — which
    is why `type_default` retired as a reason.
    """

    def test_the_spec_is_what_decides_the_call(self):
        agent = SimpleNamespace(id=19, name="Bob", llm_spec={"kind": "chat", "max_output": 8192})
        assert resolve_output_budget(agent, BOB_MODEL) == (8192, REASON_DECLARED)

    def test_the_runtime_override_still_outranks_the_declaration(self):
        agent = SimpleNamespace(id=19, name="Bob", llm_spec={"max_output": 8192})
        assert resolve_output_budget(agent, BOB_MODEL, override=4096) == (4096, REASON_OVERRIDE)

    def test_a_spec_declaring_nothing_leaves_the_fallback(self):
        agent = SimpleNamespace(
            id=19, name="Bob", llm_spec={"kind": "chat", "thinking": "none"}
        )
        assert resolve_output_budget(agent, BOB_MODEL) == (
            FALLBACK_BUDGET, REASON_NO_DECLARATION,
        )

    def test_a_spec_that_is_not_a_mapping_is_ignored(self):
        """A malformed contract is not a budget — it is undeclared."""
        assert declared_output_budget(SimpleNamespace(llm_spec="chat")) is None
        assert declared_output_budget(SimpleNamespace()) is None

    def test_the_declaration_flows_through_the_paths(self):
        """Pass 1 and the deep pass take it like any declaration (C.3's rule)."""
        agent = SimpleNamespace(id=19, name="Bob", llm_spec={"max_output": 8192})
        assert resolve_output_budget(agent, BOB_MODEL, path=PATH_PASS1) == (
            8192, REASON_DECLARED,
        )
        assert resolve_output_budget(agent, BOB_MODEL, path=PATH_DEEP) == (
            8192, REASON_DECLARED,
        )

    def test_a_thinking_driver_floors_the_declaration_too(self):
        """The floor applies to whatever number spoke, a declaration included."""
        agent = SimpleNamespace(id=19, name="Bob", llm_spec={"max_output": 8192})
        assert resolve_output_budget(agent, THINKING_MODEL) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_the_shipped_package_declares_the_ladder_s_shallow_class(self):
        """The package half: a new install's shallow agents inherit the class base."""
        from app.domain.agent_packages.seeds import SHALLOW_LLM_SPEC
        from app.services.cognitive_pipeline.output_budget import TYPE_BUDGETS, TYPE_SHALLOW

        assert SHALLOW_LLM_SPEC["max_output"] == TYPE_BUDGETS[TYPE_SHALLOW]


PLAIN = "openrouter/some-unrecorded-model"


class TestTheThinkingChain:
    """F.3 — the floor keys off the driver's RECORD; the name pattern is the fallback.

    Order, strongest evidence first: the signal a caller resolved about the driver (the
    provider's claim, else our curated label), then the agent's OWN declaration, then
    the name list. Any one of them saying "this thinks" is enough.
    """

    def test_the_agents_own_declaration_is_enough(self):
        agent = SimpleNamespace(llm_spec={"max_output": 2000, "thinking": "high"})
        assert declared_thinking(agent).thinking
        assert resolve_output_budget(agent, PLAIN) == (THINKING_FLOOR, REASON_THINKING_FLOOR)

    def test_a_none_declaration_states_nothing(self):
        agent = SimpleNamespace(llm_spec={"max_output": 2000, "thinking": "none"})
        assert declared_thinking(agent) is None
        assert resolve_output_budget(agent, PLAIN) == (2000, REASON_DECLARED)

    def test_the_drivers_record_speaks_when_the_row_is_silent(self):
        """The live case: our label and the provider's claim disagree; the claim wins."""
        agent = SimpleNamespace(llm_spec={"max_output": 8192, "thinking": "none"})
        signal = ThinkingSignal(thinking=True, source=SOURCE_PROVIDER_CLAIM)
        assert resolve_output_budget(agent, BOB_MODEL, signal) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_a_mandatory_claim_is_its_own_reason(self):
        agent = SimpleNamespace(llm_spec={"max_output": 8192})
        signal = ThinkingSignal(thinking=True, mandatory=True, source=SOURCE_PROVIDER_CLAIM)
        assert resolve_output_budget(agent, BOB_MODEL, signal) == (
            THINKING_FLOOR, REASON_THINKING_MANDATORY,
        )

    def test_the_name_pattern_still_answers_for_an_unrecorded_driver(self):
        agent = SimpleNamespace(llm_spec={"max_output": 2000})
        assert resolve_output_budget(agent, THINKING_MODEL) == (
            THINKING_FLOOR, REASON_THINKING_FLOOR,
        )

    def test_a_high_declaration_is_not_doubled_behind_the_users_back(self):
        """F-A: the ×2 is a statement about a DEFAULT, never about a declaration."""
        agent = SimpleNamespace(llm_spec={"max_output": 20000, "thinking": "high"})
        assert resolve_output_budget(agent, PLAIN) == (20000, REASON_DECLARED)

    def test_the_executor_paths_helper_knows_the_declaration_too(self):
        """`floor_budget` is the executor's door into the same rule (F-B)."""
        agent = SimpleNamespace(llm_spec={"thinking": "high"})
        assert floor_budget(PLAIN, 2000, agent=agent) == THINKING_FLOOR
        assert floor_budget(PLAIN, 2000) == 2000
