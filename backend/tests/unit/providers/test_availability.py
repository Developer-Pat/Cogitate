"""The availability read — the ONE answer to "is this service up, and what does it serve?".

Phase 6, group 5 (the availability ruling's DOWN half). What these tests pin:

* the **occupancy classification** survives the move out of `local_occupancy_service`: a silent
  local daemon beside a running one is `down-by-occupancy` (a swap-away, a CHOICE), not an incident;
* a silent daemon with nothing else local answering is `down`;
* **`unconfigured` is not `unreachable`** — a cloud row with no key is a configuration fact and the
  copy must not send the reader after the network;
* **`unknown` is NOT False** — an unprobed row has no answer, and a surface must be able to say so;
* the **cache**: a second read inside the TTL does not probe again, `force` does, and `cached()` is
  the only read a turn may make.

The probes are monkeypatched — no daemons, no network.
"""

from __future__ import annotations

import errno
import logging
import socket
from typing import Any, Dict, Optional, Tuple

import httpx
import pytest

from app.domain.providers import availability as av

# ollama is LOCAL by its type; llama.cpp is openai-TYPED but loopback — local by the class seam.
LOCAL_OLLAMA = {
    "id": 1, "name": "ollama", "provider_type": "ollama",
    "base_url": "http://localhost:11434",
}
LOCAL_LLAMA = {
    "id": 6, "name": "llama", "provider_type": "openai",
    "base_url": "http://127.0.0.1:8080/v1",
}
CLOUD_DEEPSEEK = {
    "id": 3, "name": "deepseek", "provider_type": "deepseek",
    "base_url": "https://api.deepseek.com",
}


@pytest.fixture(autouse=True)
def _cold_cache():
    """Every test starts with an empty memo AND an empty observation window — and leaves both so.

    The announced facts are the bridge's own memory (seam 3) and are process-wide like the memo, so
    they are cleared here too: a test that publishes must not decide the next test's news.
    """
    av.clear_cache()
    av.clear_observations()
    av.clear_facts()
    yield
    av.clear_cache()
    av.clear_observations()
    av.clear_facts()


def _probe_from(answers: Dict[Tuple[str, str], Optional[Dict[str, Any]]], calls: Optional[list] = None):
    """A `probe_json` stand-in answering per (base_url, path); a missing key = no answer."""

    async def probe(base_url: str, path: str, headers=None):
        if calls is not None:
            calls.append((base_url, path))
        return answers.get((base_url, path))

    return probe


# ── the local classification (moved from the occupancy service) ──────────────────────────────────

@pytest.mark.anyio
async def test_a_running_local_server_reads_available_with_what_it_serves(monkeypatch) -> None:
    """It answers, and we say WHAT it holds — the only honest local signal (the echo-back case)."""
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]}}),
    )

    result = await av.read_availability([LOCAL_LLAMA])

    llama = result["llama"]
    assert llama.state == "available"
    assert llama.available is True
    assert llama.models_served == ("bonsai-8b",)
    assert llama.checked_at, "the copy needs WHEN it was checked"


@pytest.mark.anyio
async def test_a_silent_daemon_beside_a_running_one_reads_down_by_occupancy(monkeypatch) -> None:
    """THE CLASSIFICATION THAT MADE THIS THE ONLY PROBE: a local down is usually a swap-away.

    ollama answers; llama.cpp is silent. On a flat up/down probe llama would read as an incident,
    and the capability page would then disagree with the local page about one daemon.
    """
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({
            ("http://localhost:11434", "/api/tags"): {"models": [{"name": "phi4-mini"}]},
            ("http://localhost:11434", "/api/ps"): {"models": [{"model": "phi4-mini:latest"}]},
        }),
    )

    result = await av.read_availability([LOCAL_OLLAMA, LOCAL_LLAMA])

    assert result["ollama"].state == "available"
    assert result["ollama"].models_served == ("phi4-mini:latest",)
    assert result["llama"].state == "down-by-occupancy"
    assert result["llama"].available is False, "it still cannot answer — the reason says why"
    assert "swap-away" in result["llama"].reason


@pytest.mark.anyio
async def test_nobody_local_answering_reads_down(monkeypatch) -> None:
    """The ownerless down: nothing answers, so it is an incident rather than a choice."""
    monkeypatch.setattr(av, "probe_json", _probe_from({}))

    result = await av.read_availability([LOCAL_OLLAMA, LOCAL_LLAMA])

    assert result["ollama"].state == "down"
    assert result["llama"].state == "down"


