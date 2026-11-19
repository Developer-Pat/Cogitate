"""The bridge's SECOND PRODUCER — the chat funnel reporting what a real call did.

`acompletion_with_retry` is the one funnel every chat call passes through (its own comment: the loop,
the fallback, the delegate), so it is the one place a turn's traffic can be observed — and the ruling
allows the bridge no traffic of its own. What these tests pin:

* a failed call is reported with **the class read off the exception** (`classify_call_error`, whose
  whole point is that the wrapper's own type misleads);
* the ROW the caller named **rides along** — the carrier the provider fact needs;
* the carrier flag is **consumed**, never forwarded to litellm;
* a call that names no row is observed anyway but accuses nobody;
* a call that ANSWERED is reported as an answer (a fact about a failure only exists when there is
  one), and a RATE LIMIT is an answer too;
* **the known gap is pinned**: a STREAMED call that opens is not reported at all — a returned iterator
  is not a response, and a failure arriving mid-stream surfaces in the consumer.

The prose above is the arc's; the mechanism under test is `availability.note_call_outcome`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.api.v1.chat import llm_utils
from app.domain.providers import availability


@pytest.fixture(autouse=True)
def _clean_bridge():
    """The bridge's own memory is process-wide — every test starts and leaves it empty."""
    availability.clear_observations()
    availability.clear_facts()
    yield
    availability.clear_observations()
    availability.clear_facts()


@pytest.fixture
def reported(monkeypatch) -> List[Dict[str, Any]]:
    """Every outcome the funnel hands the bridge, in order."""
    sent: List[Dict[str, Any]] = []

    def capture(destination: str, **kwargs: Any) -> None:
        sent.append({"destination": destination, **kwargs})

    monkeypatch.setattr(availability, "note_call_outcome", capture)
    return sent


class _Response:
    """A non-streamed completion with no usage — the shape `response_usage` answers None for."""

    choices: List[Any] = []


class _FakeCompletion:
    """A litellm stand-in: answers by default, or raises exactly what the test sets."""

    def __init__(self) -> None:
        self.raises: Optional[BaseException] = None
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return _Response()


@pytest.fixture
def fake_acompletion(monkeypatch) -> _FakeCompletion:
    fake = _FakeCompletion()
    monkeypatch.setattr(llm_utils, "acompletion", fake)
    return fake


@pytest.mark.anyio
async def test_a_failed_call_reports_its_class_and_the_row_it_named(fake_acompletion, reported) -> None:
    """The provider fact needs a subject; the class needs to survive the wrapper."""
    from litellm.exceptions import Timeout

    fake_acompletion.raises = Timeout(message="timed out", llm_provider="deepseek", model="m")

    with pytest.raises(Timeout):
        await llm_utils.acompletion_with_retry(
            model="deepseek/deepseek-chat",
            messages=[],
            api_base="https://api.deepseek.com",
            provider="deepseek",
            max_retries=1,
        )

    assert reported == [
        {
            "destination": "https://api.deepseek.com",
            "failure": availability.FAILURE_TIMEOUT,
            "provider": "deepseek",
            "model": "deepseek/deepseek-chat",
        }
    ]


@pytest.mark.anyio
async def test_the_destination_is_the_rows_address_when_there_is_one(fake_acompletion, reported) -> None:
    """A local row's `api_base` IS where the call went — that is the verdict's destination."""
    fake_acompletion.raises = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await llm_utils.acompletion_with_retry(
            model="openai/bonsai-8b",
            messages=[],
            api_base="http://127.0.0.1:8080/v1",
            provider="llama",
            max_retries=1,
        )

    assert reported[0]["destination"] == "http://127.0.0.1:8080/v1"
    assert reported[0]["failure"] == availability.FAILURE_UNKNOWN, "an unreadable failure accuses nobody"


@pytest.mark.anyio
async def test_without_an_address_the_model_prefix_names_the_service(fake_acompletion, reported) -> None:
    """Two cloud services must be two destinations, or the verdict cannot corroborate across them."""
    await llm_utils.acompletion_with_retry(model="groq/llama-3.3-70b", messages=[], provider="groq")

    assert reported[0]["destination"] == "groq"
    assert reported[0]["failure"] is None


@pytest.mark.anyio
async def test_a_rate_limit_is_reported_as_an_ANSWER(fake_acompletion, reported) -> None:
    """A 429 is a reply: evidence the path works, and NOT the service being down — and the retry is
    still the turn's own business, unchanged by the report."""
    from litellm.exceptions import RateLimitError

    fake_acompletion.raises = RateLimitError(message="429", llm_provider="deepseek", model="m")

    with pytest.raises(RateLimitError):
        await llm_utils.acompletion_with_retry(
            model="deepseek/x", messages=[], provider="deepseek", max_retries=2, retry_delay=0
        )

    assert [r["failure"] for r in reported] == [
        availability.FAILURE_ANSWERED,
        availability.FAILURE_ANSWERED,
    ]
    assert len(fake_acompletion.calls) == 2, "each attempt is a call, and the retry still happens"


@pytest.mark.anyio
async def test_a_stream_that_opens_is_NOT_reported(fake_acompletion, reported) -> None:
    """THE KNOWN GAP, pinned so nobody assumes otherwise: a returned iterator is not a response, and
    a failure arriving mid-stream surfaces in the consumer — where the funnel is not looking."""
    stream = await llm_utils.acompletion_with_retry(
        model="deepseek/x", messages=[], stream=True, provider="deepseek"
    )

    assert stream is not None
    assert reported == [], "opening a stream is not evidence of an answer"


@pytest.mark.anyio
async def test_the_carrier_flag_is_consumed_and_never_forwarded(fake_acompletion, reported) -> None:
    """The wiring's own test: an unknown kwarg would reach litellm as a TypeError in production."""
    await llm_utils.acompletion_with_retry(model="deepseek/x", messages=[], provider="deepseek")

    assert "provider" not in fake_acompletion.calls[0]


@pytest.mark.anyio
async def test_a_caller_that_names_no_row_is_observed_but_accuses_nobody(fake_acompletion, reported) -> None:
    """The `/completions` passthrough takes a raw model string: it is traffic, not a row."""
    fake_acompletion.raises = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await llm_utils.acompletion_with_retry(model="meta/llama-3", messages=[], max_retries=1)

    assert reported[0]["provider"] is None
