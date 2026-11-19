"""B.3 — the characterization table: every budget the app sends, as it is TODAY.

**This file is the arc's resume point.** Phase B changes no behaviour, so this
table is what makes Phase C provable: C moves every path onto the resolver, and
the table's diff can then only be the rows someone meant to change. If a row
here fails after a phase, that phase moved a budget it did not admit to moving.

The columns are (agent type × executor profile × run path) — the crossing the
study (`local/token-limits/study.md` §1) says is why the numbers disagree: the
type does not decide a budget today, the PATH does. Never a measurement run
(D5): every number below is read off the code and the live turn.

**The anchor row is Bob's production turn** (`agents.id=19`,
`inclusionai/ling-3.0-flash`, `{"max_tokens": 8192}`, cognitive profile 8 =
`chat-skill` → the `hybrid` executor):

    8192 declared  →  8192 on pass 1 (the declaration itself)  →  8192 on the deep pass

All three numbers are the DECLARATION now. The first two are C.2's move (pass 1
was capped at 1024); the third is F.4's (2026-09-23): his row was raised to his
class's base — the ladder's shallow value — and because the deep pass takes the
larger of the declaration and its own named minimum (C.3), an 8192 declaration
flows straight through it instead of being flattened to 4096. If a row does not
match the live turn, this table is describing a different system. The anchor is
`test_bobs_production_turn`.

The rows B pinned as deliberately WRONG are fixed: a raised declaration now
REACHES both passes, and a thinking driver's deep pass runs at its floor instead
of below it. The values that remain are the ones the arc ruled.

**The live rows now read** (re-measured 2026-09-24, after F.1/F.2/F.3 landed):
Bob **16000** (`thinking_floor` — his driver's thinking is verified, so the 8192
declaration is floored), Wanda **8192** (`type_default` — she was re-adopted onto the
`shallow-agent` package, whose spec now declares the shallow class, and her row declares
no budget of its own), Lois **16000** (`declared` — she sits exactly ON the floor, so no
floor fires), the export test agent **16000** (`thinking_floor`, via the name pattern:
`deepseek-v4-flash` has no curated claim). A 2000 declaration is still a live CASE —
`DECLARED_OTHERS` below — because that is what keeps the deep pass's minimum
(`deep_min`, 4096) pinned as behaviour rather than a memory.

The second half of the table — **the limit set in force per path** — is
`TestTheLimitsArmedToday`: the tool guard's ceilings as `Limit` objects (B.5).
Today it is the same set for every type, profile and path, which is itself the
finding — one guard, and no output-side ceiling at all, so the only thing that
stops a runaway answer is the provider's own cut.

**E.2's move (the window's clamp) is the last block of rows.** Every row above it
runs with ``window=None``, which is why none of their numbers moved: the window is
the only limit allowed to LOWER a budget, and it only speaks when BOTH the driver's
window and the prompt's size are known. Three of the new rows clamp (the third on a
thinking driver, where physics outranks the 16000 floor: a driver that cannot hold
its floor is replaced, not exceeded) and one carries a window with no prompt — no
measurement, no clamp.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

import pytest
from pydantic import ValidationError

from app.api.v1.chat.tool_call_tracker import ToolCallTracker
from app.domain.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentTemplateCreate,
    AgentUpdate,
)
from app.domain.runtime_config.schemas import RuntimeConfigBase, RuntimeConfigCreate
from app.api.v1.agent_chat.router import _build_agent_descriptor
from app.services.cognitive_pipeline.executor import (
    FastExecutor,
    HybridExecutor,
    LiteLLMExecutor,
    budget_for,
)
from app.services.cognitive_pipeline.limits import TURN as TURN_SCOPE
from app.services.cognitive_pipeline.limits import (
    HARD,
    SOFT,
    call_soft_limits,
    hard_turn_limits,
    limits_in_force,
    turn_soft_limits,
)
from app.services.cognitive_pipeline.output_budget import (
    BUDGET_CEILING,
    DEEP_MIN_BUDGET,
    PATH_DEFAULT,
    EXECUTOR_PASS1_CAP,
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
    REASON_THINKING_FLOOR,
    REASON_WINDOW_CLAMP,
    THINKING_MULTIPLIER,
    TYPE_BUDGETS,
    TYPE_DEEP,
    TYPE_DEEP_LONG,
    TYPE_LESSER,
    TYPE_SHALLOW,
    floor_budget,
    resolve_output_budget,
    type_default_budget,
)
from app.services.cognitive_pipeline.reasoning_support import REASONING_MAX_TOKENS_FLOOR

# The models, verbatim from the database: Bob's, and a thinking driver
# (deepseek-v4, whose family is name-pattern detected — the declaration is not
# trustworthy until F.3).
BOB_MODEL = "openrouter/inclusionai/ling-3.0-flash"
THINKING_MODEL = "deepseek/deepseek-v4-flash"

# The chat-path types (study §1). Pseudo-agents, workflow nodes, the auxiliary
# callers and the external agent are a SEPARATE table — they are not chat turns
# and must not be folded in.
TYPES = ("trivial", "shallow", "deep")

# The executor profiles a cognitive profile can set, and the PATH each one runs
# a turn on. `hybrid` has two: pass 1, then the conduit's deep pass.
PROFILE_PATHS = {
    "default": (PATH_DEFAULT,),
    "fast": (PATH_FAST,),
    "hybrid": (PATH_PASS1, PATH_DEEP),
}

# THE DECLARATION IN FORCE, per row. F.4 raised Bob's row to his class's base by hand;
# F.2 made that base a TABLE the code holds, and `DECLARED_BOB` is still his bespoke
# declaration. `DECLARED_OTHERS` is a FIXTURE case now rather than a live row: the live
# rows read 16000 (Bob, thinking_floor) / 8192 (Wanda, type_default) / 16000 (Lois,
# declared) / 16000 (the export test agent, thinking_floor — see the header), and this
# value is what keeps the deep pass's minimum pinned as BEHAVIOUR below.
DECLARED_BOB = 8192      # agents.id=19, `{"max_tokens": 8192}` — the anchor
DECLARED_OTHERS = 2000   # a 2000 declaration, as its own case
UNDECLARED = None
# The deep class's base (roadmap §1) — now READ from the table (F.2) rather than
# typed beside it, and still not in force: the class rows land at F's Step 4.
LADDER_DEEP = type_default_budget(TYPE_DEEP)


@dataclass(frozen=True)
class Row:
    """One (type, profile, path) and the budget it sends today.

    ``window`` and ``prompt_tokens`` are E.2's clamp inputs — ``None`` on every row
    that existed before it, which is exactly why the clamp moved no old number (E
    is a CEILING over the constant, and the window only speaks when both numbers
    are known).
    """

    agent_type: str
    profile: str
    path: str
    declared: Optional[int]
    model: str
    budget: int
    reason: str
    note: str = ""
    window: Optional[int] = None
    prompt_tokens: Optional[int] = None

    @property
    def id(self) -> str:
        declared = "none" if self.declared is None else str(self.declared)
        model = "thinking" if self.model == THINKING_MODEL else "base"
        return f"{self.agent_type}-{self.profile}-{self.path}-{declared}-{model}"


# ── THE TABLE ───────────────────────────────────────────────────────────────
ROWS: tuple[Row, ...] = (
    # The ordinary turn: the declared value runs. The trivial/deep TYPE rows carry
    # the OTHER rows' declaration — the type decides nothing today, so they exist
    # to show that one declaration produces one number whatever the type.
    Row("trivial", "default", PATH_DEFAULT, DECLARED_OTHERS, BOB_MODEL, 2000, REASON_DECLARED),
    Row(
        "shallow", "default", PATH_DEFAULT, DECLARED_BOB, BOB_MODEL, 8192,
        REASON_DECLARED, note="Bob's own row (F.4) — his class's base, not 2000",
    ),
    Row("deep", "default", PATH_DEFAULT, DECLARED_OTHERS, BOB_MODEL, 2000, REASON_DECLARED),
    # The fast profile: the resolver's POLICY CONSTANT — named and logged (C.2),
    # no longer a silent `min(declared, 512)`. The declaration cannot change it,
    # which is why the rows keep their own rows' number.
    Row("trivial", "fast", PATH_FAST, DECLARED_OTHERS, BOB_MODEL, 512, REASON_FAST_POLICY),
    Row("shallow", "fast", PATH_FAST, DECLARED_BOB, BOB_MODEL, 512, REASON_FAST_POLICY),
    Row("deep", "fast", PATH_FAST, DECLARED_OTHERS, BOB_MODEL, 512, REASON_FAST_POLICY),
    # Hybrid pass 1 runs on the DECLARED budget (C.2) — the cap that quartered
    # the pass is gone, so the number is the agent's own.
    Row("trivial", "hybrid", PATH_PASS1, DECLARED_OTHERS, BOB_MODEL, 2000, REASON_DECLARED),
    Row("trivial", "hybrid", PATH_DEEP, DECLARED_OTHERS, BOB_MODEL, 4096, REASON_DEEP_MIN),
    # THE ANCHOR — Bob's production turn, pass 1 and the deep pass (F.4: 8192 on both).
    Row(
        "shallow", "hybrid", PATH_PASS1, DECLARED_BOB, BOB_MODEL, 8192,
        REASON_DECLARED, note="BOB, pass 1 (the anchor row) — the declaration, not 1024",
    ),
    Row(
        "shallow", "hybrid", PATH_DEEP, DECLARED_BOB, BOB_MODEL, 8192,
        REASON_DECLARED,
        note=(
            "BOB, the deep pass (the anchor row) — F.4's declaration sits ABOVE "
            "the pass's 4096 minimum, so it flows through instead of being flattened"
        ),
    ),
    # The same paths on the other two types: identical numbers for the same
    # declaration, because the type decides nothing today. F is where this stops
    # being true.
    Row("deep", "hybrid", PATH_PASS1, DECLARED_OTHERS, BOB_MODEL, 2000, REASON_DECLARED),
    Row("deep", "hybrid", PATH_DEEP, DECLARED_OTHERS, BOB_MODEL, 4096, REASON_DEEP_MIN),
    # An agent that declares nothing: the router's own 4096 — the fast policy
    # still speaks on the fast path; pass 1 has no policy of its own to add.
    Row("trivial", "default", PATH_DEFAULT, UNDECLARED, BOB_MODEL, 4096, REASON_NO_DECLARATION),
    Row("trivial", "fast", PATH_FAST, UNDECLARED, BOB_MODEL, 512, REASON_FAST_POLICY),
    Row("shallow", "hybrid", PATH_PASS1, UNDECLARED, BOB_MODEL, 4096, REASON_NO_DECLARATION),
    # A THINKING driver: the floor (16000) beats the fast policy and the deep
    # pass's minimum alike — the pass that used to drop BELOW the floor (C.3).
    Row("shallow", "default", PATH_DEFAULT, DECLARED_OTHERS, THINKING_MODEL, 16000, REASON_THINKING_FLOOR),
    Row("shallow", "fast", PATH_FAST, DECLARED_OTHERS, THINKING_MODEL, 16000, REASON_THINKING_FLOOR),
    Row("shallow", "hybrid", PATH_PASS1, DECLARED_OTHERS, THINKING_MODEL, 16000, REASON_THINKING_FLOOR),
    Row(
        "shallow", "hybrid", PATH_DEEP, DECLARED_OTHERS, THINKING_MODEL, 16000,
        REASON_THINKING_FLOOR, note="the floor, not 4096 — C.3's headline row",
    ),
    # THE DEEP CLASS'S BASE — still NOT in force (F.4's second half, banked). It
    # stays as the row that proves a declaration above the pass's minimum flows
    # through the deep pass untouched.
    Row("deep", "default", PATH_DEFAULT, LADDER_DEEP, BOB_MODEL, 16384, REASON_DECLARED),
    # ── E.2 — THE WINDOW'S CLAMP (the only limit allowed to LOWER a budget) ────
    # Physics, applied AFTER the path's policy and AFTER the floor. Until E.2 every
    # row above ran with `window=None`, which is why none of their numbers moved.
    Row(
        "shallow", "default", PATH_DEFAULT, DECLARED_BOB, BOB_MODEL, 5000,
        REASON_WINDOW_CLAMP, window=20000, prompt_tokens=15000,
        note="E.2: the declared 8192 cannot sit beside a 15000-token prompt in a 20000 window",
    ),
    Row(
        "shallow", "hybrid", PATH_DEEP, DECLARED_BOB, BOB_MODEL, 6000,
        REASON_WINDOW_CLAMP, window=16000, prompt_tokens=10000,
        note="E.2: the same clamp on the deep pass — physics speaks there too",
    ),
    Row(
        "deep", "default", PATH_DEFAULT, DECLARED_OTHERS, THINKING_MODEL, 8000,
        REASON_WINDOW_CLAMP, window=12000, prompt_tokens=4000,
        note=(
            "E.2: PHYSICS OUTRANKS THE FLOOR — a driver whose window cannot hold "
            "16000 is replaced (E.3 warns at match time), not exceeded"
        ),
    ),
    # A window with no prompt estimate is NO measurement, so nothing clamps (the
    # clamp needs both numbers) — the same rule that keeps an unrecorded driver
    # behaving as it does today.
    Row(
        "deep", "default", PATH_DEFAULT, DECLARED_BOB, BOB_MODEL, 8192,
        REASON_DECLARED, window=4096,
        note="E.2: a window alone is not a measurement — no prompt, no clamp",
    ),
)


def _agent(declared: Optional[int]) -> SimpleNamespace:
    """An agent row as the router hands it over: the declaration in its OWN spec.

    G-I: this used to be `parameters.max_tokens` (the slot the profile form also
    wrote); the spec is the one slot the resolver reads now.
    """
    spec: dict = {}
    if declared is not None:
        spec["max_output"] = declared
    return SimpleNamespace(
        id=19, name="Bob",
        parameters={"temperature": 0.7, "top_p": 0.9},
        llm_spec=spec,
    )


def _resolve(row: Row) -> tuple[int, str]:
    return resolve_output_budget(
        _agent(row.declared),
        row.model,
        path=row.path,
        window=row.window,
        prompt_tokens=row.prompt_tokens,
    )


@pytest.mark.parametrize("row", ROWS, ids=[row.id for row in ROWS])
def test_the_table_row_is_what_today_sends(row: Row):
    budget, reason = _resolve(row)
    assert (budget, reason) == (row.budget, row.reason), row.note or row.id


class TestBobsProductionTurn:
    """The anchor: one Bob turn, in order — 8192 declared, 8192 on pass 1, 8192 on the deep pass."""

    def test_the_turn_runs_at_the_numbers_the_roadmap_names(self):
        agent = _agent(DECLARED_BOB)
        pass_1 = resolve_output_budget(agent, BOB_MODEL, path=PATH_PASS1)
        deep = resolve_output_budget(agent, BOB_MODEL, path=PATH_DEEP)
        assert (pass_1[0], deep[0]) == (8192, 8192)
        # F.4's move is visible in the REASON too: the deep pass is no longer
        # speaking through its own 4096 minimum — the declaration is.
        assert (pass_1[1], deep[1]) == (REASON_DECLARED, REASON_DECLARED)

    def test_the_declared_number_is_the_one_the_agent_stores(self):
        assert resolve_output_budget(_agent(DECLARED_BOB), BOB_MODEL, path=PATH_DEFAULT)[0] == 8192

    def test_bob_is_not_a_thinking_driver(self):
        """The floor must NOT be what produces the anchor numbers."""
        assert resolve_output_budget(_agent(DECLARED_BOB), BOB_MODEL, path=PATH_PASS1)[0] != 16000


class TestTheTableIsComplete:
    """Every (type, profile, path) is represented — a gap is a silent path."""

    def test_every_type_profile_path_appears(self):
        covered = {(row.agent_type, row.profile, row.path) for row in ROWS}
        for agent_type in TYPES:
            for profile, paths in PROFILE_PATHS.items():
                for path in paths:
                    assert (agent_type, profile, path) in covered, (
                        f"{agent_type}/{profile}/{path} has no row — the table "
                        f"would not notice that path moving"
                    )

    def test_the_undeclared_state_is_covered_on_the_paths_that_still_decide(self):
        """The default, fast and pass-1 paths all decide a number even with no
        declaration — the fast policy and the fallback both have to be visible."""
        covered = {(row.profile, row.path) for row in ROWS if row.declared is None}
        assert covered == {("default", PATH_DEFAULT), ("fast", PATH_FAST), ("hybrid", PATH_PASS1)}

    def test_the_thinking_driver_covers_both_caps_and_the_deep_pass(self):
        covered = {row.path for row in ROWS if row.model == THINKING_MODEL}
        assert covered == {PATH_DEFAULT, PATH_FAST, PATH_PASS1, PATH_DEEP}


class TestWhatTheTypeDoesNotDecide:
    """Today the type changes nothing about the sent budget — F is where it starts to."""

    def test_no_row_disagrees_with_another_of_the_same_path(self):
        """Same profile + path + declaration ⇒ same number, whatever the type.

        **Clamped rows are excluded on purpose** (E.2): they carry a window and a
        prompt size, so their number is decided by the DRIVER, not by the type —
        the type deciding nothing is a claim about policy, and physics is not
        policy.
        """
        by_path: dict[tuple[int, str, str], set[int]] = {}
        for row in ROWS:
            if row.declared is None or row.model != BOB_MODEL or row.window is not None:
                continue
            key = (row.declared, row.profile, row.path)
            by_path.setdefault(key, set()).add(row.budget)
        # Every declaration the table represents must have more than one TYPE on
        # a path, or the claim is untested. F.4 put TWO declarations in force
        # (Bob's 8192 and the other rows' 2000), so both must appear.
        assert {DECLARED_BOB, DECLARED_OTHERS} <= {declared for declared, _, _ in by_path}
        for key, budgets in by_path.items():
            assert len(budgets) == 1, f"{key} differs by type: {budgets}"

    def test_the_type_is_not_a_resolver_ARGUMENT(self):
        """F.1 reads the type default off the AGENT's own `llm_spec`, not a parameter.

        The resolver's shape is unchanged on purpose: the package's default arrives as
        a field of the thing being resolved, so there is still no (type, profile, path)
        key to keep in step.
        """
        import inspect

        names = set(inspect.signature(resolve_output_budget).parameters)
        assert not names & {"agent_type", "class", "kind", "type", "package"}

    def test_raising_the_declaration_now_reaches_bob(self):
        """THE PREMISE OF THIS TEST WAS REVERSED ON PURPOSE AT C.2/C.3.

        It used to assert that raising the stored budget alone changed nothing
        (`pass 1 == 1024`, `deep == 4096`) — the finding that made C the gate in
        front of F.4. A raised declaration now reaches BOTH passes, which is what
        F.4's 8192 needs to mean anything.
        """
        agent = _agent(8192)
        assert resolve_output_budget(agent, BOB_MODEL, path=PATH_PASS1) == (8192, REASON_DECLARED)
        assert resolve_output_budget(agent, BOB_MODEL, path=PATH_DEEP) == (8192, REASON_DECLARED)



class TestTheTypeTableAndTheDerivedCeiling:
    """F.2 — the ladder as constants, and ONE ceiling derived from it (D3).

    The type table is the source F.1's packages declare and F.4's rows raise to, and
    the ceiling is not typed anywhere: it is what the table can PRODUCE, so a class
    budget that moves moves the ceiling with it and this test names the row that did.
    """

    def test_the_classes_are_the_ladder_the_roadmap_seeded(self):
        assert TYPE_BUDGETS == {
            TYPE_LESSER: 4096,
            TYPE_SHALLOW: 8192,
            TYPE_DEEP: 16384,
            TYPE_DEEP_LONG: 24576,
        }, "the ladder moved — every class default reads this table"

    def test_every_class_default_is_a_sendable_number(self):
        for agent_type, budget in TYPE_BUDGETS.items():
            assert budget >= 1, f"{agent_type} would send {budget} tokens"
            assert budget <= BUDGET_CEILING, f"{agent_type} sits above the ceiling"

    def test_a_thinking_default_is_doubled_and_a_plain_one_is_not(self):
        assert THINKING_MULTIPLIER == 2
        assert type_default_budget(TYPE_SHALLOW) == 8192
        assert type_default_budget(TYPE_SHALLOW, thinking=True) == 16384

    def test_the_ceiling_is_derived_from_the_table_and_covers_what_it_produces(self):
        assert BUDGET_CEILING == max(TYPE_BUDGETS.values()) * THINKING_MULTIPLIER == 49152
        # A bound the table can legitimately produce above is not a bound (F-C).
        assert BUDGET_CEILING >= type_default_budget(TYPE_DEEP_LONG, thinking=True)

    def test_an_unknown_class_is_refused_rather_than_defaulted(self):
        with pytest.raises(ValueError, match="unknown agent type"):
            type_default_budget("research-ish")


class TestTheLimitsArmedToday:
    """The table's second half: what is ARMED, per path, today.

    **THE PREMISE OF THIS CLASS WAS REVERSED TWICE, ON PURPOSE.** B.5 could say
    "the only armed limits are the tool guards" and "no output limit exists"; D.2
    armed the turn's soft lines, and D.3 armed the turn's two HARD plugs, so both
    of those statements are false BY DESIGN. What replaces them is a census
    rather than less coverage: the guard's three, the turn's three softs, and the
    turn's two hard plugs. The OUTPUT side still has no hard stop of its own —
    the provider's own cut is that stop, reported as `truncated=True`.
    """

    def test_the_armed_set_is_the_guards_lines_the_turns_softs_and_the_two_plugs(self):
        guard = ToolCallTracker().limits_for("file_info", consecutive=0)
        armed = tuple(guard) + turn_soft_limits() + hard_turn_limits()

        assert limits_in_force(armed) == (
            "limits: tool_calls(hard turn 30), consecutive_tool_calls(soft turn 3), "
            "consecutive_tool_calls(hard turn 4), provider_calls(soft turn 8), "
            "tool_calls(soft turn 20), wall_clock_s(soft turn 300), "
            "provider_calls(hard turn 12), wall_clock_s(hard turn 600)"
        )

    def test_the_output_limit_is_a_soft_fraction_and_never_a_hard_stop(self):
        """90 % hears the cut coming; the HARD stop remains the provider's.

        D.3's two plugs are the TURN's (`provider_calls`, `wall_clock_s`) and do
        not touch this row: the output budget's only hard stop is still the cut
        the provider makes at `max_tokens`.
        """
        armed = call_soft_limits(2000)

        assert [(limit.key, limit.kind, limit.threshold) for limit in armed] == [
            ("output_tokens", SOFT, 1800)
        ]
        assert [limit for limit in armed if limit.kind == HARD] == []
        assert "output_tokens" not in {limit.key for limit in hard_turn_limits()}

    def test_the_turn_scoped_limits_do_not_vary_by_type_profile_or_path(self):
        """The turn's own lines take no type/profile/path — the PER-TYPE budgets
        are F.2's, and this row moves the day they arrive."""
        assert turn_soft_limits() == turn_soft_limits()
        assert set(inspect.signature(turn_soft_limits).parameters) == set()

    def test_the_output_soft_varies_with_the_budget_the_path_runs_under(self):
        """A call's soft is 90 % of ITS budget: 460 / 1800 / 3686 by path."""
        assert {
            "fast": call_soft_limits(512)[0].threshold,
            "pass1": call_soft_limits(2000)[0].threshold,
            "deep": call_soft_limits(4096)[0].threshold,
        } == {"fast": 460, "pass1": 1800, "deep": 3686}

    def test_the_guard_is_turn_scoped(self):
        """Its ceilings count the whole turn — both executor passes included."""
        scopes = {limit.scope for limit in ToolCallTracker().limits_for("file_info", 0)}
        assert scopes == {TURN_SCOPE}


