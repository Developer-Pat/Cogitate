"""
The catalog checker — it must FIRE on project history, and stay quiet on real words.

WHY THE QUIET HALF MATTERS AS MUCH AS THE FIRING HALF. The first sweep of these
docstrings was done with a regex, and the regex DESTROYED A REAL WORD: its phase
pattern matched inside ``two-phase``, so "The two-phase shutdown record" became
"The two- record". A checker that flags real words is the same defect with a
different symptom, and a check that cries wolf gets ignored — which is worse than
having no check at all, because it looks like diligence.

So every pattern here is tested in both directions: the history form fires, and the
English word that resembles it does not.
"""

from __future__ import annotations

import pytest

from app.domain.testing.catalog_check import check_catalog, check_description


def classes(description: str) -> set[str]:
    return {f["class"] for f in check_description("x.py", description)}


def detail(description: str, cls: str) -> str | None:
    for f in check_description("x.py", description):
        if f["class"] == cls:
            return f["detail"]
    return None


# ── IT FIRES ────────────────────────────────────────────────────────────────


def test_a_date_fires() -> None:
    assert "DATE" in classes("The chat-event contract tests (Step 1, 2026-08-24).")


def test_a_digit_phase_fires() -> None:
    assert "PHASE" in classes("The Phase 4 tests — the provision action.")


def test_a_LETTER_phase_fires() -> None:
    """THE CLASS THE FIRST SWEEP MISSED. A digit-only pattern matched ``Phase 2``
    and walked straight past 21 files reading ``Phase B``."""
    assert "PHASE" in classes("Agent selection + the GRAS override (ARM Phase B).")
    assert "PHASE" in classes("Create scaffolds (agent-lifecycle Phase B).")


def test_a_session_number_fires() -> None:
    assert "SESSION" in classes("Test script for Session 46: Observability with Langfuse.")


def test_an_incident_fires() -> None:
    assert "INCIDENT" in classes("WS cancel path (INCIDENT 2026-08-13).")


def test_a_build_label_fires() -> None:
    assert "CODENAME" in classes("The send_notification tool — the _23 F5 build.")


def test_a_known_codename_fires() -> None:
    for name in ("the yellow pages", "the yolo button", "the white pages"):
        assert "CODENAME" in classes(f"Registry addressing (ARM Phase A — {name})."), name


def test_two_sentences_on_the_rendered_line_fire() -> None:
    """The page takes the FIRST LINE, so a second sentence is truncated mid-thought.
    This is the defect that shipped and was caught by the user's spot check."""
    assert "TWO_SENTENCES" in classes(
        "The reasoning-model support — the budget floor. The ox-alpha incident showed a"
    )


def test_no_terminator_fires() -> None:
    assert "NO_TERMINATOR" in classes("Test Multi-Agent Parallel Execution")


def test_a_missing_description_fires() -> None:
    assert "MISSING" in classes("")


def test_too_long_fires() -> None:
    assert "TOO_LONG" in classes("The " + "very " * 25 + "long description of a test.")


def test_boilerplate_fires_when_the_description_is_the_module() -> None:
    """`Tests for X` where X is the module's own name. It is TRUE and a reader learns
    nothing - 31 of 173 descriptions measured this way."""
    assert "BOILERPLATE" in classes("Tests for Context Builder component.")
    assert "BOILERPLATE" in classes("Tests for conversation compaction.")
    assert "BOILERPLATE" in classes("Integration tests for the Curated Models API.")


def test_boilerplate_stays_quiet_when_the_description_names_something() -> None:
    """THE HALF THAT KEEPS THE CLASS USEFUL. 10 of the 41 `Tests for X` descriptions
    DO inform - they name a function or carry a parenthetical. Flagging those would
    make the class noise, and the batch would become a review of good descriptions."""
    clean = [
        "Tests for fact extraction (extract_facts -> cognitive_memory).",
        "Unit tests for the agent health scan (check_agent_health.py).",
        "Unit tests for EnvKeyStore - the app's single secrets store (.env).",
        "Unit tests for AgentService.health_for_agents (F3).",
        "Tests for the monitor workflow family (RSS digest + market watch).",
    ]
    for c in clean:
        assert "BOILERPLATE" not in classes(c), c


def test_boilerplate_is_not_raised_for_other_shapes() -> None:
    """Only the `Tests for X` opener. A description that names the behaviour directly
    is not boilerplate, however short."""
    for good in ("The two-phase shutdown record tests.",
                 "The chat-bus publishing tests.",
                 "The orphaned-messages regression tests - the ghost-history bug."):
        assert "BOILERPLATE" not in classes(good), good


# ── IT STAYS QUIET (the half that protects real words) ──────────────────────


@pytest.mark.parametrize("good", [
    "The two-phase shutdown record tests.",
    "The chat-bus publishing tests.",
    "The agent-package ADOPT action tests.",
    "The orphaned-messages regression tests — the ghost-history bug.",
    "The empty-completion fix tests — the empty assistant bubble.",
    "Regression tests for the litellm route.",
    "The a-key macros seed tests.",
    "The production-hardening gate tests.",
])
def test_a_clean_description_is_quiet(good: str) -> None:
    """Every one of these is real output from the corrected sweep. A checker that
    flags them is the "two-" bug in a new costume."""
    assert classes(good) == set(), f"{good!r} -> {classes(good)}"


def test_the_word_phase_inside_a_real_compound_word_is_not_a_phase() -> None:
    """THE REGRESSION THAT MOTIVATES THIS FILE. `two-phase` is a real word and must
    never be read as a project phase."""
    assert "PHASE" not in classes("The two-phase shutdown record tests.")
    assert "PHASE" not in classes("Tests for the multi-phase pipeline.")
    # and the detail, when it DOES fire, names the actual match - not a bare prefix
    assert detail("The Phase 4 tests.", "PHASE") == "Phase 4"


def test_a_clean_line_with_a_period_inside_a_path_is_not_two_sentences() -> None:
    """A dotted identifier and file paths carry dots that are not sentence ends."""
    assert "TWO_SENTENCES" not in classes("Regression tests for app.core.config.Settings.")


def test_an_abbreviation_ending_is_accepted() -> None:
    """A description may legitimately close on a bracket or a code span."""
    assert "NO_TERMINATOR" not in classes("The provider key endpoints (the Keys tab).")
