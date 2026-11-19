"""The reasoning-model support — the budget floor.

The ox-alpha incident showed a 512-token budget eaten by the thinking phase ->
empty reply; the helpers prevent it generically (name-pattern detection, not a
curated list — the families change, the failure modes don't).
"""
import pytest

from app.services.cognitive_pipeline.reasoning_support import (
    SOURCE_CURATED,
    SOURCE_DECLARATION,
    SOURCE_PROVIDER_CLAIM,
    ThinkingSignal,
    as_signal,
    extract_response_text,
    is_reasoning_model,
    level_from_claim,
    signal_from_level,
)


class _FakeMessage:
    def __init__(self, content=None, reasoning=None, reasoning_content=None):
        self.content = content
        self.reasoning = reasoning
        self.reasoning_content = reasoning_content


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, choices):
        self.choices = choices


def test_is_reasoning_model_matches_the_families():
    assert is_reasoning_model("deepseek/deepseek-r1")
    assert is_reasoning_model("deepseek/deepseek-r1-0528")
    # the v4 family is reasoning-shaped too (observed 2026-09-05)
    assert is_reasoning_model("deepseek/deepseek-v4-flash")
    # the stealth model is GONE from OpenRouter — no longer detected
    # (the 2026-09-07 scrub)
    assert not is_reasoning_model("openrouter/stealth/ox-alpha")
    assert not is_reasoning_model("openrouter/nvidia/nemotron-3")

# THE FLOOR'S ONE APPLICATION IS `output_budget.floor_budget` (F.2/F-B retired the
# separate helper). Its assertions live with it:
# tests/unit/test_output_budget_table.py :: TestTheFloorHasOneApplication.
# This module keeps the DETECTION (`is_reasoning_model`) and the floor's VALUE.


def test_extract_response_text_reads_content_first():
    resp = _FakeResponse([_FakeChoice(_FakeMessage(content="the answer"))])
    assert extract_response_text(resp, "deepseek/deepseek-v4-flash") == "the answer"


def test_extract_response_text_falls_back_to_reasoning_fields():
    # content is empty (the reasoning-shaped response)
    resp = _FakeResponse([_FakeChoice(_FakeMessage(content="", reasoning="the thinking"))])
    assert extract_response_text(resp, "deepseek/deepseek-v4-flash") == "the thinking"
    resp2 = _FakeResponse([_FakeChoice(_FakeMessage(content="", reasoning_content="the thinking 2"))])
    assert extract_response_text(resp2) == "the thinking 2"


def test_extract_response_text_returns_empty_for_empty():
    resp = _FakeResponse([_FakeChoice(_FakeMessage(content=""))])
    assert extract_response_text(resp) == ""
    assert extract_response_text(None) == ""
    assert extract_response_text(_FakeResponse([])) == ""


class TestTheThinkingVocabulary:
    """F.3 — a level, a claim, and the difference between "thinks" and "must think"."""

    def test_a_silent_level_states_nothing(self):
        """`none` returns None so the NEXT source in the chain can speak."""
        assert signal_from_level("none", SOURCE_CURATED) is None
        assert signal_from_level(None, SOURCE_CURATED) is None
        assert signal_from_level("nonsense", SOURCE_CURATED) is None

    def test_the_effort_levels_mean_it_thinks(self):
        for level in ("low", "medium", "high"):
            signal = signal_from_level(level, SOURCE_DECLARATION)
            assert signal is not None
            assert signal.thinking and not signal.mandatory
            assert signal.source == SOURCE_DECLARATION

    def test_mandatory_is_a_different_fact_from_high(self):
        signal = signal_from_level("mandatory", SOURCE_PROVIDER_CLAIM)
        assert signal is not None
        assert signal.thinking and signal.mandatory

    def test_a_claim_is_projected_onto_our_levels(self):
        assert level_from_claim(True, True, "max") == "mandatory"
        assert level_from_claim(True, False, "max") == "high"
        assert level_from_claim(True, False, "xhigh") == "high"
        assert level_from_claim(True, False, None) == "high"   # never under-declare
        assert level_from_claim(True, False, "medium") == "medium"
        assert level_from_claim(True, False, "low") == "low"
        assert level_from_claim(True, False, "minimal") == "low"

    def test_a_claim_that_states_nothing_maps_to_nothing(self):
        assert level_from_claim(False, False, None) is None
        assert level_from_claim(False, False, "high") is None
        assert level_from_claim(True, False, "none") is None

    def test_a_signal_is_truthy_only_when_it_thinks(self):
        assert bool(signal_from_level("high", SOURCE_CURATED))
        assert not bool(ThinkingSignal())
        assert as_signal(True).thinking
        assert not as_signal(None).thinking
        given = ThinkingSignal(thinking=True, mandatory=True, source=SOURCE_CURATED)
        assert as_signal(given) is given

    def test_the_name_pattern_is_still_the_fallback_list(self):
        """F.3 shrinks it; it does not delete it — an unrecorded driver still floors."""
        assert is_reasoning_model("deepseek/deepseek-v4-flash")