# ── the cloud path ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_a_cloud_row_without_a_key_is_unconfigured_not_unreachable(monkeypatch) -> None:
    """A configuration fact is NOT an outage, and the copy must not send the reader after the net."""
    calls: list = []
    monkeypatch.setattr(av, "probe_json", _probe_from({}, calls))
    monkeypatch.setattr(av, "env_key", lambda provider_type: None)

    async def no_key(provider):
        return None

    result = await av.read_availability([CLOUD_DEEPSEEK], key_for=no_key)

    deepseek = result["deepseek"]
    assert deepseek.state == "unconfigured"
    assert deepseek.available is False
    assert "unreachable" not in deepseek.reason
    assert calls == [], "a row with no key is not probed at all"


@pytest.mark.anyio
async def test_a_cloud_row_that_answers_reads_available_with_its_catalogue(monkeypatch) -> None:
    """A DELIBERATE read (`force`) is the only kind that dials a cloud row (ruled 2026-11-22)."""
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("https://api.deepseek.com", "/v1/models"): {"data": [{"id": "deepseek-v4-flash"}]}}),
    )

    async def key(provider):
        return "zz-key"

    result = await av.read_availability([CLOUD_DEEPSEEK], key_for=key, force=True)

    assert result["deepseek"].state == "available"
    assert result["deepseek"].models_served == ("deepseek-v4-flash",)


# ── the cache: the turn's only allowed read ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_a_second_read_inside_the_ttl_does_not_probe_again(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]}}, calls),
    )

    first = await av.read_availability([LOCAL_LLAMA])
    after_first = len(calls)
    second = await av.read_availability([LOCAL_LLAMA])

    assert after_first > 0, "the first read must actually probe"
    assert len(calls) == after_first, "the memo answered the second read"
    assert second["llama"] == first["llama"]
    # `cached()` is the ONLY read a turn may make — the pre-turn refusal asks this and never probes.
    assert av.cached(6) is not None


@pytest.mark.anyio
async def test_force_reprobes(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]}}, calls),
    )

    await av.read_availability([LOCAL_LLAMA])
    after_first = len(calls)
    await av.read_availability([LOCAL_LLAMA], force=True)

    assert len(calls) > after_first, "force must go back to the service"


def test_an_unknown_state_is_not_false() -> None:
    """`available=None` is the honest answer for an unprobed row — NOT False, which reads as broken."""
    unknown = av.Availability(
        provider_id=99, name="zz", state=av.STATE_UNKNOWN, reason="never checked",
        checked_at="2026-10-05T00:00:00Z",
    )
    assert unknown.available is None

    down = av.Availability(
        provider_id=99, name="zz", state=av.STATE_DOWN, reason="silent",
        checked_at="2026-10-05T00:00:00Z",
    )
    assert down.available is False


def test_cached_is_empty_after_a_clear() -> None:
    assert av.cached(6) is None


@pytest.mark.anyio
async def test_the_local_reason_names_the_file_not_the_servers_absolute_path(monkeypatch) -> None:
    """llama.cpp's single-model mode answers `/v1/models` with the `-m` path it was launched with.

    The reader must see the FILE. An absolute path in user-facing copy is the defect the
    local-provider page already carries (banked: THE LOCAL RUNTIME SELECTOR), and this read must not
    spread it to a second surface.

    The served id is built from parts so THIS FILE carries no absolute path of its own (the repo's
    path rule) while still exercising one.
    """
    served_id = "/".join(["", "srv", "llama-models", "Bonsai-27B-Q1_0.gguf"])
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": served_id}]}}),
    )

    result = await av.read_availability([LOCAL_LLAMA])

    assert "Bonsai-27B-Q1_0.gguf" in result["llama"].reason
    assert "/srv/" not in result["llama"].reason


# ── WHICH END a failure came from (the availability bridge's first seam) ─────────────────────────
#
# The user's ruling (2026-10-14): *"If the network is down (failure on the user's end) we can alert the
# user. If the network is up and we get a cloud failure, it is likely that comes from a provider
# related issue (failure on their end.)"* — and before this, EVERY failure arrived as one `None`, so a
# dead router, a dead daemon and a provider's HTTP 500 produced the same sentence.
#
# Two layers, because the class is read in two places: `classify_probe_error` off the exception (pure,
# tested directly), and `probe_json`/`_probe_cloud` carrying it into the payload (tested through a
# transport that fails the way a real one does).

