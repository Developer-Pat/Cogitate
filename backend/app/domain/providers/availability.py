"""ONE answer to *"is this service up, and what does it serve right now?"*

The service-capability arc, phase 6 group 5 — the availability ruling's DOWN half.

**Why this module exists.** Before it, the app answered "is the provider up?" in FOUR places that
agreed only by luck: `POST /providers/config/{id}/test` (a flat up/down plus a model count),
a zero-caller copy of the same logic in `ProviderConfigService.test_provider_connection`, the legacy
`POST /providers/{id}/test` over a hardcoded provider dict, and the local occupancy read
(`healthy` / `down-by-occupancy` / `down`). A `down` here and a `healthy` there about one daemon is
the class of second answer this arc removes, so the probe primitives MOVED here (from
`local_occupancy_service`, verbatim) and everything that asks the question calls THIS.

**Consumers, as they stand.** The capability read-out, the agent surfaces' "can this run now?"
badge and the pre-turn refusal all read this module (`read_availability`,
`read_availability_for`, `cached`). So do all three "test this provider" endpoints —
`/providers/config/{id}/test`, `/providers/managed/{id}/test` and the legacy `/providers/{id}/test` —
each rendering `test_card`, so no two of them can describe one daemon differently.
`ProviderConfigService.test_provider_connection` — the zero-caller copy — is DELETED.

**A LISTING IS NOT A KEY CHECK.** An availability read is reachability plus a listing, and on
ollama.com every listing is ungated: `/api/tags` answers 200 with no key at all and the
OpenAI-compat `/v1/models` answers 200 to a deliberately fake one (both measured). A Test that stops
at the listing therefore reports "connected" through a dead key. `verify_key=True` — asked only by
the Test button, never by a page's read — adds the one gated operation, a one-token completion, and
reports a refusal as CONFIGURATION (`unconfigured`) rather than an outage.

**What it answers.**
* **connectivity** — does the service answer at all;
* **what it serves RIGHT NOW** (the loaded models) — which for a local row is the only honest
  signal: llama.cpp's single-model mode serves what it loaded and **echoes it back**, so a
  configured slug the catalogue does not list is NOT proof of failure (measured 2026-10-04);
* for a **LOCAL** row the state is the occupancy classification, because a local "down" is usually a
  swap-away — the GPU is owned by another daemon — and that is a **choice**, not an incident. A flat
  up/down would call it an incident and put this module at odds with the local page about one daemon.

**What it deliberately does NOT do.** It does not decide a turn. The **at-turn chain walk stays the
arbiter** for a real turn (a turn tries, fails over, and reports the last failure); this module seeds
the SIGNAL the surfaces show. The pre-turn refusal reads the **cache only** — it never probes on a
turn's behalf — so an `unknown`/stale state never refuses.

**The cache.** In-process, keyed by provider id, TTL'd. Every payload carries `checked_at`, so the
copy owns the staleness window rather than a bare boolean hiding it.
"""

from __future__ import annotations

import asyncio
import errno
import logging
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

import httpx

from app.domain.providers.failure_statement import EXA_DIAGNOSIS_OFFER, model_subject
from app.domain.providers.provider_endpoints import compat_root_offer, native_root

logger = logging.getLogger(__name__)

# The probe timeout: SHORT — an availability read must never hang a page the way a stalled fetch
# hangs a turn. Inherited verbatim with the primitive.
PROBE_TIMEOUT = 2.5

# The endpoints per class.
OLLAMA_PS_PATH = "/api/ps"          # ollama's loaded models
OLLAMA_TAGS_PATH = "/api/tags"      # ollama reachability
OPENAI_MODELS_PATH = "/v1/models"   # llama.cpp / any openai-compatible service

# ── The states ───────────────────────────────────────────────────────────────────────────────────
# `available` is DERIVED from the state, so a surface has one boolean to key on and one reason to
# print, and the copy never has to map a vocabulary of its own.
STATE_AVAILABLE = "available"                  # it answers
STATE_DOWN_BY_OCCUPANCY = "down-by-occupancy"  # silent, but another LOCAL daemon answers: the GPU
                                               # is owned — a swap-away / a choice, not an incident
STATE_DOWN = "down"                            # silent, and nothing else local answers either
STATE_UNCONFIGURED = "unconfigured"            # cannot be attempted for a CONFIGURATION reason
                                               # (no API key) — not a connectivity one, and the copy
                                               # must not call this "unreachable"
STATE_UNKNOWN = "unknown"                      # never probed — say so rather than guess

# The cache TTL: generous by the seeding rule, and `checked_at` rides every payload so the staleness
# window is owned by the copy rather than hidden behind a bare boolean.
DEFAULT_TTL_SECONDS = 60.0

# ── WHICH END a failure came from ────────────────────────────────────────────────────────────────
# The availability bridge's first seam (2026-10-14). The ruling rests on an attribution the probe
# could not make: *"If the network is down (failure on the user's end) we can alert the user. If the
# network is up and we get a cloud failure, it is likely that comes from a provider related issue
# (failure on their end.)"* — and every failure used to arrive as one `None`, so the reason said
# "the provider did not answer" for a dead router, a dead daemon and a provider's HTTP 500 alike.
#
# The class is read off the exception the transport actually raised. Nothing here probes anything:
# these are the ENDS a failure can be on, and the wiring that publishes one is the bridge's own work.
FAILURE_UNREACHABLE = "unreachable"  # no route, or a name that will not resolve — the USER's end
FAILURE_REFUSED = "refused"          # something answered and said no — nothing is listening there
FAILURE_ANSWERED = "answered"        # a response arrived with a bad status — the PROVIDER's end
FAILURE_TIMEOUT = "timeout"          # nothing in time: a stalled path or a slow provider
FAILURE_UNKNOWN = "unknown"          # a failure with no end to point at — say so, never guess


# How deep a cause chain is read. A DIRECT transport failure is shallow (httpx's wrapper, then the
# socket error), but a real CALL arrives wrapped twice more — measured 2026-10-14: a refused
# connection through litellm surfaces as `InternalServerError` carrying `status_code=500`, with
# `ConnectionRefusedError` SIX hops down. So the probe's bound stays where it was and the call's is
# wider; a bounds that is too tight does not mis-accuse, it goes silent (`unknown`), which is why
# this is a depth and not a guess.
PROBE_CAUSE_DEPTH = 5
CALL_CAUSE_DEPTH = 10


def _cause_chain(exc: BaseException, depth: int) -> List[BaseException]:
    """The exception and up to `depth - 1` of its causes — bounded, because a chain that points at
    itself is legal (`test_a_self_referential_cause_chain_does_not_loop`)."""
    chain: List[BaseException] = []
    inner: Optional[BaseException] = exc
    for _ in range(depth):
        if inner is None:
            break
        chain.append(inner)
        inner = inner.__cause__ or inner.__context__
    return chain


def _classify_socket_chain(chain: Sequence[BaseException]) -> str:
    """The END a socket-level fact names, from a cause chain — or `unknown` when it names none."""
    for inner in chain:
        if isinstance(inner, socket.gaierror):
            return FAILURE_UNREACHABLE
        if isinstance(inner, (ConnectionRefusedError, ConnectionResetError)):
            return FAILURE_REFUSED
        if isinstance(inner, OSError) and inner.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
            return FAILURE_UNREACHABLE
    return FAILURE_UNKNOWN


