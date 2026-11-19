"""The agent read says what a row DECLARES and what a turn would SEND.

The profile page's job is two numbers side by side plus the reason they differ. The
temptation is a second arithmetic over `parameters.max_tokens` in the UI — which is
how the arc's original defect looked. So this read calls the SAME resolver the chat
path calls at send time (`output_budget.resolve_output_budget`) with the same driver
facts the router feeds it, and the tests here pin the four shapes the live database
actually produces, measured at the G kickoff:

  Bob    8192 declared + a thinking driver   -> 16000  thinking_floor
  Wanda  nothing on the row, class 8192      ->  8192  type_default
  Lois   16000 declared, no signal in hand   -> 16000  declared
  Export 2000 declared + a thinking driver   -> 16000  thinking_floor

The batching is the other half: a page listing four agents on two drivers must cost
two window reads, not four — `health_for_agents` is batched the same way.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agents.schemas import AgentResponse
from app.domain.agents.services import AgentService
from app.domain.providers import model_window
from app.services.cognitive_pipeline.output_budget import BUDGET_CEILING
from app.services.cognitive_pipeline.reasoning_support import (
    SOURCE_PROVIDER_CLAIM,
    signal_from_level,
)

BOB = ("openrouter", "inclusionai/ling-3.0-flash")
ZERO_DECLARED = 2000
WINDOW = 131072


def _agent(
    agent_id: int = 19,
    name: str = "Bob",
    driver: tuple = BOB,
    declared: int | None = 8192,
    spec: dict | None = None,
) -> SimpleNamespace:
    """A row shaped like the ORM one the resolver reads, without a session.

    G-I: the declaration lives in the agent's OWN `llm_spec.max_output`, so a
    `declared` here means the SPEC carries it — one slot, and the resolver reads it.
    """
    llm_spec: dict = dict(spec or {})
    if declared is not None:
        llm_spec["max_output"] = declared
    return SimpleNamespace(
        id=agent_id,
        name=name,
        provider=driver[0],
        model=driver[1],
        parameters={"temperature": 0.7, "top_p": 0.9},
        llm_spec=llm_spec,
    )


@pytest.fixture
def reads(monkeypatch):
    """Count the driver reads and script each driver's (window, thinking) pair."""
    calls: dict = {"window": [], "thinking": []}
    scripted: dict = {}

    async def fake_window(db, provider, model):
        calls["window"].append((provider, model))
        return SimpleNamespace(value=scripted.get((provider, model), (WINDOW, None))[0])

    async def fake_thinking(db, provider, model):
        calls["thinking"].append((provider, model))
        return scripted.get((provider, model), (WINDOW, None))[1]

    # the service imports these inside the method, from this module — so patching
    # the module attribute is what the call site resolves.
    monkeypatch.setattr(model_window, "resolve_model_window", fake_window)
    monkeypatch.setattr(model_window, "resolve_model_thinking", fake_thinking)
    return calls, scripted


def _service() -> AgentService:
    # The two driver readers are patched, so nothing ever touches the session —
    # the cast says that is deliberate rather than an oversight.
    return AgentService(db=cast(AsyncSession, None))


class TestTheReadAnswersWithTheResolversNumber:
    async def test_a_declared_8192_on_a_thinking_driver_sends_16000(self, reads):
        """Bob's live row: the pair the page exists to show."""
        _, scripted = reads
        scripted[BOB] = (WINDOW, signal_from_level("high", SOURCE_PROVIDER_CLAIM))

        read = (await _service().output_budget_for_agents([_agent()]))[19]

        assert read.declared == 8192
        assert read.effective == 16000
        assert read.reason == "thinking_floor"
        assert read.path == "default"

    async def test_a_mandatory_driver_says_mandatory(self, reads):
        """The distinction F.3 made: a claim that CANNOT be turned off is its own word."""
        _, scripted = reads
        scripted[BOB] = (WINDOW, signal_from_level("mandatory", SOURCE_PROVIDER_CLAIM))

        read = (await _service().output_budget_for_agents([_agent()]))[19]

        assert read.effective == 16000
        assert read.reason == "thinking_mandatory"

    async def test_a_class_default_in_the_spec_reads_as_the_declaration(self, reads):
        """Wanda's live row: the class number rides her OWN spec, so it IS her
        declaration. G-I retired the layer that read the same field as a separate
        "type default" while another field outranked it."""
        read = (
            await _service().output_budget_for_agents(
                [
                    _agent(
                        agent_id=54,
                        name="Wanda",
                        driver=("ollama", "codellama:latest"),
                        declared=None,
                        spec={"kind": "chat", "max_output": 8192, "thinking": "none"},
                    )
                ]
            )
        )[54]

        assert read.declared == 8192
        assert read.effective == 8192
        assert read.reason == "declared"

    async def test_a_declared_number_no_driver_floors_goes_out_as_itself(self, reads):
        """Lois's live row: 16000 declared, and 16000 sent."""
        read = (
            await _service().output_budget_for_agents(
                [_agent(agent_id=56, name="Lois", declared=16000)]
            )
        )[56]

        assert read.declared == 16000
        assert read.effective == 16000
        assert read.reason == "declared"

    async def test_a_small_declaration_on_a_thinking_driver_is_floored(self, reads):
        """The fixture row: 2000 typed, 16000 sent — the page's most surprising pair."""
        _, scripted = reads
        scripted[BOB] = (WINDOW, signal_from_level("high", SOURCE_PROVIDER_CLAIM))

        read = (
            await _service().output_budget_for_agents(
                [_agent(agent_id=57, name="Export Test Agent", declared=ZERO_DECLARED)]
            )
        )[57]

        assert read.declared == ZERO_DECLARED
        assert read.effective == 16000
        assert read.reason == "thinking_floor"

    async def test_nothing_declared_anywhere_still_has_a_number_and_a_reason(self, reads):
        """The honest state for a row with no budget: the fallback, NAMED as one."""
        read = (
            await _service().output_budget_for_agents(
                [_agent(agent_id=99, declared=None, spec=None)]
            )
        )[99]

        assert read.declared is None
        assert read.effective == 4096
        assert read.reason == "no_declared_budget"