class TestTheCeilingBoundsEverySurface:
    """F.2/D3 — ONE derived ceiling, shared by the API validation and the resolver.

    D3's purpose is a typo guard: `200000` must not reach a provider, and no surface
    carries its own copy of the bound. The ceiling is
    ``BUDGET_CEILING = max(TYPE_BUDGETS.values()) * THINKING_MULTIPLIER``; every other
    surface has to AGREE with that number, which is what these assertions check.
    """

    def test_the_runtime_override_is_bounded_by_the_derived_ceiling(self):
        field = RuntimeConfigBase.model_fields["max_tokens"]
        bounds = [m.le for m in field.metadata if hasattr(m, "le")]
        assert bounds == [BUDGET_CEILING], (
            "the runtime override carries its own ceiling — it must be the derived one"
        )

    # REMOVED (G-I, 2026-09-25): `test_the_versioned_agent_config_is_bounded_too`.
    # It asserted the ceiling on the workflow agent-versioning registry's `max_tokens`
    # — a field nothing read (no executor, no resolver, no export consumer) and that
    # carried the silent 2000 default. The field is gone, so its bound is too.

    def test_an_agent_may_be_created_AT_the_ceiling_and_not_above_it(self):
        def build(budget):
            return AgentCreate(
                name="ceiling probe",
                provider="openrouter",
                model=BOB_MODEL,
                llm_spec={"max_output": budget},
            )

        assert (build(BUDGET_CEILING).llm_spec or {})["max_output"] == BUDGET_CEILING
        with pytest.raises(ValidationError, match="above the budget ceiling"):
            build(BUDGET_CEILING + 1)

    def test_an_agent_update_is_bounded_the_same_way(self):
        assert AgentUpdate(llm_spec={"max_output": BUDGET_CEILING}).llm_spec
        with pytest.raises(ValidationError, match="above the budget ceiling"):
            AgentUpdate(llm_spec={"max_output": BUDGET_CEILING + 1})

    def test_the_retired_budget_key_is_refused_loudly(self, caplog):
        """G-I: `parameters.max_tokens` is not ignored — a writer that still sends it
        fails AND the refusal is written to the log (a guard nobody reads is a guard
        that lets the shape back in)."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError, match="unknown model parameter key"):
                AgentUpdate(parameters={"temperature": 0.7, "max_tokens": 2000})
            with pytest.raises(ValidationError, match="unknown model parameter key"):
                AgentCreate(
                    name="stale writer", provider="openrouter", model=BOB_MODEL,
                    parameters={"temperature": 0.7, "max_tokens": 2000},
                )
        refusals = [r.getMessage() for r in caplog.records if "REFUSED model parameters" in r.getMessage()]
        assert len(refusals) == 2, f"the refusal was not logged: {refusals}"
        assert "max_tokens" in refusals[0], "the log line does not name the offending key"

    def test_any_unknown_parameter_key_is_refused_and_named(self, caplog):
        """The shape's own point: the NEXT stray needs no new rule here."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError, match="frequency_penalty"):
                AgentUpdate(parameters={"temperature": 0.7, "frequency_penalty": 0.2})
        assert any(
            "frequency_penalty" in r.getMessage() and r.levelno == logging.ERROR
            for r in caplog.records
        ), "an unknown key was refused without a logged error naming it"

    def test_the_two_sampling_settings_are_accepted(self):
        """The guard is about the SHAPE, not about refusing edits."""
        assert AgentUpdate(parameters={"temperature": 0.3, "top_p": 0.95}).parameters == {
            "temperature": 0.3, "top_p": 0.95,
        }

    @pytest.mark.anyio
    async def test_the_orm_column_declares_nothing_either(self, test_session):
        """The API refuses what nothing reads; the COLUMN DEFAULT is the way around it.

        An ORM insert never meets a request schema — the same shape that let a seeded
        template re-create a retired key in a brand-new agent. A value in this default
        therefore rides every new agent row, and a SAMPLING value is no different from a
        retired key: it is a setting nobody chose, made operative for the life of the
        row. An ORM-created agent stores nothing, the turn sends no sampling setting,
        and the provider's own default applies.
        """
        from app.infrastructure.database.models import Agent as AgentModel

        fresh = AgentModel(
            name="Default Parameters Agent",
            provider="ollama",
            model="llama3.2:latest",
            is_active=True,
        )
        test_session.add(fresh)
        await test_session.commit()
        await test_session.refresh(fresh)

        assert fresh.parameters is None, (
            "the agent column writes a sampling pair no one chose — every ORM-created "
            "agent carries it, including the ones no request schema ever saw"
        )

    def test_a_template_refuses_a_budget_and_an_override_is_still_bounded(self):
        """G-I: a template has no spec column, so it cannot declare a budget — an
        unknown key is refused rather than silently dropped. The SESSION override keeps
        its own bound: it is a session's choice, not the agent's declaration."""
        with pytest.raises(ValidationError, match="unknown model parameter key"):
            AgentTemplateCreate(
                name="t", description="d", provider="openrouter", model=BOB_MODEL,
                parameters={"max_tokens": BUDGET_CEILING},
            )
        with pytest.raises(ValidationError):
            RuntimeConfigCreate(
                session_id=1, agent_id=19, max_tokens=BUDGET_CEILING + 1
            )

    def test_a_row_with_an_unknown_key_is_refused_at_the_copy(self, caplog):
        """The internal copy path (template→agent) writes the JSON column directly:
        it validates the row it is copying, so a legacy key cannot ride forward."""
        from app.domain.agents.schemas import checked_parameters

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="max_tokens"):
                checked_parameters({"temperature": 0.7, "max_tokens": 2000})
        assert checked_parameters({"temperature": 0.7, "top_p": 0.9}) == {
            "temperature": 0.7, "top_p": 0.9,
        }

    def test_a_stored_row_above_the_ceiling_is_still_readable(self):
        """The ceiling bounds REQUESTS — a legacy row must not fail on read."""
        row = AgentResponse(
            id=1, name="legacy", provider="openrouter", model=BOB_MODEL,
            parameters={"max_tokens": BUDGET_CEILING * 4},
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        assert row.parameters["max_tokens"] == BUDGET_CEILING * 4

    def test_a_budget_below_one_is_refused_too(self):
        with pytest.raises(ValidationError, match="not a sendable budget"):
            AgentUpdate(llm_spec={"max_output": 0})

    def test_an_unreadable_budget_is_left_to_the_resolver(self):
        """Not a number IS "undeclared" — the resolver's rule, not a schema's."""
        assert AgentUpdate(llm_spec={"max_output": "plenty"}).llm_spec == {
            "max_output": "plenty"
        }


class TestTheExecutorUsesTheSharedNumbers:
    """F-B — the registry path's numbers come from the table, not from literals.

    These are the DEFAULTS: what an executor runs under when nobody resolved a budget
    for it. Since G-F that is no longer how `/agent-chat` decides — its descriptor
    carries the resolver's answer, and `budget_for` gives that answer precedence — so
    the defaults here are the fallback for a caller with no reading to give, and the
    one named divergence (the fast policy) is still declared in the resolver.
    """

    def test_the_constructors_default_to_the_shared_constants(self):
        assert LiteLLMExecutor().max_tokens == FALLBACK_BUDGET
        assert FastExecutor().max_tokens == FAST_POLICY_BUDGET
        hybrid = HybridExecutor()
        assert hybrid.fast_max_tokens == EXECUTOR_PASS1_CAP
        assert hybrid.deep_max_tokens == DEEP_MIN_BUDGET

    def test_the_pass_one_cap_is_declared_in_the_resolver(self):
        assert EXECUTOR_PASS1_CAP == 1024, (
            "the named divergence moved — it is the value C.2 removed from the chat "
            "path and the value the executor path still runs under"
        )


class TestTheDescriptorDecidesTheBudget:
    """G-F — `/agent-chat` runs the resolver's number, not the executor's default.

    The default is the fallback, never the decision: a descriptor that carries a
    reading uses it, and a descriptor that carries none behaves exactly as it did
    before this phase.
    """

    def test_the_readings_number_beats_the_executors_default(self):
        assert budget_for(SimpleNamespace(output_budget=16000), 2000) == 16000
        assert budget_for(SimpleNamespace(output_budget=16000), 2000) != 2000

    def test_no_reading_leaves_the_executor_default_in_place(self):
        assert budget_for(SimpleNamespace(output_budget=None), 2000) == 2000
        assert budget_for(SimpleNamespace(), FAST_POLICY_BUDGET) == FAST_POLICY_BUDGET

    def test_the_deep_pass_floor_outranks_a_low_reading(self):
        """C.3: a pass meant to reason does not run below the deep floor, whichever
        number arrived — the floor is a floor, not a suggestion."""
        assert budget_for(
            SimpleNamespace(output_budget=512), DEEP_MIN_BUDGET, minimum=DEEP_MIN_BUDGET
        ) == DEEP_MIN_BUDGET
        assert budget_for(
            SimpleNamespace(output_budget=16000), DEEP_MIN_BUDGET, minimum=DEEP_MIN_BUDGET
        ) == 16000

    def test_the_agent_chat_descriptor_asks_the_resolver(self):
        """The builder resolves through the SAME function, so the two paths cannot
        drift apart — and the resolution is logged with the shared line."""
        source = inspect.getsource(_build_agent_descriptor)
        assert "resolve_output_budget" in source
        assert "output_budget=budget" in source, "the reading never reaches the descriptor"
        assert "log_effective_budget" in source, (
            "a path that decides a budget without logging it is the defect G-F closes"
        )

    @pytest.mark.anyio
    async def test_a_descriptor_with_no_session_has_no_reading(self, test_session):
        """Called without a session (or when the read raises), the field stays None and
        the executor default speaks — the pre-G-F behaviour, kept for callers that
        cannot read."""
        from app.infrastructure.database.models import Agent as AgentModel

        plain = AgentModel(
            name="Plain Driver Agent", provider="openrouter", model="nvidia/nemotron-3",
            is_active=True, llm_spec={"kind": "chat", "max_output": 1234},
        )
        thinking = AgentModel(
            name="Thinking Driver Agent", provider="openrouter", model="deepseek-v4-flash",
            is_active=True, llm_spec={"kind": "chat", "max_output": 1234},
        )
        test_session.add_all([plain, thinking])
        await test_session.commit()
        await test_session.refresh(plain)
        await test_session.refresh(thinking)

        bare = await _build_agent_descriptor(plain, None)
        assert bare.output_budget is None, "no session, no reading — the executor default decides"

        resolved = await _build_agent_descriptor(plain, None, test_session)
        assert resolved.output_budget == 1234, (
            "the declared number is what this path sends when nothing else speaks"
        )

        # ...and on a thinking driver the resolver's own layering still decides: the
        # floor outranks a declaration below it. The path runs the resolver, not a
        # shortcut to the declaration.
        floored = await _build_agent_descriptor(thinking, None, test_session)
        assert floored.output_budget == resolve_output_budget(
            thinking, "openrouter/deepseek-v4-flash", None, PATH_DEFAULT
        )[0] == REASONING_MAX_TOKENS_FLOOR, (
            "the descriptor's number diverged from the resolver's answer"
        )


class TestTheFloorHasOneApplication:
    """F-B — the thinking floor is applied in ONE place (`floor_budget`).

    The assertions moved here from `test_reasoning_support.py` when F.2 retired the
    separate floor helper: the detection stayed in `reasoning_support`, the
    application moved to the resolver, and the executor path calls the same function.
    """

    def test_the_floor_applies_to_the_known_thinking_families(self):
        assert floor_budget("deepseek/deepseek-r1", 2000) == REASONING_MAX_TOKENS_FLOOR
        assert floor_budget("deepseek/deepseek-v4-flash", 512) == REASONING_MAX_TOKENS_FLOOR

    def test_a_plain_family_passes_through_and_a_large_budget_stays(self):
        assert floor_budget("openrouter/nvidia/nemotron-3", 512) == 512
        assert floor_budget("deepseek/deepseek-v4-flash", 20000) == 20000

    def test_the_declaration_is_the_second_trigger(self):
        """F.3's hook: a DECLARED thinking driver floors when the name says nothing."""
        stealth = "openrouter/stealth/space-bunny-alpha"
        assert floor_budget(stealth, 512, thinking=True) == REASONING_MAX_TOKENS_FLOOR
        assert floor_budget(stealth, 512) == 512

    def test_the_resolver_and_the_executor_path_agree(self):
        """Same rule, two callers — the number cannot drift between the surfaces."""
        budget, reason = resolve_output_budget(
            {"parameters": {"max_tokens": 2000}},
            "deepseek/deepseek-v4-flash",
            None,
            PATH_DEFAULT,
        )
        assert reason == REASON_THINKING_FLOOR
        assert budget == floor_budget("deepseek/deepseek-v4-flash", 2000)