CLOUD_ROW = {
    "id": 3, "name": "deepseek", "provider_type": "deepseek",
    "base_url": "https://api.deepseek.com",
}


async def _key_for(_provider):
    return "sk-fake"


class _RaisingClient:
    """A transport that fails the way httpx does — the exception, with its cause attached."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        raise self._exc


def _connect_error(cause: BaseException) -> httpx.ConnectError:
    """The shape httpx raises for BOTH a refused connection and a name that will not resolve."""
    err = httpx.ConnectError("probe failed")
    err.__cause__ = cause
    return err


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.deepseek.com/v1/models")
    return httpx.HTTPStatusError("bad status", request=request, response=httpx.Response(status, request=request))


# ── the classifier, read off the exception ───────────────────────────────────────────────────────

def test_the_classifier_reads_the_CAUSE_not_the_wrapper() -> None:
    """httpx raises `ConnectError` for a refused connection AND for a name that will not resolve.

    Only the socket error underneath separates them, so a classifier keyed on the wrapper alone would
    call every one of these "unreachable" — which is the misattribution the ruling exists to remove.
    """
    assert av.classify_probe_error(_connect_error(socket.gaierror(-2, "Name or service not known"))) \
        == av.FAILURE_UNREACHABLE
    assert av.classify_probe_error(_connect_error(ConnectionRefusedError(111, "Connection refused"))) \
        == av.FAILURE_REFUSED
    assert av.classify_probe_error(_connect_error(OSError(errno.ENETUNREACH, "Network is unreachable"))) \
        == av.FAILURE_UNREACHABLE


def test_a_status_that_ARRIVED_is_the_providers_end() -> None:
    """The path worked — the provider answered, badly. That is not the user's network."""
    assert av.classify_probe_error(_status_error(500)) == av.FAILURE_ANSWERED


def test_a_timeout_names_no_end() -> None:
    """A stall is a stalled path OR a slow provider. The module's discipline is to say so."""
    assert av.classify_probe_error(httpx.ConnectTimeout("timed out")) == av.FAILURE_TIMEOUT


def test_an_unreadable_failure_stays_unknown() -> None:
    """Never accuse a side on evidence that does not name one."""
    assert av.classify_probe_error(RuntimeError("something else entirely")) == av.FAILURE_UNKNOWN


def test_a_self_referential_cause_chain_does_not_loop() -> None:
    """The walk is bounded ON PURPOSE: an exception whose cause points back at itself is legal."""
    err = RuntimeError("cyclic")
    err.__cause__ = err
    assert av.classify_probe_error(err) == av.FAILURE_UNKNOWN


# ── the class riding the payload ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_the_probe_reports_the_class_it_failed_with(monkeypatch) -> None:
    exc = _connect_error(socket.gaierror(-2, "Name or service not known"))
    monkeypatch.setattr(av.httpx, "AsyncClient", lambda **kw: _RaisingClient(exc))

    outcome = await av.probe_json("https://api.deepseek.com", "/v1/models")

    assert outcome.payload is None
    assert outcome.failure == av.FAILURE_UNREACHABLE


@pytest.mark.anyio
async def test_a_cloud_row_names_the_USERS_end_when_the_name_will_not_resolve(monkeypatch) -> None:
    """The sentence a reader acts on: the network is THEIR side, and it says so."""
    exc = _connect_error(socket.gaierror(-2, "Name or service not known"))
    monkeypatch.setattr(av.httpx, "AsyncClient", lambda **kw: _RaisingClient(exc))

    reading = await av._probe_cloud(CLOUD_ROW, _key_for)

    assert reading.state == av.STATE_DOWN
    assert reading.failure == av.FAILURE_UNREACHABLE
    assert "network" in reading.reason


@pytest.mark.anyio
async def test_a_cloud_row_names_the_PROVIDERS_end_when_a_status_came_back(monkeypatch) -> None:
    """A 500 is not a network fault, and the copy must not send the reader after their router."""
    monkeypatch.setattr(
        av.httpx, "AsyncClient", lambda **kw: _RaisingClient(_status_error(500))
    )

    reading = await av._probe_cloud(CLOUD_ROW, _key_for)

    assert reading.failure == av.FAILURE_ANSWERED
    assert "provider" in reading.reason
    assert "network" not in reading.reason


