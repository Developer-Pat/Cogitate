"""The definitive failure statement — the app says WHERE the problem is.

WHY THIS EXISTS (the Lois / Space Bunny dig, 2026-09-29). OpenRouter's cloaked
`stealth/space-bunny-alpha` returned "Provider returned an empty response"
(`provider_unavailable`) twice inside one turn. The app had ALREADY classified
that failure — `handle_streaming_error` sends the honest sentence in the error
frame — and then asked the MODEL to explain it, with tools withheld. The model
answered with a claim about its own limits ("I don't have live weather access in
this response…") for a turn whose tools had just fetched that very weather, and
because the deep pass came back empty that claim was KEPT as the answer.

`build_failure_statement` composes the answer from the classifier instead:
the model's own name, what happened, and what to do about it.

THE TESTS are discriminating: each fails if the statement stops naming the model
or stops carrying the classifier's words.
"""

from types import SimpleNamespace
from typing import Any

from app.api.v1.chat.error_handling import (
    build_failure_statement,
    failure_sentence,
    model_label,
    model_subject,
)
from app.domain.providers.failure_statement import (
    FailureSubject,
    failure_sentence_for,
    failure_sentence_for_subject,
    provider_reported,
)


class MidStreamFallbackError(RuntimeError):
    """Shaped like litellm's `MidStreamFallbackError`.

    The class NAME is what the classifier reads first, and the provider
    attributes are what make `extract_litellm_error_details` return anything at
    all — without one of them none of the interpretation branches run.
    """

    def __init__(self, message: str, status_code: int | None = 503):
        super().__init__(message)
        self.llm_provider = "openrouter"
        self.model = "stealth/space-bunny-alpha"
        if status_code is not None:
            self.status_code = status_code


def _context(
    model: str = "openrouter/stealth/space-bunny-alpha",
    provider: str = "openrouter",
    fallback: bool = False,
) -> Any:
    """The fields `build_error_context` reads off the chat context.

    A stand-in, not a `ChatContext`: the function reads attributes and nothing else, and
    building a real one needs an Agent and a ChatSession row. `fallback` is the agent's
    `fallback_enabled` setting — the default here matches the agent in the report (off).
    """
    return SimpleNamespace(
        model=model,
        provider=provider,
        session_id=189,
        agent_id=56,
        agent_name="Lois",
        messages_count=2,
        tools_count=10,
        agent=SimpleNamespace(name="Lois", fallback_enabled=fallback),
    )


# ---------------------------------------------------------------------------
# 1. The label a person reads
# ---------------------------------------------------------------------------

def test_model_label_drops_the_routing_and_the_variant_marker():
    assert model_label("openrouter/stealth/space-bunny-alpha") == "Space Bunny Alpha"
    assert model_label("openrouter/google/gemma-4-31b-it:free") == "Gemma 4 31b It"
    assert model_label("llama3.2") == "Llama3.2"


def test_model_label_never_returns_an_empty_string():
    assert model_label(None) == "The model"
    assert model_label("") == "The model"


# ---------------------------------------------------------------------------
# 2. The statement: WHERE the problem is, and a name for it
# ---------------------------------------------------------------------------

def test_statement_names_the_model_and_carries_the_classification():
    error = MidStreamFallbackError(
        "Provider returned an empty response, Metadata: {'error_type': 'provider_unavailable'}"
    )
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert statement.startswith("Space Bunny Alpha (openrouter) is not functioning properly —")
    # the classifier's own words, lower-cased for mid-sentence flow
    assert "the upstream for this model is overloaded or unavailable." in statement
    # the setting that would have carried the turn, said plainly
    assert "No fallback is configured for this agent." in statement


def test_statement_never_recommends_a_model():
    """The user's rule: name the offender and say it is not working — the replacement is the
    reader's decision, not the app's."""
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context())

    assert statement is not None
    lowered = statement.lower()
    for recommendation in ("try another model", "paid version", "different model", "use another"):
        assert recommendation not in lowered


def test_statement_fingers_BOTH_the_llm_and_its_provider():
    """The requirement: the reader must be able to act, which needs the offender named.

    The model alone leaves "which provider?" open for a model served by more than one, and
    the provider alone leaves "which model?" open — this turn ran a model, not a provider.
    """
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert "Space Bunny Alpha" in statement
    assert "(openrouter)" in statement