def classify_probe_error(exc: BaseException) -> str:
    """Which END a probe failure came from, read off the exception it raised.

    The wrapper alone is not enough: httpx raises `ConnectError` for a refused connection AND for a
    name that will not resolve, and the socket error underneath is what separates them. So walk the
    `__cause__`/`__context__` chain — bounded, because a chain that refers to itself would otherwise
    loop — looking for the one fact that names an end, and answer `unknown` rather than accuse a side.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        # The status ARRIVED, so the path to the provider is fine: the provider answered, badly.
        return FAILURE_ANSWERED
    if isinstance(exc, httpx.TimeoutException):
        return FAILURE_TIMEOUT
    return _classify_socket_chain(_cause_chain(exc, PROBE_CAUSE_DEPTH))


def _is_status_family(exc: BaseException) -> bool:
    """Whether a provider error reports a status the far side SENT — the ANSWERED half of a call.

    The TYPE is asked, never `status_code`: measured 2026-10-14, litellm's `APIConnectionError`
    carries `status_code=500` as a placeholder, so a classifier reading that attribute calls a dead
    port an answer. `openai.APIStatusError` is the family litellm's status-bearing errors are built on
    (`RateLimitError`, `AuthenticationError`, `InternalServerError`, `BadRequestError`,
    `NotFoundError`, `ServiceUnavailableError` — all measured), and `APIConnectionError` is NOT one.
    """
    try:
        from openai import APIStatusError
    except Exception:  # noqa: BLE001 — a missing client library is not a classification
        return False
    return isinstance(exc, APIStatusError)


def _is_timeout_family(exc: BaseException) -> bool:
    """Whether a provider error is the timeout family — litellm's, or the OpenAI client's own."""
    try:
        from litellm.exceptions import Timeout as LiteLLMTimeout
        from openai import APITimeoutError
    except Exception:  # noqa: BLE001 — same as above
        return False
    return isinstance(exc, (LiteLLMTimeout, APITimeoutError))


def classify_call_error(exc: BaseException) -> str:
    """Which END a REAL CALL's failure came from — the second producer's classifier (seam 3).

    Distinct from `classify_probe_error` in ORDER, and the order is the whole point. A probe raises
    the httpx exception itself; a turn's call arrives wrapped by litellm and the OpenAI client, and
    **the wrapper's own type misleads**: measured 2026-10-14 against a dead local port, a refused
    connection is raised as `InternalServerError` — a status-bearing type carrying `status_code=500`
    — with the socket error six hops down. So the socket facts are read FIRST (whatever the wrapper
    says, a refusal reached back and a DNS failure did not), then a stall, and only then a status:
    an answer that truly arrived has a socket-successful path underneath it.
    """
    chain = _cause_chain(exc, CALL_CAUSE_DEPTH)
    socket_end = _classify_socket_chain(chain)
    if socket_end != FAILURE_UNKNOWN:
        return socket_end
    if any(isinstance(inner, httpx.TimeoutException) for inner in chain) or _is_timeout_family(exc):
        return FAILURE_TIMEOUT
    if any(isinstance(inner, httpx.HTTPStatusError) for inner in chain) or _is_status_family(exc):
        return FAILURE_ANSWERED
    return FAILURE_UNKNOWN


# ── The NETWORK verdict: derived from calls the app already makes ─────────────────────────────────
# The ruling (2026-10-14) asks whether a failure is on the USER's end or the PROVIDER's, and the
# constraint that outranks the technique: *"The application may run on someones network having
# unexplained network accesses could cause concern."* So this verdict is never probed for — there is
# no canary, no ping, no periodic lookup. It is DERIVED from the outcome of calls the app was making
# anyway (a page's availability read, a turn's provider call), which is why the user's follow-up is
# the module's rule too: *"We notify when WE have a problem. We don't go looking for them."*
NETWORK_UP = "up"          # the path demonstrably works
NETWORK_DOWN = "down"      # several independent destinations are silent the same way
NETWORK_UNKNOWN = "unknown"  # not enough evidence — say so rather than blame the connection

# How far back an observation counts. Short enough that a stale success cannot mask a live outage,
# long enough that a page's few concurrent probes corroborate each other.
NETWORK_WINDOW_SECONDS = 180.0
_OBSERVATION_CAP = 64


@dataclass(frozen=True)
class _Observation:
    at: float                 # monotonic — the window is read against this
    observed_at: str          # what a reader sees
    destination: str          # WHO was called (a base URL)
    failure: Optional[str]    # the class, or None when it answered


@dataclass(frozen=True)
class NetworkVerdict:
    """What the app knows about the connection, from the calls it has actually made."""

    state: str
    reason: str
    observed_at: Optional[str] = None
    destinations: tuple[str, ...] = ()


_OBSERVATIONS: List[_Observation] = []


def _monotonic() -> float:
    """The clock the window is read against — one indirection so a test can drive it."""
    return time.monotonic()


def clear_observations() -> None:
    """Drop every observation (a test's clean start, and the live proof's). Nothing else clears."""
    _OBSERVATIONS.clear()


# The addresses that mean "on THIS machine". A call that never crossed the wire is evidence about
# nothing on the wire: a local daemon answering proves the loopback stack works, and two dead local
# ports are two dead daemons, not a lost connection.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})


def is_loopback_destination(destination: str) -> bool:
    """Whether an address is THIS machine — the line between a local row and one reached over a wire.

    It is the same tiebreaker `provider_location` uses on a row, applied to whatever the caller can
    name: a provider's `base_url` from the memo's write, or the address a turn's call went to. A bare
    service name (`deepseek`) is not loopback, and neither is a LAN address — both are reached over
    the network, which is exactly what the news rule and the verdict are about.
    """
    text = str(destination or "").strip()
    if not text:
        return False
    if "//" not in text:
        text = "//" + text
    try:
        host = (urlparse(text).hostname or "").lower()
    except ValueError:
        return False
    return host in _LOOPBACK_HOSTS


def record_observation(destination: str, failure: Optional[str] = None) -> None:
    """Note how one call to `destination` ended — the ONLY input the network verdict has.

    `failure` is a FAILURE_* class, or None when the call answered. Cheap and synchronous on
    purpose: it runs on the path of a call that may be about to raise, so it must not be able to.

    Every observation is a chance for the verdict to CHANGE, so the connection's own fact is
    re-read here (the bridge's third seam) — a call that fails is the moment the app can first say
    the connection is gone, and it costs no traffic to ask.
    """
    try:
        _OBSERVATIONS.append(
            _Observation(
                at=_monotonic(),
                observed_at=_now_iso(),
                destination=str(destination or ""),
                failure=failure,
            )
        )
        del _OBSERVATIONS[:-_OBSERVATION_CAP]
        _note_network_state()
    except Exception:  # noqa: BLE001 — bookkeeping must never break the call it observes
        logger.debug("availability: could not record an observation", exc_info=True)


def network_verdict() -> NetworkVerdict:
    """The connection's state, from the observations inside the window — never from a new request.

    THE POSITIVE HALF NEEDS NO CORROBORATION, because it is evidence rather than an absence: a body
    that arrived (any status — a 500 is still an answer) or a connection the far side REFUSED both
    prove a packet went out and something on the network replied.

    THE SILENT HALF DOES, and that is the whole point of the rule. One destination that will not
    resolve is that destination's problem until a SECOND, INDEPENDENT one agrees — otherwise a single
    bad name, a hosts entry, or one provider's DNS blip would accuse the user's connection. So `down`
    requires two distinct destinations silent the same way, and anything less stays `unknown` rather
    than guessing (the same discipline as `STATE_UNKNOWN`).
    """
    now = _monotonic()
    # A call to THIS machine is not evidence about the wire (see `is_loopback_destination`), so the
    # verdict reads only what crossed it — a local daemon's answer or its dead port says nothing
    # about the connection the app is riding.
    fresh = [
        o
        for o in _OBSERVATIONS
        if now - o.at <= NETWORK_WINDOW_SECONDS and not is_loopback_destination(o.destination)
    ]
    if not fresh:
        return NetworkVerdict(NETWORK_UNKNOWN, "no call has been observed yet")

    # Only what happened SINCE the last positive evidence is allowed to accuse the connection: a
    # success a minute ago must not be outvoted by two stale failures, and vice versa.
    newest_positive = None
    for index, observation in enumerate(fresh):
        if observation.failure in (None, FAILURE_ANSWERED, FAILURE_REFUSED):
            newest_positive = index
    if newest_positive is not None:
        positive = fresh[newest_positive]
        if newest_positive == len(fresh) - 1:
            return NetworkVerdict(
                NETWORK_UP,
                f"{positive.destination} answered — the connection works",
                positive.observed_at,
                (positive.destination,),
            )
        fresh = fresh[newest_positive + 1:]

    silent = [o for o in fresh if o.failure == FAILURE_UNREACHABLE]
    destinations = tuple(sorted({o.destination for o in silent}))
    latest = fresh[-1].observed_at if fresh else None
    if len(destinations) >= 2:
        return NetworkVerdict(
            NETWORK_DOWN,
            f"{len(destinations)} independent destinations could not be reached — the connection "
            f"looks down",
            latest,
            destinations,
        )
    if destinations:
        return NetworkVerdict(
            NETWORK_UNKNOWN,
            f"{destinations[0]} could not be reached — one destination is not enough to blame the "
            f"connection",
            latest,
            destinations,
        )
    return NetworkVerdict(
        NETWORK_UNKNOWN,
        "only unattributable failures have been observed — no end to point at",
        latest,
    )


# ── THE TRANSITION RULE — what the bridge TELLS the user, and when (the bridge's THIRD seam) ─────
# Three rulings shape this, all the user's own:
#
#   scope   — watch the **local rows** and the **network**; a cloud row is OBSERVED, never probed.
#   traffic — *"the application may run on someones network having unexplained network accesses could
#             cause concern"*: the bridge adds NO traffic of its own.
#   idle    — *"We notify when WE have a problem. We don't go looking for them."*
#
# What those leave is a rule about the CHANGE. The toaster keys its dedupe on `event_id`
# (`frontend/src/hooks/useNotifyBridge.ts`), so the same content at a NEW event toasts again —
# publishing every observation would be a toast every cycle. So a transition is news and a
# re-observation is not, per subject and per FACT: a service's state and the end its failure came from
# are ONE fact between them, because they are what the sentence is made of.
#
# AND THE FIRST SIGHT OF A PROBLEM SPEAKS (the user, 2026-10-14: *"First sight publishes when the
# first sight IS the problem"*). The other reading — a cold app silent about a service it finds
# already down — would suppress the alert a user most needs until the service RECOVERED, and would
# then announce a recovery from an outage nobody was told about. So a first look that finds a problem
# speaks; a first look that finds things FINE is silent (a cold cache must not announce six "up"s);
# and a change of any kind speaks.
#
# THE NEWS RULE outranks the transition (the page's own words): a service reached over the wire that
# cannot be reached WHILE THE CONNECTION IS DOWN is the network's story, not its own — the network's
# transition is the news, and publishing the provider's would send the reader to the wrong end. A
# suppressed fact is left UNJUDGED (not stored), so the next observation is compared against the last
# fact the user was actually TOLD: a recovery nobody was told about stays unannounced.

FACT_NETWORK = "network"                 # the connection's own subject — the ruling's second watch
PROVIDER_STATE_KIND = "provider-state"   # the `notify:<kind>` these warnings ride

# subject -> the fact last ANNOUNCED. THE BRIDGE'S MEMORY, and deliberately not the memo: the memo is
# a TTL'd probe result that a turn may not pay for, while this is what the user has been told. They
# answer different questions — a turn's failed call is evidence about a service without being a probe,
# and a fact the user was never told must not become the baseline a recovery is read against.
_FACTS: Dict[str, str] = {}
_FACTS_LOCK = threading.RLock()


def announced_fact(subject: str) -> Optional[str]:
    """The fact the bridge last told the user about a subject — `None` when it has said nothing."""
    with _FACTS_LOCK:
        return _FACTS.get(subject)


def clear_facts() -> None:
    """Forget every announced fact — a test's clean start, and the live proof's. Nothing else clears."""
    with _FACTS_LOCK:
        _FACTS.clear()


def _publish(title: str, message: str) -> None:
    """Hand ONE warning to the app's bus. Never raises: a toast must not break a probe or a turn."""
    try:
        from app.domain.messaging.services import publish_warning

        publish_warning(title, message, kind=PROVIDER_STATE_KIND)
    except Exception:  # noqa: BLE001 — the notification is the last step, never the load-bearing one
        logger.debug("availability: could not publish a state change", exc_info=True)


def _state_copy(name: str, state: str, reason: str, model: Optional[str], local: bool) -> tuple[str, str]:
    """The (title, message) a state change is announced with — from THIS module's own wording.

    The sentence is the reason the module already owns for that state or failure class, so a warning
    and the badge a page shows cannot describe one service in two vocabularies. Only the cloud half
    carries the app's diagnosis offer (`failure_statement.EXA_DIAGNOSIS_OFFER`): a local daemon that
    is not running is something the reader settles here — start it, or accept the swap-away — and
    offering an outside diagnosis for a dead loopback port is the wrong next move. Nothing here
    recommends a model, which is the statement contract's other half.
    """
    clause = (reason or "").strip().rstrip(".")
    label = model_subject(model, name) if model else name
    if state == STATE_AVAILABLE:
        title = f"{name} is running again" if local else f"{name} is answering again"
        return title, f"{label} — {clause}." if clause else f"{label} is answering."
    title = f"{name} is not running" if local else f"{name} is not answering"
    message = f"{label} — {clause}." if clause else f"{label} is not answering."
    if not local:
        message = f"{message} {EXA_DIAGNOSIS_OFFER}"
    return title, message


def _announce(
    subject: str,
    fact: str,
    *,
    problem: bool,
    title: str,
    message: str,
    suppressible: bool,
) -> bool:
    """Publish `fact` about `subject` if the ruling says it is news — THE ONE RULE.

    Every producer goes through here (the memo's write, a real call's outcome, the connection
    verdict), so no two of them can drift about what counts as news. `problem` is whether this fact
    IS the problem — the first-sight clause speaks only for those. `suppressible` is the news rule's
    door: `True` for a service reached over the wire, `False` for a local row and for the connection
    itself, whose failures are nobody else's story.
    """
    with _FACTS_LOCK:
        seen = _FACTS.get(subject)
        if seen == fact:
            return False                                  # a re-observation is not news
        if suppressible and problem and network_verdict().state == NETWORK_DOWN:
            return False                                  # left UNJUDGED — see the section note
        _FACTS[subject] = fact
    if seen is None and not problem:
        return False                                      # a first look that finds things fine
    _publish(title, message)
    return True


def _fact_of(state: str, failure: Optional[str]) -> str:
    """A service's fact: its state, plus WHICH END it failed at — the two halves the copy is made of."""
    return f"{state}|{failure or ''}"


def _note_provider_fact(
    name: str,
    state: str,
    *,
    reason: str,
    failure: Optional[str] = None,
    model: Optional[str] = None,
    local: bool = False,
) -> bool:
    """Announce what a READ — or a real call — found about ONE service.

    `local` is the news rule's other half: a daemon on this machine cannot have been cut off by the
    connection, so its failure is always its own news.
    """
    title, message = _state_copy(name, state, reason, model, local)
    return _announce(
        f"provider:{name}",
        _fact_of(state, failure),
        problem=state == STATE_DOWN,
        title=title,
        message=message,
        suppressible=not local,
    )


def _note_network_state() -> bool:
    """Announce the CONNECTION's own fact, from the verdict the observations have earned.

    Only the two DECIDED states are announced and only they are STORED: `unknown` is the app saying
    it does not know, and "the connection works" is not a claim an unreadable stretch supports. Not
    storing it is what keeps a `down` after an unreadable stretch the change it is, and a second
    `down` after one from being re-toasted.
    """
    verdict = network_verdict()
    if verdict.state == NETWORK_UNKNOWN:
        return False
    problem = verdict.state == NETWORK_DOWN
    return _announce(
        FACT_NETWORK,
        verdict.state,
        problem=problem,
        title="The connection looks down" if problem else "The connection works",
        message=((verdict.reason or "").strip().rstrip(".") + "."),
        suppressible=False,
    )


# ── THE SECOND PRODUCER — the traffic the app was sending anyway ─────────────────────────────────
# The verdict above and the provider facts below both need observations, and the ruling allows the
# bridge NO traffic of its own. So the funnel every chat call already passes through
# (`api/v1/chat/llm_utils.acompletion_with_retry`) reports what each real call did — it is the one
# place a turn's call is visible, and reporting from there costs nothing.
#
# THE KNOWN GAP, stated rather than papered over: a STREAMED call returns its iterator BEFORE its
# chunks, so a failure that arrives MID-STREAM surfaces in the consumer and is not observed here.
# What is observed is a stream that fails to OPEN — a dead endpoint, a refused connection, a rejected
# key — which is also where a turn's chain walk does its failover.
#
# A call that named NO row (the `/completions` passthrough, which takes a raw model string) is still
# observed — it is traffic — but nobody is accused: a fact needs a subject.

# The classes that mean "no answer arrived", for the SERVICE's own fact. `answered` is deliberately
# not one: a 429 or a 401 IS a reply, and a service that answered badly is not a service that is
# down — the per-turn copy already speaks for those.
_SILENT_FAILURES = frozenset({FAILURE_UNREACHABLE, FAILURE_REFUSED, FAILURE_TIMEOUT})


def note_call_outcome(
    destination: str,
    *,
    failure: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Report ONE real call the app just made — the bridge's second producer.

    `failure` is a FAILURE_* class, or None when the call answered (`classify_call_error` reads it off
    the exception for a caller that has one). `provider` is the ROW the call was made against, when
    the caller knows it; `model` is the model it asked for, which the copy degrades to a readable name
    (`failure_statement.model_subject`).

    The observation is recorded FIRST, so the connection's fact is judged with THIS call included —
    which is the whole point: a turn's failure is traffic, and traffic is all the verdict has. Never
    raises (a report must not break the call that earned it), and it adds no traffic of its own.

    The fact it announces is NOT written to the memo. The memo is a probe result and the pre-turn
    refusal's only allowed read (`refusal.py`, *"a turn never pays a probe"*); a turn's failure is a
    different and stronger kind of evidence, so it moves what the app has TOLD the user without
    pretending a probe ran.
    """
    record_observation(destination, failure=failure)
    if not provider:
        return                                            # traffic, but no subject to accuse
    if failure is None:
        state: str = STATE_AVAILABLE
        reason = "the service answered a call"
    elif failure in _SILENT_FAILURES:
        state = STATE_DOWN
        reason = _cloud_failure_reason(failure)           # the module's per-class sentence
    else:
        return                                            # the far side answered — see above
    _note_provider_fact(
        provider,
        state,
        reason=reason,
        failure=failure if state == STATE_DOWN else None,
        model=model,
        local=is_loopback_destination(destination),
    )


# ── The primitives (moved from `local_occupancy_service`, verbatim) ──────────────────────────────

def join_probe_url(base_url: str, path: str) -> str:
    """Join a probe path to a base URL without doubling — or missing — the API root.

    A resolved endpoint is **the API root the app dials** (2026-10-11, the `ollama_cloud` ruling), and
    a path that belongs to a DIFFERENT root of the same service must be composed against that root
    rather than pasted onto this one. Two cases, one rule:

    * **The openai-compat paths.** Managed local base_urls carry the litellm-style trailing /v1
      (http://127.0.0.1:8080/v1) while the openai-compat probe paths also start with /v1 — a blind
      join produced /v1/v1/models and a live daemon read as down (2026-09-09, Exa's find). When the
      base already IS the API root, the path's leading /v1 is dropped.
    * **The native Ollama paths** (/api/*). Those never live under the compat root: measured on
      ollama.com, /api/tags answers 200 while /v1/api/tags answers 404. A native path is composed
      against the NATIVE root, so a row carrying the compat root still reaches its listings and its
      key check.
    """
    base = base_url.rstrip("/")
    p = path
    if p.startswith("/api/"):
        base = native_root(base)
    elif base.endswith("/v1") and p.startswith("/v1"):
        p = p[len("/v1"):]
    if p and not p.startswith("/"):
        p = "/" + p
    return f"{base}{p}"


@dataclass(frozen=True)
class ProbeOutcome:
    """What a probe got, and — when it got nothing — WHICH END the silence came from.

    `payload` is the JSON body, or None. `failure` is one of the FAILURE_* classes when no payload
    arrived. They are ONE value on purpose: a caller that read its payload from one request and its
    class from another would be describing two different probes.
    """

    payload: Optional[Dict[str, Any]] = None
    failure: Optional[str] = None


def _outcome(result: Any) -> ProbeOutcome:
    """Whatever `probe_json` returned, as a `ProbeOutcome`.

    The test doubles answer with a BARE payload (or None), because they stand in for the transport
    rather than for the classification: a bare dict reads as "it answered", and a bare None as "it
    did not answer, for a reason this stand-in does not model" (`failure=None`). Reading through here
    is what lets one implementation of the request serve the callers and the doubles alike.
    """
    if isinstance(result, ProbeOutcome):
        return result
    return ProbeOutcome(payload=result)


async def probe_json(
    base_url: str, path: str, headers: Optional[Mapping[str, str]] = None
) -> ProbeOutcome:
    """GET base_url+path with the short timeout, and name WHICH END a failure came from.

    `headers` is only passed through when it is non-empty, so the plain reachability probe is a
    bare GET (which is also what the occupancy tests' stand-in client accepts). The class rides the
    return value because it is a fact about THIS request — the user's end and the provider's end both
    used to arrive here as the same `None`.
    """
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
            url = join_probe_url(base_url, path)
            if headers:
                response = await client.get(url, headers=dict(headers))
            else:
                response = await client.get(url)
            response.raise_for_status()
            payload: dict = response.json()
            record_observation(base_url, failure=None)
            return ProbeOutcome(payload=payload)
    except Exception as exc:  # noqa: BLE001 — any probe failure = the service did not answer
        failure = classify_probe_error(exc)
        logger.debug("availability probe failed %s%s (%s): %s", base_url, path, failure, exc)
        record_observation(base_url, failure=failure)
        return ProbeOutcome(failure=failure)


# ── The key check: the question a LISTING cannot answer ──────────────────────────────────────────
#
# On ollama.com EVERY listing is ungated. Measured: `/api/tags` answers 200 with no key at all, and
# the OpenAI-compat `/v1/models` answers 200 to a deliberately fake one. So "the models listed" means
# the endpoint is reachable and NOTHING about whether the key works — a test built on a listing stays
# green through a dead key. The one gated operation is inference (`/api/chat` -> 401 with no key), so
# the honest check is the smallest possible completion.
#
# It is `verify_key`-only, never a page's read: this spends a real request against the account's
# usage, and a badge refresh is not a reason to do that. The explicit Test button is.
OLLAMA_CHAT_PATH = "/api/chat"
KEY_PROBE_TIMEOUT = 15.0
KEY_PROBE_MAX_TOKENS = 1


async def probe_key_accepted(base_url: str, key: str, model: str) -> Optional[bool]:
    """Whether this service ACCEPTS `key` — True, False (refused), or None (unknown).

    None is the answer for every case that is not a verdict: no model to name, a timeout, a 5xx.
    A refusal is 401/403 — the same statuses a dead key produces on the inference path — and the
    caller turns that into a CONFIGURATION state rather than an outage, because a rejected key is
    something to fix, not something to wait on.
    """
    if not model:
        return None
    try:
        async with httpx.AsyncClient(timeout=KEY_PROBE_TIMEOUT) as client:
            response = await client.post(
                join_probe_url(base_url, OLLAMA_CHAT_PATH),
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "options": {"num_predict": KEY_PROBE_MAX_TOKENS},
                },
            )
    except Exception as exc:  # noqa: BLE001 — an unreachable probe is not a refusal
        logger.debug("availability key probe failed %s: %s", base_url, exc)
        return None
    if response.status_code in (401, 403):
        return False
    if response.status_code < 400:
        return True
    logger.debug("availability key probe: %s -> HTTP %s", base_url, response.status_code)
    return None


def is_ollama(provider_type: str) -> bool:
    return provider_type == "ollama"


def env_key(provider_type: str) -> Optional[str]:
    """The env-var fallback for a cloud row whose key is not in the secrets store.

    Moved with the rest of the provider-test logic (the old `POST /providers/config/{id}/test`
    handled this inline): a row's OWN stored key wins, and this covers the "configured by
    environment" case. Absent for a local or unknown type.
    """
    try:
        from app.core.config import get_settings

        settings = get_settings()
    except Exception:  # noqa: BLE001 — no settings is not a connectivity failure
        return None
    attr = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "deepseek": "deepseek_api_key",
    }.get(provider_type or "")
    value = getattr(settings, attr, None) if attr else None
    return str(value) if value else None


async def served_models(provider: Mapping[str, Any]) -> List[str]:
    """What the service serves RIGHT NOW (the loaded model / the catalogue)."""
    base = provider.get("base_url") or ""
    if is_ollama(provider.get("provider_type", "")):
        ps = _outcome(await probe_json(base, OLLAMA_PS_PATH)).payload
        if ps:
            return [m.get("model", "") for m in ps.get("models", []) if m.get("model")]
        return []
    # openai-compatible (llama.cpp etc.): /v1/models lists what it has
    models = _outcome(await probe_json(base, OPENAI_MODELS_PATH)).payload
    if models:
        return [m.get("id", "") for m in models.get("data", []) if m.get("id")]
    return []


async def is_reachable(provider: Mapping[str, Any]) -> bool:
    """Whether the service answers at all (the short-timeout probe)."""
    base = provider.get("base_url") or ""
    if is_ollama(provider.get("provider_type", "")):
        return _outcome(await probe_json(base, OLLAMA_TAGS_PATH)).payload is not None
    return _outcome(await probe_json(base, OPENAI_MODELS_PATH)).payload is not None


# ── The payload ──────────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Availability:
    """One service's state, the reason a reader can act on, and WHEN it was checked."""

    provider_id: Optional[int]
    name: str
    state: str
    reason: str
    checked_at: str
    models_served: tuple[str, ...] = ()
    latency_ms: Optional[float] = None
    # `verify_key`-only: True/False when the key was exercised, None when nobody asked. It rides the
    # payload rather than the state, so a reader can tell "reachable, key unchecked" from "reachable,
    # key accepted".
    key_accepted: Optional[bool] = None
    # WHICH END it failed at, when it failed — a FAILURE_* class, or None when it answered (or when
    # nobody classified the failure). The STATE says it cannot answer; this says whose problem that
    # is, which is the question a reader actually has and the one the copy used to answer wrongly.
    failure: Optional[str] = None
    # THE ROW-vs-PROTOCOL REPORT (2026-10-11, the `ollama_cloud` ruling's *"report, then offer"*):
    # a service can answer perfectly and still be dialled one directory outside its API. The clause
    # names what will be dialled and what to set — nothing ever applies it. `provider_endpoints
    # .compat_root_offer` owns the knowledge; this carries it to the surfaces a reader uses.
    note: Optional[str] = None

    @property
    def available(self) -> Optional[bool]:
        """True / False / None — None only when nothing has been checked (`unknown`).

        `down-by-occupancy` and `unconfigured` are BOTH False: neither can answer. The `reason` is
        what tells the reader why, and that is the part they can act on.
        """
        if self.state == STATE_UNKNOWN:
            return None
        return self.state == STATE_AVAILABLE


# ── The classification ───────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _LocalProbe:
    """One local daemon's raw probe result, before the occupancy classification."""

    provider_id: Optional[int]
    name: str
    reachable: bool
    models: tuple[str, ...] = ()
    latency_ms: Optional[float] = None


async def _probe_local(provider: Mapping[str, Any]) -> _LocalProbe:
    """Probe one local daemon: does it answer, and what does it hold?"""
    started = time.monotonic()
    reachable = await is_reachable(provider)
    models: tuple[str, ...] = ()
    if reachable:
        models = tuple(await served_models(provider))
    latency = (time.monotonic() - started) * 1000
    return _LocalProbe(
        provider_id=provider.get("id"),
        name=str(provider.get("name") or ""),
        reachable=reachable,
        models=models,
        latency_ms=round(latency, 2),
    )


def _local_state(probe: _LocalProbe, any_running: bool) -> str:
    if probe.reachable:
        return STATE_AVAILABLE
    return STATE_DOWN_BY_OCCUPANCY if any_running else STATE_DOWN


def _short(model: str) -> str:
    """A served model as a READER names it — the filename, never the server's absolute path.

    llama.cpp's single-model mode reports the `-m` path it was launched with, so a raw served id can
    BE such a path rather than a model name. An absolute path in user-facing copy is the defect the
    local-provider page already carries (banked: THE LOCAL RUNTIME SELECTOR — router mode fixes it at
    the source); this read must not spread it to a second surface.
    """
    name = model.rstrip("/").split("/")[-1]
    return name or model


def _local_reason(state: str, probe: _LocalProbe) -> str:
    if state == STATE_AVAILABLE:
        served = ", ".join(_short(m) for m in probe.models) if probe.models else "nothing yet"
        return f"the local server is running and serves {served}"
    if state == STATE_DOWN_BY_OCCUPANCY:
        return (
            "the local server is not running, but another local server owns the GPU — "
            "this is a swap-away, not a fault"
        )
    return "the local server is not running and no local server answers"


def _endpoint_root_note(provider: Mapping[str, Any]) -> Optional[str]:
    """The ROW-vs-PROTOCOL report, when a hybrid type's row carries the service's NATIVE root.

    The knowledge lives in `provider_endpoints.compat_root_offer`; this renders it into the `reason` a
    reader sees — the provider test cards and the capability read-out both print that string, so the
    report reaches the surfaces where the row is configured, not only the log.

    Say WHAT will be dialled and WHAT to set; never touch the row. The user ruled *"report, then
    offer"* (2026-10-11): the app reports, and the value stays the user's to change.
    """
    base = str(provider.get("base_url") or "").rstrip("/")
    offer = compat_root_offer(str(provider.get("provider_type") or ""), provider.get("base_url"))
    if not offer:
        return None
    return (
        f"this row carries the service's NATIVE root ({base}) where the app dials the "
        f"OpenAI-compatible one — a completion goes to {base}/chat/completions; "
        f"set the row's endpoint to {offer}"
    )


def _cloud_failure_reason(failure: Optional[str]) -> str:
    """The sentence for a cloud row that did not answer — naming the END when the class knows one.

    The classes are `classify_probe_error`'s; the fallback is the sentence this module has always
    used, so an unclassified failure reads exactly as it did before and no surface loses its copy.
    A reader's next move differs by end: the network is theirs to fix, the provider's is to wait on
    (or to fail over), and the key is a row to correct.
    """
    if failure == FAILURE_UNREACHABLE:
        return "this machine could not reach it — the network looks down"
    if failure == FAILURE_REFUSED:
        return "the connection was refused"
    if failure == FAILURE_ANSWERED:
        return "the provider answered with an error"
    if failure == FAILURE_TIMEOUT:
        return "the provider did not answer in time"
    return "the provider did not answer"


async def _probe_cloud(
    provider: Mapping[str, Any],
    key_for: Optional[Callable[[Mapping[str, Any]], Awaitable[Optional[str]]]],
    *,
    verify_key: bool = False,
) -> Availability:
    """Probe a non-local row: reachability with its own key, plus what it catalogues.

    `verify_key` adds the ONE question a listing cannot answer — see `probe_key_accepted`. It is off
    by default because it spends a real inference request; the explicit Test button asks for it.
    """
    name = str(provider.get("name") or "")
    provider_id = provider.get("id")
    started = time.monotonic()

    key: Optional[str] = None
    if key_for is not None:
        try:
            key = await key_for(provider)
        except Exception as exc:  # noqa: BLE001 — a key lookup failure is not a connectivity one
            logger.warning("availability: key lookup failed for %s: %s", name, exc)
    if not key:
        key = env_key(str(provider.get("provider_type") or ""))
    if not key:
        # A row with no key cannot be attempted — but that is CONFIGURATION, not an outage, and
        # calling it "unreachable" would send the reader after the wrong thing.
        return Availability(
            provider_id=provider_id,
            name=name,
            state=STATE_UNCONFIGURED,
            reason="no API key is configured",
            checked_at=_now_iso(),
        )

    outcome = _outcome(
        await probe_json(
            provider.get("base_url") or "",
            OPENAI_MODELS_PATH,
            headers={"Authorization": f"Bearer {key}"},
        )
    )
    payload = outcome.payload
    latency = round((time.monotonic() - started) * 1000, 2)
    if payload is None:
        return Availability(
            provider_id=provider_id,
            name=name,
            state=STATE_DOWN,
            reason=_cloud_failure_reason(outcome.failure),
            checked_at=_now_iso(),
            latency_ms=latency,
            failure=outcome.failure,
        )
    models = tuple(m.get("id", "") for m in payload.get("data", []) if m.get("id"))

    # The row-vs-protocol report rides WHATEVER reason this read ends on (see `_endpoint_root_note`),
    # AND as its own field: a card builds its own sentence, so a report that only lived in `reason`
    # would be invisible exactly where things look fine (`test_card`).
    note = _endpoint_root_note(provider)

    key_accepted: Optional[bool] = None
    reason = f"the provider answers and catalogues {len(models)} model(s)"
    if verify_key:
        # THE LISTING PROVED REACHABILITY, NOT THE KEY (`probe_key_accepted`). Ask the one gated
        # operation, and report a refusal as CONFIGURATION — `unconfigured`, not `down` — so the
        # reader is sent to the key rather than to the network, which is answering fine.
        key_accepted = await probe_key_accepted(
            str(provider.get("base_url") or ""), key, models[0] if models else ""
        )
        if key_accepted is False:
            return Availability(
                provider_id=provider_id,
                name=name,
                state=STATE_UNCONFIGURED,
                reason="the service is reachable but REJECTED the API key",
                checked_at=_now_iso(),
                models_served=models,
                latency_ms=latency,
                key_accepted=False,
            )
        if key_accepted is True:
            reason = (
                f"the provider answers, catalogues {len(models)} model(s), "
                "and the API key was accepted"
            )

    if note:
        reason = f"{reason} — {note}"

    return Availability(
        provider_id=provider_id,
        name=name,
        state=STATE_AVAILABLE,
        reason=reason,
        checked_at=_now_iso(),
        models_served=models,
        latency_ms=latency,
        key_accepted=key_accepted,
        note=note,
    )


# ── The cache ────────────────────────────────────────────────────────────────────────────────────

# provider id -> (expires_at_monotonic, Availability). In-process and deliberately small: this is a
# memo of a probe, not a store. `clear()` exists so a test (or a forced refresh) starts clean.
_CACHE: Dict[int, "tuple[float, Availability]"] = {}


def clear_cache() -> None:
    """Drop every memo. The live proof and the tests both need a cold start."""
    _CACHE.clear()


def cached(provider_id: int) -> Optional[Availability]:
    """The cached state for a provider, or None when it is missing or stale.

    This is the ONLY read a turn may make: the pre-turn refusal asks this and never probes.
    """
    entry = _CACHE.get(provider_id)
    if entry is None:
        return None
    expires_at, availability = entry
    if expires_at <= time.monotonic():
        return None
    return availability


def cached_by_name(name: str) -> Optional[Availability]:
    """The cached state for a provider NAME — the handle an agent's declared candidate carries.

    The memo is keyed by provider ID (that is what a row has), but the chat chain's primary for a
    DECLARING agent is the agent's own ``provider`` name with no row id resolved onto it
    (`capabilities._candidate_from_agent`), so a consumer asking "can this turn run?" has to ask by
    name in that case. It reads the SAME memo — this is not a second cache and it never probes.
    """
    now = time.monotonic()
    for expires_at, availability in _CACHE.values():
        if expires_at > now and availability.name == name:
            return availability
    return None


async def read_availability(
    providers: Sequence[Mapping[str, Any]],
    *,
    key_for: Optional[Callable[[Mapping[str, Any]], Awaitable[Optional[str]]]] = None,
    force: bool = False,
    verify_key: bool = False,
) -> Dict[str, Availability]:
    """Read the state of every provider given, keyed by NAME — the handle a candidate carries.

    Probes run CONCURRENTLY and only for the rows whose memo is missing or stale (or for all of
    them when `force`). Pass every provider the answer depends on: the occupancy classification
    needs the LOCAL rows as a set, because "down-by-occupancy" is a fact about the group, not about
    one daemon.

    `verify_key` additionally asks whether each cloud row's key is ACCEPTED — see
    `probe_key_accepted` for why a listing cannot answer that. Off by default: it is a real inference
    request, so only an explicit test should ask for it.
    """
    now = time.monotonic()
    out: Dict[str, Availability] = {}
    stale: List[Mapping[str, Any]] = []
    for provider in providers:
        provider_id = provider.get("id")
        memo = None
        if provider_id is not None and not force:
            entry = _CACHE.get(provider_id)
            if entry is not None and entry[0] > now:
                memo = entry[1]
        if memo is not None:
            out[memo.name] = memo
        else:
            stale.append(provider)

    if not stale:
        return out

    local_batch = [p for p in stale if is_local(p)]
    cloud_batch = [p for p in stale if not is_local(p)]

    fresh: List[Availability] = []

    if local_batch:
        probes = await asyncio.gather(*[_probe_local(p) for p in local_batch])
        # The occupancy context: does ANY local daemon in this pass answer? A sibling already in
        # the memo counts too — otherwise a cached "healthy" would not protect a fresh "down".
        any_running = any(p.reachable for p in probes) or any(
            av.state == STATE_AVAILABLE
            for av in out.values()
        )
        for probe in probes:
            state = _local_state(probe, any_running)
            fresh.append(
                Availability(
                    provider_id=probe.provider_id,
                    name=probe.name,
                    state=state,
                    reason=_local_reason(state, probe),
                    checked_at=_now_iso(),
                    models_served=probe.models,
                    latency_ms=probe.latency_ms,
                )
            )

    if cloud_batch:
        fresh.extend(
            await asyncio.gather(
                *[_probe_cloud(p, key_for, verify_key=verify_key) for p in cloud_batch]
            )
        )

    expires_at = time.monotonic() + DEFAULT_TTL_SECONDS
    # THE BRIDGE'S OBSERVATION POINT (seam 3): the memo's write is where every probe's answer lands,
    # so it is where a CHANGE becomes visible — for the local rows the poll watches and for the cloud
    # rows a page observes. Announcing from here rather than from the probe keeps the class seam's own
    # answer to "is this row local?" (`is_local`) instead of a second opinion about it.
    local_by_name = {str(p.get("name") or ""): is_local(p) for p in providers}
    for availability in fresh:
        out[availability.name] = availability
        if availability.provider_id is not None:
            _CACHE[availability.provider_id] = (expires_at, availability)
        _note_provider_fact(
            availability.name,
            availability.state,
            reason=availability.reason,
            failure=availability.failure,
            local=local_by_name.get(availability.name, False),
        )
    return out


def is_local(provider: Mapping[str, Any]) -> bool:
    """Whether this row is a LOCAL-class service — the house seam, not a second opinion.

    `provider_location` is what the A1 split and the resolver both use (the cloud whitelist plus a
    loopback tiebreaker), so an availability read and a resolution can never disagree about which
    class a row is in. Falls back to the ollama type when the seam cannot be reached (a bare dict
    from a test).
    """
    try:
        from app.domain.providers.provider_classes import provider_location

        location = provider.get("location") or provider_location(
            str(provider.get("provider_type") or ""), provider.get("base_url")
        )
        return location == "local"
    except Exception:  # noqa: BLE001 — never let the classification itself be the failure
        return is_ollama(str(provider.get("provider_type") or ""))


async def read_availability_for(
    db: Any,
    resolutions: Sequence[Any] = (),
    *,
    extra_names: Sequence[str] = (),
    force: bool = False,
    verify_key: bool = False,
) -> Dict[str, Availability]:
    """ONE cached, concurrent availability pass over the services the given resolutions name.

    Every LOCAL row joins the pass whether or not a chain names it, because "down-by-occupancy" is
    a fact about the LOCAL SET: without the siblings the classification would call a swap-away an
    incident, and two surfaces — the capability page and an agent's own badge — would then disagree
    about one daemon.

    This is that ONE pass, and it lives here so both surfaces make it through the same code: a
    caller supplies the RESOLUTIONS (it holds the session and has resolved them), or provider NAMES
    it needs regardless of a chain (`extra_names` — the explicit "test this provider" button, which
    has no resolution in hand), and this decides which rows to probe and supplies the stored key per
    row. The rows go through `read_availability`, so the memo this warms is the memo the pre-turn
    refusal reads.

    `force` re-probes: a deliberate test must not answer with a memo from a minute ago, and
    refreshing the shared memo means the badges then agree with what it just found.

    `verify_key` goes to the cloud probes, which is where the key lives — the "test this provider"
    button is its only caller, and it is the one surface that SHOULD spend an inference request to
    find out whether the key works.
    """
    from app.domain.providers.config_service import ProviderConfigService

    service = ProviderConfigService()
    providers = await service.list_providers(db, include_inactive=False)
    rows: Dict[str, Dict[str, Any]] = {row["name"]: row for row in _provider_rows(providers)}

    needed: Dict[str, Dict[str, Any]] = {}
    for resolution in resolutions:
        for candidate in resolution.candidates:
            if candidate.provider and candidate.provider in rows:
                needed[candidate.provider] = rows[candidate.provider]
    for name in extra_names:
        if name in rows:
            needed[name] = rows[name]
    for name, row in rows.items():
        if is_local(row):
            needed.setdefault(name, row)

    async def key_for(provider: Mapping[str, Any]) -> Optional[str]:
        provider_id = provider.get("id")
        if provider_id is None:
            return None
        return await service.get_api_key(db, int(provider_id))

    return await read_availability(
        list(needed.values()), key_for=key_for, force=force, verify_key=verify_key
    )


# ── THE POLL — the bridge's IDLE path, and the ONE scope the ruling allows ───────────────────────
#
# Why a timer at all: an outage is only news when somebody was watching. A page load or a turn
# observes a service and the memo's write announces the change — so an IDLE app says nothing about a
# daemon that died ten minutes ago, and the pre-turn REFUSAL reads the memo only ("a turn never pays
# a probe"), which makes a cold cache refuse nothing at all. A minute-tick read answers both.
#
# It is compatible with "no unexplained network access" for exactly one reason: what it probes never
# leaves the host. THE SCOPE IS THE RULING (the user, 2026-10-14) — the rows whose address is THIS
# MACHINE. A local-class row that is NOT loopback (`provider_location` counts "any LAN daemon" as
# local) is deliberately left to the traffic the user already causes: a page's read and a turn still
# observe it, and the app puts no packet of its own on somebody's network. Widening this is a
# per-row decision, never a default.

IDLE_POLL_JOB_ID = "availability-idle-poll"
IDLE_POLL_BOOT_JOB_ID = "availability-idle-poll-boot"
# Every minute. The read's own TTL (60s) decides whether a tick PAYS a probe, so the timer and the
# cache agree rather than argue; APScheduler's cron has no finer step anyway.
IDLE_POLL_CRON = "* * * * *"
# The first look happens HERE rather than at the next minute boundary: a service this machine hosts
# is announced (the first-sight clause) as the app comes up, and the memo is warm before the first
# turn. A delay, not a blocking probe — the boot path stays uncluttered and the probe is a loopback
# GET.
IDLE_POLL_BOOT_DELAY_SECONDS = 10


def _provider_rows(providers: Sequence[Any]) -> List[Dict[str, Any]]:
    """The mapping shape every read works on — ONE builder, so no caller invents its own."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "display_name": getattr(p, "display_name", None),
            "provider_type": p.provider_type,
            "base_url": p.base_url,
            "location": getattr(p, "location", None),
        }
        for p in providers
    ]


def pollable_rows(providers: Sequence[Any]) -> List[Dict[str, Any]]:
    """The rows the POLL may probe: this machine's own services, and nothing else.

    Both conditions are load-bearing. LOCAL-class, so the pass can never route a row into the cloud
    probe — which needs a key and reports CONFIGURATION states nobody asked it to refresh. And
    LOOPBACK, because that is the line between a probe that never leaves the host and one that shows
    up on somebody's network.
    """
    return [
        row
        for row in _provider_rows(providers)
        if is_local(row) and is_loopback_destination(str(row.get("base_url") or ""))
    ]


async def poll_local_rows() -> Dict[str, Availability]:
    """ONE idle pass over the services this machine hosts — through the SAME read a page makes.

    That sameness is the point: the memo this warms is the memo the pre-turn refusal reads, and a
    change a page would have seen and a change the poll sees are one event rather than two.

    No `key_for`: every row here is local-class by construction, so no key is ever asked for and no
    cloud probe is ever made — the pass spends nothing but loopback requests.

    Never raises: a maintenance job has no caller to raise to, and the next tick is a minute away.
    """
    from app.core.database import AsyncSessionLocal
    from app.domain.providers.config_service import ProviderConfigService

    try:
        async with AsyncSessionLocal() as db:
            providers = await ProviderConfigService().list_providers(db, include_inactive=False)
            rows = pollable_rows(providers)
            if not rows:
                return {}
            return await read_availability(rows)
    except Exception as exc:  # noqa: BLE001 — a maintenance job's contract is to leave the app up
        logger.warning("⚠️ availability poll: pass failed: %s", exc)
        return {}


def register_idle_poll(scheduler: Any) -> bool:
    """Put the poll on the app's trigger scheduler — ENABLED, and gated by nothing.

    It ships ON and unconfigured, because a bridge that ships switched off is the defect this arc
    exists to close (the RSS monitor's dormancy was diagnosed for exactly that reason). What makes it
    safe to run unasked is its SCOPE, not a flag: it only ever talks to this machine.

    Two jobs: the minute tick, and a one-shot at boot so the first look is not up to a minute late.
    Returns whether the tick was accepted; the boot check is a convenience beside it.
    """
    registered = scheduler.add_maintenance_job(
        IDLE_POLL_JOB_ID,
        IDLE_POLL_CRON,
        poll_local_rows,
        "Availability poll (this machine's services only)",
    )
    scheduler.schedule_once(
        IDLE_POLL_BOOT_JOB_ID,
        poll_local_rows,
        delay_seconds=IDLE_POLL_BOOT_DELAY_SECONDS,
    )
    return bool(registered)


# ── The provider-Test card, rendered from the ONE read ───────────────────────────────────────────
#
# Three endpoints answer "test this provider" (`/providers/config/{id}/test`,
# `/providers/managed/{id}/test`, and the legacy `/providers/{id}/test`) and each used to carry its
# own inline probe. They now all RENDER the same read through here, so no two of them can describe
# one daemon differently.
#
# The four-word vocabulary is the CARDS' own and predates the availability states (the frontend's
# branches key on it), so the mapping is deliberate rather than incidental: a `down-by-occupancy`
# is a swap-away to the read and an "unreachable" to this card.

TEST_STATUS_BY_STATE: Dict[str, str] = {
    STATE_AVAILABLE: "connected",
    STATE_DOWN: "unreachable",
    STATE_DOWN_BY_OCCUPANCY: "unreachable",
    STATE_UNCONFIGURED: "not_configured",
    STATE_UNKNOWN: "error",
}


def test_card(availability: Availability, label: str) -> Dict[str, Any]:
    """The Test button's card's FIELDS, from one availability reading.

    A dict rather than a model because each router owns its own `ProviderTestResponse`; the fields
    are the shared thing. `state` and `checked_at` ride along so a caller can have the read's own
    finer answer and WHEN it looked.
    """
    if availability.state == STATE_AVAILABLE:
        served = len(availability.models_served)
        message = f"{label} is running" + (f" with {served} model(s)" if served else "")
        # The key verdict rides along when a Test asked for it: "reachable" and "your key works" are
        # two answers, and a card that only says the first is why a dead key reads as healthy.
        if availability.key_accepted is True:
            message += " — API key accepted"
        # THE ROW-vs-PROTOCOL REPORT: reachable is not the same as dialled correctly, and this card is
        # one of the two places the report reaches a reader. The message carries it because this
        # branch's message is what the card renders (the `reason` above is the read's own sentence).
        if availability.note:
            message += f" — {availability.note}"
        return {
            "status": "connected",
            "message": message,
            "latency_ms": availability.latency_ms,
            "models_available": served or None,
            "state": availability.state,
            "checked_at": availability.checked_at,
        }
    return {
        "status": TEST_STATUS_BY_STATE.get(availability.state, "error"),
        "message": availability.reason or f"{label} did not answer",
        "latency_ms": availability.latency_ms,
        "models_available": None,
        "state": availability.state,
        "checked_at": availability.checked_at,
    }