@pytest.mark.anyio
async def test_an_answered_row_carries_no_class(monkeypatch) -> None:
    """`failure` is a fact about a FAILURE — a row that answered has none, at any state."""

    async def _listing(base_url, path, headers=None):
        return {"data": [{"id": "deepseek-v4-flash"}]}

    monkeypatch.setattr(av, "probe_json", _listing)

    reading = await av._probe_cloud(CLOUD_ROW, _key_for)

    assert reading.state == av.STATE_AVAILABLE
    assert reading.failure is None


@pytest.mark.anyio
async def test_a_stand_in_probe_keeps_the_modules_own_sentence(monkeypatch) -> None:
    """The doubles answer with a BARE payload — no class — so the copy must not lose its words.

    Every stand-in in the suite (`_probe_from`, the api tiers' fixtures) replaces `probe_json` with
    something that returns a dict or None. This pins what a bare None means: unattributed, and the
    module's own sentence survives rather than degrading to an empty reason.
    """

    async def nothing(base_url, path, headers=None):
        return None

    monkeypatch.setattr(av, "probe_json", nothing)

    reading = await av._probe_cloud(CLOUD_ROW, _key_for)

    assert reading.state == av.STATE_DOWN
    assert reading.failure is None
    assert reading.reason == "the provider did not answer"


# ── the NETWORK verdict: derived, never probed ───────────────────────────────────────────────────
#
# The user's constraint (2026-10-14): *"The application may run on someones network having unexplained
# network accesses could cause concern."* So the verdict has NO probe of its own — it is derived from
# calls the app was making anyway (a page's availability read, and later a turn's provider call), which
# is also why the ruling reads *"we notify when WE have a problem. We don't go looking for them."*
#
# The rule that earns its tests is the ASYMMETRY: evidence needs no corroboration (a body that arrived
# or a connection that was refused both prove the path works), while an ABSENCE does (blaming the
# user's connection takes two independent destinations going silent the same way).

def test_nothing_observed_is_unknown_not_up() -> None:
    """Silence is not health. With no call made, the app says it does not know."""
    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_UNKNOWN
    assert verdict.observed_at is None
    assert verdict.destinations == ()


def test_one_answered_call_proves_the_connection_works() -> None:
    av.record_observation("https://api.deepseek.com")
    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_UP
    assert "api.deepseek.com" in verdict.reason


def test_an_http_error_is_still_proof_the_path_works() -> None:
    """A 500 is an ANSWER: the packet went out and something replied. Not the user's connection."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_ANSWERED)
    assert av.network_verdict().state == av.NETWORK_UP


def test_a_refused_connection_also_proves_the_path_works() -> None:
    """A refusal travelled BACK, so the network carried it — this is the far side's answer."""
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_REFUSED)
    assert av.network_verdict().state == av.NETWORK_UP


def test_ONE_silent_destination_does_not_blame_the_connection() -> None:
    """One bad name is that name's problem — a hosts entry, a resolver blip, one provider's DNS."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_UNKNOWN
    assert "not enough" in verdict.reason


def test_twice_silent_on_the_SAME_destination_is_still_one_destination() -> None:
    """INDEPENDENCE is the rule, not the count: two failures at one host corroborate nothing."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_UNKNOWN
    assert verdict.destinations == ("https://api.deepseek.com",)


def test_two_independent_silent_destinations_blame_the_connection() -> None:
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_DOWN
    assert verdict.destinations == ("https://api.deepseek.com", "https://api.groq.com/openai/v1")


def test_only_what_happened_SINCE_the_last_answer_is_allowed_to_accuse() -> None:
    """A success a moment ago must not outvote the silence since it — and vice versa (next test)."""
    av.record_observation("https://api.deepseek.com")
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert av.network_verdict().state == av.NETWORK_DOWN


def test_a_later_answer_clears_the_verdict() -> None:
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert av.network_verdict().state == av.NETWORK_DOWN

    av.record_observation("https://api.deepseek.com")

    assert av.network_verdict().state == av.NETWORK_UP


def test_observations_older_than_the_window_are_dropped(monkeypatch) -> None:
    """A stale outage must stop being reported: the window is why the verdict has a freshness."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert av.network_verdict().state == av.NETWORK_DOWN

    later = av._monotonic() + av.NETWORK_WINDOW_SECONDS + 1
    monkeypatch.setattr(av, "_monotonic", lambda: later)

    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_UNKNOWN
    assert "no call has been observed" in verdict.reason


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _AnsweringClient:
    """A transport that answers — the success half of the producer."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        return _StubResponse(self._payload)


