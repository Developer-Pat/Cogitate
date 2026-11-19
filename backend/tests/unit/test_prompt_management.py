"""Better prompt management — the app's OWN prompt, kept honest and small.

The input-budget arc began with a warning about a 16,000-token budget and ended up measuring
the prompt itself. This file guards the two findings that were finishable without touching the
agents:

- **the tools section no longer repeats the tool schemas.** It printed one `- **name**:
  description` line per tool — the same two strings every schema already carries in the
  request's `tools=[...]` field. Measured on a live agent (14 tools): 1,281 tokens per call,
  1,020 of them the duplicate. A prompt section that grows with the tool count and says nothing
  the schemas do not is a section that should not exist;
- **the input soft reports what it measures.** Its sentence used to name a cause it never
  measured ("most of the room is going to the persona, the tools and the message") — and the
  measurement said otherwise: the persona is 579 tokens, and what filled the prompt was the
  pages the turn fetched.

Both are the same rule: a claim in the prompt (or about it) has to be a claim the app checked.
"""

import sys

sys.path.insert(0, "backend")

from app.api.v1.chat.context import _build_tools_section
from app.domain.chat.token_budget import estimate_tokens


def _tools(n: int) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": f"tool-{i}",
                "description": "A tool with a long description that the schema already carries. " * 3,
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for i in range(n)
    ]


def test_the_tools_section_is_not_an_inventory_of_the_tools():
    section = _build_tools_section(_tools(14))
    assert section, "a turn with tools still gets the behavioural note"
    assert "- **" not in section, "the name/description listing is the schemas' job"
    # not one tool name appears — the schemas are where names belong
    for i in range(14):
        assert f"tool-{i}" not in section


def test_the_tools_section_has_a_budget_and_does_not_grow_with_the_tool_count():
    """The old section grew by ~73 tokens per tool; this one does not grow at all. Pinned so a
    future edit cannot quietly reintroduce a listing."""
    small = _build_tools_section(_tools(1))
    large = _build_tools_section(_tools(60))
    assert small == large
    assert estimate_tokens(large) < 100, "a prompt section earns its tokens or it goes"


def test_no_tools_means_no_section():
    assert _build_tools_section([]) == ""
    assert _build_tools_section(None) == ""  # type: ignore[arg-type]


def test_the_delegates_strip_still_finds_the_section():
    """`router.chat_delegate` removes the tool guidance before it answers with the tools
    withheld, splitting on the section's heading. Renaming the heading without updating that
    split would leave tool guidance on a call that has no tools — so the coupling is pinned
    here rather than discovered later."""
    import re

    from app.api.v1.chat.context import _build_tools_section as build

    prompt = "the persona\n\n" + build(_tools(3))
    stripped = re.split(r"\n## Tools|\n## Available Tools|\n---\n", prompt)[0]
    assert stripped.strip() == "the persona"
    assert "## Tools" not in stripped


def test_the_input_soft_says_what_it_measures_and_not_what_it_guessed():
    from app.services.cognitive_pipeline.limits import call_soft_limits

    (limit,) = call_soft_limits(None, input_budget=16000)
    assert limit.key == "input_tokens"
    assert limit.threshold == 12800
    reason = limit.reason
    # it still says the thing the user needs (history is being dropped, nothing is blocked)
    assert "history is being dropped to fit" in reason
    assert "Nothing is blocked" in reason
    # and it no longer asserts the cause it never measured
    assert "the persona, the tools and the message" not in reason
    # Phase B changed what the budget counts, and the sentence has to say the new truth: the
    # fixed part IS counted now (schemas + replay), and the one thing still not re-judged is what
    # the turn adds to the prompt after assembly.
    assert "tool schemas" in reason and "replayed thinking" in reason
    assert "not re-judged" in reason
    assert "HISTORY alone" not in reason