def test_statement_survives_a_missing_provider_name():
    """No provider on the context: name the model rather than print empty brackets."""
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context(provider=""))

    assert statement is not None
    assert statement.startswith("Space Bunny Alpha is not functioning properly —")
    assert "()" not in statement


def test_a_configured_fallback_is_not_touted_as_missing():
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context(fallback=True))

    assert statement is not None
    assert "No fallback is configured" not in statement


def test_a_non_provider_failure_does_not_mention_the_fallback():
    """An auth failure is not a model that failed — a fallback would not have helped, and every
    model would have hit the same wall."""
    error = MidStreamFallbackError("invalid api key", status_code=401)
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert "authentication failed" in statement.lower()
    assert "No fallback is configured" not in statement


def test_the_statement_offers_exa_for_the_diagnosis():
    """The app names what broke; the deeper why is Exa's job."""
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert statement.endswith("You can have Exa attempt diagnosis (ask Exa).")


def test_statement_is_the_app_s_own_words_not_a_model_claim():
    """The defect this replaces: the answer must not read as a capability limit."""
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert "I don't have" not in statement
    assert "I can't" not in statement
    # three sentences of fact: what is not working, the setting that would have covered it,
    # and the diagnosis offer — no diagnostics, no model recommendation
    assert statement.count(". ") <= 3


def test_statement_uses_the_classification_for_other_recognised_failures():
    """A rate limit is a different problem and gets different words."""
    error = MidStreamFallbackError("rate limit exceeded", status_code=429)
    statement = build_failure_statement(error, _context())

    assert statement is not None
    assert "Space Bunny Alpha (openrouter) is not functioning properly — provider rate limit exceeded." in statement


def test_the_model_name_is_the_one_this_turn_ran():
    error = MidStreamFallbackError("provider_unavailable")
    statement = build_failure_statement(error, _context(model="openrouter/inclusionai/ling-3.0-flash"))

    assert statement is not None
    assert statement.startswith("Ling 3.0 Flash (openrouter) is not functioning properly —")


# ---------------------------------------------------------------------------
# 3. When the app CANNOT place the failure, it says nothing
# ---------------------------------------------------------------------------

def test_unclassified_failure_still_names_the_llm():
    """The rule does not depend on the classifier: even a failure nothing recognises says WHICH
    LLM failed, because that is the part the reader can act on."""
    statement = build_failure_statement(RuntimeError("something odd arrived from the provider"), _context())

    assert statement is not None
    assert statement.startswith("Space Bunny Alpha (openrouter) is not functioning properly —")
    assert "the provider reported: something odd arrived from the provider." in statement
    # nothing classified → nothing claims a cause, and the fallback note is not invented
    assert "No fallback is configured" not in statement


def test_an_unclassified_reason_is_one_trimmed_line():
    long_error = RuntimeError("x" * 400)
    statement = build_failure_statement(long_error, _context())

    assert statement is not None
    assert len(statement) < 400
    assert "…" in statement


def test_missing_error_is_not_a_statement():
    assert build_failure_statement(None, _context()) is None


# ---------------------------------------------------------------------------
# 4. The same naming, for the failures the classifier cannot cover
# ---------------------------------------------------------------------------

def test_model_subject_needs_both_halves():
    assert model_subject("openrouter/stealth/space-bunny-alpha", "openrouter") == "Space Bunny Alpha (openrouter)"
    # a missing half is left out, never printed as empty brackets
    assert model_subject("openrouter/stealth/space-bunny-alpha", None) == "Space Bunny Alpha"
    assert model_subject("openrouter/stealth/space-bunny-alpha", "  ") == "Space Bunny Alpha"


def test_failure_sentence_names_the_llm():
    """The fallback's own failure modes get the same treatment as a classified one."""
    sentence = failure_sentence(_context(), "the answer took too long to arrive. Try again.")

    assert sentence == (
        "Space Bunny Alpha (openrouter) is not functioning properly — "
        "the answer took too long to arrive. Try again. "
        "You can have Exa attempt diagnosis (ask Exa)."
    )


# ---------------------------------------------------------------------------
# 5. The subject-taking core, and the chat façade over it
#    (phase 6 group 3 — the wording MOVED to the domain so the title service
#    could reach it; the chat path's sentence must not have moved with it)
# ---------------------------------------------------------------------------