@pytest.mark.anyio
async def test_the_ONE_probe_a_page_already_makes_is_the_producer(monkeypatch) -> None:
    """No new traffic: the verdict's input is the read the pages were already making."""
    exc = _connect_error(socket.gaierror(-2, "Name or service not known"))
    monkeypatch.setattr(av.httpx, "AsyncClient", lambda **kw: _RaisingClient(exc))

    await av.probe_json("https://api.deepseek.com", "/v1/models")
    await av.probe_json("https://api.groq.com/openai/v1", "/v1/models")

    verdict = av.network_verdict()
    assert verdict.state == av.NETWORK_DOWN
    assert verdict.destinations == ("https://api.deepseek.com", "https://api.groq.com/openai/v1")


@pytest.mark.anyio
async def test_a_probe_that_answers_records_a_success(monkeypatch) -> None:
    monkeypatch.setattr(
        av.httpx, "AsyncClient",
        lambda **kw: _AnsweringClient({"data": [{"id": "deepseek-v4-flash"}]}),
    )

    outcome = await av.probe_json("https://api.deepseek.com", "/v1/models")

    assert outcome.payload is not None
    assert av.network_verdict().state == av.NETWORK_UP


def test_a_double_that_stands_in_for_the_transport_records_nothing(monkeypatch) -> None:
    """The suite's stand-ins answer a dict and never touch the wire — so they observe nothing.

    Pinned because it is the boundary: the recorder is INSIDE `probe_json`, and a test that replaces
    `probe_json` wholesale is not making a call, so it must not be read as evidence about one.
    """
    async def stand_in(base_url, path, headers=None):
        return {"data": [{"id": "x"}]}

    monkeypatch.setattr(av, "probe_json", stand_in)

    assert av.network_verdict().state == av.NETWORK_UNKNOWN


# ── THE TRANSITION RULE — what the bridge TELLS the user, and when (the third seam) ──────────────
#
# The user's ruling (2026-10-14): *"First sight publishes when the first sight IS the problem"*. So a
# first look that finds a PROBLEM speaks, a first look that finds things fine does not (a cold app
# must not announce that everything is up), and any CHANGE speaks. Above both sits the news rule: a
# service that cannot be reached while the CONNECTION is down is the network's story, not its own.
#
# The producers feeding it: the memo's write (every probe, local and cloud) and a real turn's call
# (`note_call_outcome`, the second producer). Both go through ONE rule, which is why these tests
# drive them through their own public surfaces rather than the rule directly.

@pytest.fixture
def toasts(monkeypatch) -> list:
    """Every warning the bridge hands the app's bus, in order, as (title, message, kind)."""
    import app.domain.messaging.services as messaging

    sent: list = []

    def capture(title: str, message: str, kind: str = "provider-fallback") -> None:
        sent.append((title, message, kind))

    monkeypatch.setattr(messaging, "publish_warning", capture)
    return sent


@pytest.mark.anyio
async def test_a_first_look_that_finds_a_dead_daemon_speaks(monkeypatch, toasts) -> None:
    """A cold app that finds a service down SAYS SO — silencing it would announce the recovery of an
    outage nobody was told about."""
    monkeypatch.setattr(av, "probe_json", _probe_from({}))

    await av.read_availability([LOCAL_OLLAMA, LOCAL_LLAMA])

    assert sorted(t[0] for t in toasts) == ["llama is not running", "ollama is not running"]
    assert all(t[2] == av.PROVIDER_STATE_KIND for t in toasts), "one kind, so one Message Center family"
    assert "the local server is not running" in toasts[0][1], "the module's own sentence, reused"


@pytest.mark.anyio
async def test_a_first_look_that_finds_things_fine_is_silent_but_recorded(monkeypatch, toasts) -> None:
    """Six rows read on a cold page must not produce six "up" toasts — and the fact still becomes the
    baseline, so the NEXT change is read against it."""
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]}}),
    )

    await av.read_availability([LOCAL_LLAMA])

    assert toasts == []
    assert av.announced_fact("provider:llama") == "available|"


