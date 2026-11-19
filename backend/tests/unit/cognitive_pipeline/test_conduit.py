"""The conduit router's rules — which signals route shallow, hybrid or deep."""

import pytest
from app.services.cognitive_pipeline.conduit import (
    conduit_route,
    Route,
    ConduitDecision,
    get_delegate_agent_id,
    list_delegate_names,
    DELEGATION_TARGETS,
)


class TestConduitRoute:
    """Decision logic for conduit routing."""

    def test_delegate_keyword_returns_shallow(self):
        """Auto-delegation is disabled — all queries return SHALLOW."""
        decision = conduit_route(
            message="Research the impact of AI on healthcare",
            executor_strategy="standard",
            accumulated_content="",
            tools_were_used=False,
        )
        assert decision.route == Route.SHALLOW

    def test_delegate_investigate_keyword(self):
        """Auto-delegation is disabled — investigate triggers HYBRID (short content + hybrid strategy)."""
        decision = conduit_route(
            message="Investigate the latest climate data",
            executor_strategy="hybrid",
            accumulated_content="Some response",
            tools_were_used=False,
        )
        assert decision.route == Route.HYBRID

    def test_hybrid_tool_usage(self):
        """Short response + tools used still triggers HYBRID (content short)."""
        decision = conduit_route(
            message="What is the weather?",
            executor_strategy="hybrid",
            accumulated_content="Short response",
            tools_were_used=True,
        )
        assert decision.route == Route.HYBRID

    def test_tools_alone_does_not_trigger_hybrid(self):
        """THE DOUBLE-GLITCH DISCRIMINATOR (2026-09-02): tools used with
        a FULL first-pass report must NOT route HYBRID — the streaming
        tool loop already synthesized the complete answer, and the deep
        pass would re-answer it (two full reports glued into one bubble,
        Bob's session). Only short content or deep keywords qualify."""
        decision = conduit_route(
            message="Let's check the alternative news sites headlines.",
            executor_strategy="hybrid",
            accumulated_content=(
                "Here's what's on the boards this morning. The clear story "
                "everywhere: the US-Iran war is dominating the alternative "
                "press. Antiwar.com reports US launched airstrikes across "
                "Iran's coast and Iran hit back at US bases in the region. "
                "Democracy Now! leads with the wave of attacks killing 11 "
                "people, plus the whistleblower warning about the USPS "
                "mail-voting system before the midterms. Drudge covers the "
                "logistics nightmare facing US warships and the record 89% "
                "saying government corruption is widespread. "
                + ("This is a long, complete first-pass report that exceeds "
                   "the five-hundred-character threshold so the short-content "
                   "trigger cannot fire — the only possible HYBRID trigger "
                   "here would be the tools flag, which must NOT fire "
                   "because the tool loop already synthesized this full "
                   "answer." * 2)
            ),
            tools_were_used=True,
        )
        assert decision.route == Route.SHALLOW

    def test_hybrid_short_response(self):
        """Short response triggers HYBRID."""
        decision = conduit_route(
            message="Hello",
            executor_strategy="hybrid",
            accumulated_content="Hi",
            tools_were_used=False,
        )
        assert decision.route == Route.HYBRID

    def test_hybrid_keywords(self):
        """Analysis keywords without delegate words trigger HYBRID."""
        decision = conduit_route(
            message="Compare Python and JavaScript",
            executor_strategy="hybrid",
            accumulated_content="Some comparison",
            tools_were_used=False,
        )
        assert decision.route == Route.HYBRID

    def test_shallow_default(self):
        """No triggers means SHALLOW."""
        decision = conduit_route(
            message="Good morning",
            executor_strategy="standard",
            accumulated_content="",
            tools_were_used=False,
        )
        assert decision.route == Route.SHALLOW

    def test_shallow_non_hybrid_with_content(self):
        """Even with content, non-hybrid strategy goes SHALLOW."""
        decision = conduit_route(
            message="Hello there",
            executor_strategy="standard",
            accumulated_content="Some response",
            tools_were_used=True,
        )
        assert decision.route == Route.SHALLOW


class TestDelegationTargets:
    """Delegate target registry."""

    def test_researcher_registered(self):
        assert get_delegate_agent_id("researcher") == 45

    def test_case_insensitive(self):
        assert get_delegate_agent_id("Researcher") == 45

    def test_unknown_returns_none(self):
        assert get_delegate_agent_id("nonexistent") is None

    def test_list_names(self):
        names = list_delegate_names()
        assert "researcher" in names
        assert isinstance(names, list)