def test_failure_sentence_for_builds_the_sentence_from_a_subject():
    """The core takes the two halves a statement needs, not a caller-shaped context object."""
    assert failure_sentence_for(
        "openrouter/stealth/space-bunny-alpha", "openrouter", "the answer took too long."
    ) == (
        "Space Bunny Alpha (openrouter) is not functioning properly — "
        "the answer took too long. You can have Exa attempt diagnosis (ask Exa)."
    )


def test_failure_sentence_for_invents_no_name_when_nothing_resolved():
    """No model and no provider: the subject SAYS so rather than naming a service nobody chose."""
    sentence = failure_sentence_for(None, None, "no service resolved for session titles.")

    assert sentence.startswith("The model is not functioning properly —")
    assert "no service resolved for session titles." in sentence


def test_provider_reported_labels_the_words_as_theirs():
    """The unclassified clause says WHOSE words these are — one home for that labelling."""
    assert provider_reported(RuntimeError("Error code: 401")) == "the provider reported: Error code: 401"


def test_the_chat_facade_is_the_core_sentence():
    """`error_handling.failure_sentence` is a FAÇADE — the same sentence as the core it delegates to.

    The chat path's wording is a contract with the reader; the extraction that gave the title
    service the same sentence must not have changed a character of it.
    """
    reason = "the answer took too long to arrive. Try again."

    assert failure_sentence(_context(), reason) == failure_sentence_for(
        "openrouter/stealth/space-bunny-alpha", "openrouter", reason
    )


# ---------------------------------------------------------------------------
# 6. The subject value — the ONE shape every path builds and renders
#    (phase 6 group 4, G4-F3: "one wording, one place, every surface")
# ---------------------------------------------------------------------------

def test_a_subject_renders_the_one_wording_the_workflow_path_builds():
    """The workflow path's subject: the service the run resolved + the provider's own words."""
    sentence = failure_sentence_for_subject(
        FailureSubject(
            model="deepseek-v4-flash",
            provider="deepseek",
            reason=provider_reported(RuntimeError("boom")),
        )
    )

    assert sentence == (
        "Deepseek V4 Flash (deepseek) is not functioning properly — "
        "the provider reported: boom. "
        "You can have Exa attempt diagnosis (ask Exa)."
    )


def test_the_renderer_terminates_an_unterminated_clause():
    """Rule (a): `reason` is a clause and the renderer ends it — this is why the TITLE
    statement, which passes `provider_reported(...)` unterminated, now reads with its period."""
    sentence = failure_sentence_for_subject(
        FailureSubject(model="m", provider="p", reason="the provider reported: boom")
    )

    assert sentence.startswith("M (p) is not functioning properly — the provider reported: boom.")


def test_the_renderer_does_not_double_punctuate_a_terminated_clause():
    terminated = FailureSubject(model="m", provider="p", reason="the answer took too long to arrive.")

    assert "arrive." in failure_sentence_for_subject(terminated)
    assert "arrive.." not in failure_sentence_for_subject(terminated)


def test_the_renderer_mentions_the_fallback_setting_only_where_the_caller_says_so():
    """The workflow and title paths have no fallback lever, so they say NOTHING; the chat path
    answers the question it is the only one able to hear."""
    provider_failure = FailureSubject(model="m", provider="p", reason="r", category="rate_limit")

    assert "No fallback is configured" not in failure_sentence_for_subject(provider_failure)
    assert "No fallback is configured for this agent." in failure_sentence_for_subject(
        provider_failure, fallback_configured=False
    )
    # a category that is NOT the model itself failing never mentions the setting
    auth = FailureSubject(model="m", provider="p", reason="r", category="authentication")
    assert "No fallback is configured" not in failure_sentence_for_subject(
        auth, fallback_configured=False
    )


def test_the_chat_path_is_the_subject_renderer():
    """`build_failure_statement` is the SAME renderer — the chat path builds a subject and
    renders it, so its sentence cannot drift from the workflow's or the title's."""
    error = MidStreamFallbackError("provider_unavailable")
    context = _context()

    statement = build_failure_statement(error, context)
    subject = FailureSubject(
        model=context.model,
        provider=context.provider,
        reason="the upstream for this model is overloaded or unavailable",
        category="provider_unavailable",
    )

    assert statement == failure_sentence_for_subject(subject, fallback_configured=False)
