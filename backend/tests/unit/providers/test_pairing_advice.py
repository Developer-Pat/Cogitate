"""The pairing advice — what will really happen when this driver meets this contract.

G4 (the provider's own output grant, unread until now) and G5's residue (the reasoning
floor, which makes a declared number not the number that goes out). It is REPORTED, not
enforced: the provider applies its own cap and the resolver applies the floor, so the
only thing this adds is knowing the outcome when the pairing is decided.

The rule it follows is the window-fit warning's: **an unknown need is not a finding.**
"""

from app.domain.providers.model_window import pairing_advice
from app.services.cognitive_pipeline.reasoning_support import REASONING_MAX_TOKENS_FLOOR


def test_a_plain_driver_with_no_grant_says_nothing() -> None:
    assert pairing_advice(8192, "none") == []


def test_a_grant_that_covers_the_declaration_says_nothing() -> None:
    """Exactly at the grant is not above it — the provider will give all of it."""
    assert pairing_advice(32768, "none", 32768) == []


def test_an_unknown_grant_is_not_a_finding() -> None:
    assert pairing_advice(49152, "none", None) == []


def test_a_thinking_driver_below_the_floor_is_announced() -> None:
    sentences = pairing_advice(8192, "high")

    assert len(sentences) == 1
    assert str(REASONING_MAX_TOKENS_FLOOR) in sentences[0]
    assert "declared number is not the number that goes out" in sentences[0]


def test_a_declaration_the_floor_does_not_touch_says_nothing() -> None:
    assert pairing_advice(REASONING_MAX_TOKENS_FLOOR, "high") == []
    assert pairing_advice(REASONING_MAX_TOKENS_FLOOR + 1, "high") == []
    assert pairing_advice(REASONING_MAX_TOKENS_FLOOR, "mandatory") == []


def test_mandatory_is_said_differently_because_the_lever_is_different() -> None:
    # BELOW the floor, or the floor moves nothing and there is nothing to say.
    sentences = pairing_advice(4096, "mandatory")

    assert len(sentences) == 1
    assert "cannot be told not to think" in sentences[0]
    assert "another driver" in sentences[0]


def test_a_declaration_above_the_grant_is_cut_at_the_grant() -> None:
    sentences = pairing_advice(49152, "none", 32768)

    assert len(sentences) == 1
    assert "grants at most 32768" in sentences[0]
    assert "49152 will be asked for" in sentences[0]


def test_the_grant_is_compared_against_what_will_really_be_asked() -> None:
    """A mandatory driver with nothing declared asks for the FLOOR, not for zero."""
    sentences = pairing_advice(None, "mandatory", 8192)

    assert len(sentences) == 2
    assert "cannot be told not to think" in sentences[0]
    assert f"and {REASONING_MAX_TOKENS_FLOOR} will be asked for" in sentences[1]


def test_the_who_label_names_the_candidate() -> None:
    sentences = pairing_advice(20000, "none", 8192, who="Candidate openai/gpt-oss-120b")

    assert sentences and sentences[0].startswith("Candidate openai/gpt-oss-120b:")