@pytest.mark.anyio
async def test_a_swap_away_is_not_a_problem_to_announce(monkeypatch, toasts) -> None:
    """`down-by-occupancy` is this module's own *"a swap-away, not a fault"* — so a first look at one
    is silent (the ruling speaks for a PROBLEM), while the fact is still recorded."""
    monkeypatch.setattr(
        av, "probe_json",
        _probe_from({
            ("http://localhost:11434", "/api/tags"): {"models": [{"name": "phi4-mini"}]},
            ("http://localhost:11434", "/api/ps"): {"models": [{"model": "phi4-mini:latest"}]},
        }),
    )

    await av.read_availability([LOCAL_OLLAMA, LOCAL_LLAMA])

    assert toasts == []
    assert av.announced_fact("provider:llama") == "down-by-occupancy|"


@pytest.mark.anyio
async def test_a_re_observation_is_not_news_but_a_change_is(monkeypatch, toasts) -> None:
    """The toaster re-toasts the same content at a new `event_id`, so a fact may speak ONCE — and the
    daemon coming back is its own news."""
    answers: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {
        ("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]}
    }
    monkeypatch.setattr(av, "probe_json", _probe_from(answers))

    await av.read_availability([LOCAL_LLAMA])
    await av.read_availability([LOCAL_LLAMA], force=True)
    assert toasts == [], "the same fact twice is one fact"

    answers.clear()
    await av.read_availability([LOCAL_LLAMA], force=True)
    assert [t[0] for t in toasts] == ["llama is not running"]

    answers[("http://127.0.0.1:8080/v1", "/v1/models")] = {"data": [{"id": "bonsai-8b"}]}
    await av.read_availability([LOCAL_LLAMA], force=True)

    assert [t[0] for t in toasts] == ["llama is not running", "llama is running again"]
    assert "serves bonsai-8b" in toasts[-1][1]


@pytest.mark.anyio
async def test_a_cloud_row_under_a_dead_connection_is_NOT_the_providers_news(monkeypatch, toasts) -> None:
    """THE NEWS RULE: a cut cable must not publish "deepseek is down" — the network's own transition
    is the news, and the suppressed fact is left UNJUDGED so no recovery is announced for it either."""
    exc = _connect_error(socket.gaierror(-2, "Name or service not known"))
    monkeypatch.setattr(av.httpx, "AsyncClient", lambda **kw: _RaisingClient(exc))

    async def key(_provider):
        return "sk-fake"

    rows = [
        {"id": 3, "name": "deepseek", "provider_type": "deepseek", "base_url": "https://api.deepseek.com"},
        {"id": 4, "name": "groq", "provider_type": "groq", "base_url": "https://api.groq.com/openai/v1"},
    ]

    # A DELIBERATE read: page loads stopped dialling cloud rows (ruled 2026-11-22), and this test
    # is about what a FAILING cloud read publishes, not about who triggers it.
    await av.read_availability(rows, key_for=key, force=True)

    assert [t[0] for t in toasts] == ["The connection looks down"]
    assert "could not be reached" in toasts[0][1], "the verdict's own reason, not a second vocabulary"
    assert av.announced_fact("provider:deepseek") is None, "unjudged — the last TOLD fact still stands"
    assert av.announced_fact(av.FACT_NETWORK) == av.NETWORK_DOWN


def test_a_LOCAL_daemon_that_dies_is_its_own_news(toasts) -> None:
    """The news rule's other half: a daemon on THIS machine cannot have been cut off by the connection.

    The two cloud observations put the verdict at `down`, and the local call must neither be
    suppressed by that nor be read as evidence about the wire — a refused loopback connection would
    otherwise "prove" the path works.
    """
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert av.network_verdict().state == av.NETWORK_DOWN
    toasts.clear()

    av.note_call_outcome(
        "http://127.0.0.1:8080/v1",
        failure=av.FAILURE_REFUSED,
        provider="llama",
        model="openai/bonsai-8b",
    )

    assert [t[0] for t in toasts] == ["llama is not running"]
    assert "the connection was refused" in toasts[0][1], "the module's own per-class sentence"
    assert "Exa" not in toasts[0][1], "a local daemon is settled here — no outside diagnosis offered"
    assert av.network_verdict().state == av.NETWORK_DOWN, "the local call is not evidence about the wire"


def test_the_connection_speaks_once_and_only_on_a_change(toasts) -> None:
    """The corroboration rule and the transition rule, in one sequence: one silent destination is not
    enough to blame the connection, the verdict speaks when the second agrees, a repeat is not news,
    and the first answer after it is."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)
    assert toasts == [], "one destination is not the connection's problem"

    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert [t[0] for t in toasts] == ["The connection looks down"]

    av.record_observation("https://api.groq.com/openai/v1", failure=av.FAILURE_UNREACHABLE)
    assert len(toasts) == 1, "the same verdict twice is one fact"

    av.record_observation("https://api.groq.com/openai/v1")
    assert [t[0] for t in toasts] == ["The connection looks down", "The connection works"]


def test_an_unknown_connection_is_not_announced_and_not_stored(toasts) -> None:
    """`unknown` is the app saying it does not know — nothing is said, and nothing is remembered, so a
    `down` after it is still the change it is."""
    av.record_observation("https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE)

    assert toasts == []
    assert av.announced_fact(av.FACT_NETWORK) is None


def test_a_call_to_THIS_machine_is_not_evidence_about_the_connection() -> None:
    """Two dead local ports are two dead daemons — a local answer proves the loopback stack works, and
    the verdict is about the wire the app is riding."""
    assert av.is_loopback_destination("http://127.0.0.1:8080/v1")
    assert av.is_loopback_destination("localhost:11434")
    assert not av.is_loopback_destination("deepseek")
    assert not av.is_loopback_destination("https://api.deepseek.com")
    assert not av.is_loopback_destination("http://192.168.1.50:11434"), "a LAN address crosses the wire"

    av.record_observation("http://127.0.0.1:8080/v1", failure=av.FAILURE_UNREACHABLE)
    av.record_observation("http://localhost:11434", failure=av.FAILURE_UNREACHABLE)

    assert av.network_verdict().state == av.NETWORK_UNKNOWN


# ── the second producer: a REAL call's outcome ───────────────────────────────────────────────────

def test_a_real_calls_failure_names_the_row_and_the_model(toasts) -> None:
    """The statement contract: provider AND model, the module's own class sentence, no model
    recommendation — and the diagnosis offer, because a cloud service is not the reader's to fix."""
    av.note_call_outcome(
        "https://api.deepseek.com",
        failure=av.FAILURE_UNREACHABLE,
        provider="deepseek",
        model="deepseek/deepseek-chat",
    )

    assert len(toasts) == 1
    title, message, kind = toasts[0]
    assert title == "deepseek is not answering"
    assert "Deepseek Chat (deepseek)" in message
    assert "could not reach it" in message, "the class the module already owns, carried not re-invented"
    assert kind == av.PROVIDER_STATE_KIND


def test_an_ANSWERED_call_is_evidence_but_not_an_outage(toasts) -> None:
    """A 429 or a 500 is a reply: the verdict gains positive evidence, and the service is not accused
    (the per-turn copy speaks for a call that answered badly)."""
    av.note_call_outcome(
        "https://api.deepseek.com",
        failure=av.FAILURE_ANSWERED,
        provider="deepseek",
        model="deepseek/deepseek-chat",
    )

    assert toasts == []
    assert av.announced_fact("provider:deepseek") is None
    assert av.network_verdict().state == av.NETWORK_UP


def test_a_successful_call_corrects_a_stale_fact(toasts) -> None:
    """A call that answered is the strongest evidence there is, so it moves the fact — which is what
    makes a recovery visible without a probe."""
    av.note_call_outcome(
        "https://api.deepseek.com", failure=av.FAILURE_UNREACHABLE, provider="deepseek", model="deepseek/x"
    )
    assert [t[0] for t in toasts] == ["deepseek is not answering"]
    toasts.clear()

    av.note_call_outcome("https://api.deepseek.com", provider="deepseek", model="deepseek/x")

    assert [t[0] for t in toasts] == ["deepseek is answering again"]


def test_a_call_that_names_no_row_is_observed_but_accuses_nobody(toasts) -> None:
    """A fact needs a subject: the `/completions` passthrough takes a raw model string."""
    av.note_call_outcome("deepseek", failure=av.FAILURE_UNREACHABLE)

    assert toasts == []
    assert av.announced_fact("provider:deepseek") is None


# ── the call classifier: the wrapper's own type is NOT trusted ───────────────────────────────────

def _litellm_wrapped(inner: BaseException) -> BaseException:
    """The shape a real call's failure arrives in — measured 2026-10-14 against a dead local port.

    litellm raises `InternalServerError` — a STATUS-BEARING type carrying `status_code=500` — with
    the socket error SIX hops down: InternalServerError -> OpenAIError -> APIConnectionError ->
    ConnectError -> ClientConnectorError -> ConnectionRefusedError. Built by hand so the test pins
    the DEPTH as well as the order: a walk that stops early answers `unknown`, and one that reads the
    wrapper's status answers `answered`.
    """
    from litellm.exceptions import InternalServerError

    node: BaseException = inner
    for hop in ("ClientConnectorError", "ConnectError"):
        wrapper = type(hop, (Exception,), {})()
        wrapper.__cause__ = node
        node = wrapper
    api_error = InternalServerError(message="connection error", llm_provider="deepseek", model="m")
    api_error.__cause__ = node
    openai_error = type("OpenAIError", (Exception,), {})()
    openai_error.__cause__ = api_error
    top = InternalServerError(message="connection error", llm_provider="deepseek", model="m")
    top.__cause__ = openai_error
    return top


def test_a_refused_connection_under_a_STATUS_BEARING_wrapper_is_still_a_refusal() -> None:
    """The misattribution the whole arc exists to remove: the wrapper says "500", the socket says
    "refused", and the socket is right."""
    assert av.classify_call_error(_litellm_wrapped(ConnectionRefusedError(111, "Connection refused"))) \
        == av.FAILURE_REFUSED
    assert av.classify_call_error(_litellm_wrapped(socket.gaierror(-2, "Name or service not known"))) \
        == av.FAILURE_UNREACHABLE


def test_a_rate_limit_and_a_stall_are_read_off_their_own_families() -> None:
    from litellm.exceptions import RateLimitError, Timeout

    assert av.classify_call_error(RateLimitError(message="429", llm_provider="deepseek", model="m")) \
        == av.FAILURE_ANSWERED
    assert av.classify_call_error(Timeout(message="timed out", llm_provider="deepseek", model="m")) \
        == av.FAILURE_TIMEOUT


def test_an_unreadable_call_failure_stays_unknown() -> None:
    """Never accuse a side on evidence that does not name one — a turn's error copy and this class
    ride the same exception, so they must not disagree."""
    assert av.classify_call_error(RuntimeError("something else entirely")) == av.FAILURE_UNKNOWN


# ── a PAGE READ never dials a cloud row (ruled 2026-11-22) ───────────────────────────────────────

@pytest.mark.anyio
async def test_a_page_read_does_not_dial_a_cloud_row(monkeypatch) -> None:
    """The ruling: no packets of the app's own on somebody's network because a page was opened."""
    calls: list = []
    monkeypatch.setattr(av, "probe_json", _probe_from({}, calls))

    async def key(_provider):
        return "zz-key"

    result = await av.read_availability([CLOUD_DEEPSEEK], key_for=key)

    assert calls == [], "a page read must not call a cloud provider"
    row = result["deepseek"]
    assert row.state == "unknown", "no evidence means unknown — never `available`"
    assert row.available is None, "unknown is not False (which reads as broken)"
    assert row.checked_at == "", "nothing was checked, so no time may be claimed"
    assert "press Test" in row.reason


@pytest.mark.anyio
async def test_a_page_read_serves_the_memo_a_deliberate_read_warmed(monkeypatch) -> None:
    """A Test that just ran IS evidence a page may show — and it costs no second packet."""
    calls: list = []
    monkeypatch.setattr(
        av,
        "probe_json",
        _probe_from({("https://api.deepseek.com", "/v1/models"): {"data": [{"id": "deepseek-v4-flash"}]}}, calls),
    )

    async def key(_provider):
        return "zz-key"

    await av.read_availability([CLOUD_DEEPSEEK], key_for=key, force=True)
    after_test = len(calls)
    page = await av.read_availability([CLOUD_DEEPSEEK], key_for=key)

    assert len(calls) == after_test, "the page read added no probe of its own"
    assert page["deepseek"].state == "available"


@pytest.mark.anyio
async def test_a_keyless_cloud_row_still_reads_unconfigured_on_a_page(monkeypatch) -> None:
    """Configuration costs no packet, so it survives the ruling that stopped the probing."""
    calls: list = []
    monkeypatch.setattr(av, "probe_json", _probe_from({}, calls))
    monkeypatch.setattr(av, "env_key", lambda provider_type: None)

    async def no_key(_provider):
        return None

    result = await av.read_availability([CLOUD_DEEPSEEK], key_for=no_key)

    assert calls == []
    assert result["deepseek"].state == "unconfigured"
