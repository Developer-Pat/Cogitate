"""The shared-conversation-rules tests — which parts generalise.
"""

import inspect

from app.api.v1.chat.context import prepare_chat_context  # noqa: F401


def _src():
    return inspect.getsource(prepare_chat_context)


def test_shared_rules_are_unconditional():
    """The GENERAL rules (the etiquette + the source-integrity +
    the temporal context) apply to EVERY agent — the code has NO
    name-gates left (the persona moved to the stored profile)."""
    src = _src()
    assert "SHARED CONVERSATION RULES" in src
    assert "SNIPPET-DATE RULE" in src
    assert "TURN-TAKING RULE" in src
    assert "MORE THAN ONE" in src  # the numbered-questions rule
    assert "CONCISENESS RULE" in src
    assert "SOLICITATION RULE" in src
    assert "SOURCE-INTEGRITY RULE" in src
    assert "TOOL-HONESTY RULE" in src
    assert "TIMELINESS RULE" in src
    assert "MULTI-SOURCE RULE" in src
    assert "current date is {_today}" in src
    assert "{_timestr} ({_utc})" in src
    # NO agent-specific gates remain — the rules are everyone's
    assert 'agent.name == "Bob"' not in src


def test_scout_persona_is_data_owned():
    """The news-scout role text is NOT in the code — it lives in
    Bob's stored agent profile (the agents row). Code duplicating
    the persona would create drift."""
    src = _src()
    assert "NEWS-SCOUT ROLE" not in src
    assert "Antiwar.com" not in src
    assert "CURATED SOURCES" not in src
    # the shared rules remain the code-side layer
    assert "shared_rules" in src


def test_context_reads_persona_via_the_module():
    """THE WIRING PIN: prepare_chat_context builds the prompt through
    read_persona (the folder-first path) — reverting the call site to
    a bare `agent.system_prompt` would silently undo the workspace-
    first migration (the row fallback would win again)."""
    import inspect
    from app.api.v1.chat.context import prepare_chat_context
    src = inspect.getsource(prepare_chat_context)
    assert "from app.domain.agents.persona import read_persona" in src
    assert "read_persona(agent)" in src
