"""The stream-error interpretations — the shapes the user actually met.

`build_error_context` had branches for the status codes and none for the
provider's own failure vocabulary, so three real cases fell into the generic
buckets: a saturated upstream (`provider_unavailable`, usually arriving as a
503), a POLICY refusal (a 403 that no key change can fix), and a provider that
switches models mid-stream (litellm's MidStreamFallbackError).
"""

from __future__ import annotations

from app.api.v1.chat.error_handling import build_error_context


class _LiteLLMError(Exception):
    """The slice of a litellm error `extract_litellm_error_details` reads."""

    def __init__(self, message: str, status_code=None, type=None, response_body=""):
        super().__init__(message)
        self.status_code = status_code
        self.type = type
        self.response_body = response_body


def _category(error: Exception) -> str:
    return build_error_context(error, None, 0.0).get("error_interpretation", {}).get("category", "")


def test_a_saturated_upstream_is_named_as_such_not_as_a_server_error():
    # the shape OpenRouter used for nvidia/nemotron-3-super-120b-a12b:free
    err = _LiteLLMError("provider_unavailable: upstream is overloaded", status_code=503,
                        type="provider_unavailable")
    ctx = build_error_context(err, None, 0.0)["error_interpretation"]
    assert ctx["category"] == "provider_unavailable"
    assert ctx["is_user_error"] is False and ctx["is_retryable"] is True
    assert "overloaded" in ctx["summary"]


def test_a_policy_refusal_is_not_blamed_on_the_key():
    err = _LiteLLMError("403 only available on agentic harnesses", status_code=403,
                        response_body="This model is only available on agentic harnesses")
    ctx = build_error_context(err, None, 0.0)["error_interpretation"]
    assert ctx["category"] == "policy_refusal"
    assert ctx["is_user_error"] is False
    assert "key" in ctx["likely_cause"]


def test_an_ordinary_403_still_reads_as_a_permission_problem():
    err = _LiteLLMError("Forbidden", status_code=403, response_body="")
    assert _category(err) == "permission"


def test_a_mid_stream_fallback_is_its_own_category():
    class MidStreamFallbackError(Exception):
        pass

    assert _category(MidStreamFallbackError("provider switched model")) == "mid_stream_fallback"


def test_the_ordinary_branches_still_hold():
    assert _category(_LiteLLMError("slow down", status_code=429)) == "rate_limit"
    assert _category(_LiteLLMError("bad key", status_code=401)) == "authentication"
    assert _category(_LiteLLMError("boom", status_code=500)) == "server_error"