class TestTheReadIsBatched:
    async def test_two_agents_on_one_driver_cost_one_read_each(self, reads):
        calls, _ = reads

        out = await _service().output_budget_for_agents(
            [_agent(agent_id=19), _agent(agent_id=99, name="Twin")]
        )

        assert set(out) == {19, 99}
        assert calls["window"] == [BOB], "one window read for a shared driver"
        assert calls["thinking"] == [BOB], "one thinking read for a shared driver"

    async def test_two_drivers_cost_one_read_each(self, reads):
        calls, _ = reads

        await _service().output_budget_for_agents(
            [_agent(agent_id=19), _agent(agent_id=54, driver=("ollama", "codellama:latest"))]
        )

        assert calls["window"] == [BOB, ("ollama", "codellama:latest")]


class TestNothingToReadIsNotAZero:
    async def test_an_empty_list_returns_no_entries(self, reads):
        calls, _ = reads

        assert await _service().output_budget_for_agents([]) == {}
        assert calls["window"] == [] and calls["thinking"] == []

    async def test_a_none_agent_is_skipped_rather_than_crashing(self, reads):
        reads  # nothing scripted: the driver reads must not even run

        assert await _service().output_budget_for_agents([None]) == {}


class TestTheCeilingIsServedWithTheRead:
    def test_the_response_carries_the_derived_ceiling(self):
        """D3's one constant, readable by the UI bound (the G.1 remainder)."""
        assert AgentResponse.model_fields["budget_ceiling"].default == BUDGET_CEILING
        assert BUDGET_CEILING == 49152, (
            "the ceiling is max(TYPE_BUDGETS) * THINKING_MULTIPLIER — a deeper class "
            "or a higher multiplier must move this number, and this test with it"
        )


@pytest.mark.anyio
async def test_the_observation_is_the_agents_last_turn(test_session):
    """G-A ii read back: the NEWEST message wins, and a last turn with no record
    leaves NO observation — falling through to an older one would label a stale
    number "last turn carried"."""
    from app.infrastructure.database.models import Agent, ChatMessage, ChatSession

    agent = Agent(
        name="Observation Agent", provider="openrouter", model="deepseek-v4-flash",
        is_active=True,
    )
    quiet = Agent(
        name="Silent Agent", provider="openrouter", model="deepseek-v4-flash",
        is_active=True,
    )
    test_session.add_all([agent, quiet])
    await test_session.commit()
    await test_session.refresh(agent)
    await test_session.refresh(quiet)

    talking = ChatSession(agent_id=agent.id, title="the one that ran")
    silent = ChatSession(agent_id=quiet.id, title="the one that did not")
    test_session.add_all([talking, silent])
    await test_session.commit()
    await test_session.refresh(talking)
    await test_session.refresh(silent)

    test_session.add_all([
        ChatMessage(
            session_id=talking.id, role="assistant", content="older",
            meta={"budget": {"sent": 8000, "declared": 8000, "reason": "declared", "path": "pass1"}},
        ),
        ChatMessage(
            session_id=talking.id, role="assistant", content="newer",
            meta={"budget": {"sent": 16000, "declared": 8000, "reason": "thinking_floor", "path": "deep"}},
        ),
        ChatMessage(session_id=silent.id, role="assistant", content="no record", meta={"reasoning": ""}),
    ])
    await test_session.commit()

    service = AgentService(db=test_session)
    observed = await service._observed_budgets([agent.id, quiet.id])

    assert observed[agent.id].sent == 16000, "an OLDER turn's number came back as the last"
    assert observed[agent.id].reason == "thinking_floor"
    assert observed[agent.id].at is not None, "a reading with no date pretends to be current"
    assert quiet.id not in observed, "a last turn with no record must leave no reading"

    # ...and a NEWER turn that recorded nothing CLEARS it rather than falling back
    test_session.add(ChatMessage(
        session_id=talking.id, role="assistant", content="newest, no budget", meta={"reasoning": ""},
    ))
    await test_session.commit()

    assert agent.id not in await service._observed_budgets([agent.id]), (
        "the read fell through to an older message — a stale number labelled 'last turn'"
    )
