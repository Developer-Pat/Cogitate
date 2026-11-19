"""THE BRIDGE'S POLL — the idle path over the services THIS MACHINE hosts (the fourth seam).

The ruling the scope comes from (the user, 2026-10-14): *"The application may run on someones network
having unexplained network accesses could cause concern"* — and, for the idle case, *"Zero packets,
always"*. A timer that probes is compatible with both for exactly one reason, and these tests exist to
hold that reason down:

* a row is polled only when its address is **the loopback** — a LAN daemon is LOCAL-class (the class
  seam's own words: *"ollama, llama.cpp, any LAN daemon"*) and is still **NOT** polled, because the
  app puts no packet of its own on somebody's network. It is left to the traffic the user already
  causes: a page's read and a turn still observe it;
* the pass goes through the **SAME read a page makes**, which is what makes the memo it warms the
  memo the pre-turn refusal reads — and the refusal reads the memo ONLY, so a cold cache refuses
  nothing;
* it **spends nothing**: every row is local-class by construction, so no key is ever asked for and no
  cloud probe is ever made;
* it **ships enabled and gated by nothing** — two jobs on the app's trigger scheduler, and no setting
  anywhere in the path;
* a failing pass **never raises**: a maintenance job has no caller to raise to.

The probes are monkeypatched — no daemons, no network, no database.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.domain.providers import availability as av

# The four shapes the scope has to tell apart. `location=None` means the row declares nothing and the
# class seam decides (`provider_location`), which is how the app's real rows arrive.
LLAMA = SimpleNamespace(
    id=6, name="llama", display_name="Llama Server",
    provider_type="openai", base_url="http://127.0.0.1:8080/v1", location=None,
)
OLLAMA = SimpleNamespace(
    id=1, name="ollama", display_name="Ollama",
    provider_type="ollama", base_url="http://localhost:11434", location=None,
)
# A daemon on the LAN: LOCAL-class by its type, and the row the poll must never dial.
LAN_OLLAMA = SimpleNamespace(
    id=7, name="workshop-ollama", display_name="Workshop Ollama",
    provider_type="ollama", base_url="http://192.168.1.50:11434", location=None,
)
CLOUD_DEEPSEEK = SimpleNamespace(
    id=3, name="deepseek", display_name="DeepSeek",
    provider_type="deepseek", base_url="https://api.deepseek.com", location=None,
)
# The contradictory row: an address on THIS machine but a stored `location` of cloud. The class seam's
# `is_local` honours the row, so this row would join the CLOUD batch — a key lookup and a
# CONFIGURATION state nobody asked the poll to refresh. The poll takes the intersection, so it stays
# out; nothing else in the app resolves the contradiction either.
LOOPBACK_ROW_DECLARED_CLOUD = SimpleNamespace(
    id=9, name="remote-llama", display_name=None,
    provider_type="openai", base_url="http://127.0.0.1:9000/v1", location="cloud",
)

ALL_ROWS = [OLLAMA, LLAMA, LAN_OLLAMA, CLOUD_DEEPSEEK, LOOPBACK_ROW_DECLARED_CLOUD]

# What the two pollable daemons answer with, keyed the way `probe_json` is called (base_url, path).
ANSWERS: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {
    ("http://127.0.0.1:8080/v1", "/v1/models"): {"data": [{"id": "bonsai-8b"}]},
    ("http://localhost:11434", "/api/tags"): {"models": [{"name": "phi4-mini"}]},
    ("http://localhost:11434", "/api/ps"): {"models": [{"model": "phi4-mini:latest"}]},
}


@pytest.fixture(autouse=True)
def _clean_bridge():
    """The memo, the observation window and the announced facts are process-wide — start and leave
    them empty, so a test that publishes cannot decide the next test's news."""
    av.clear_cache()
    av.clear_observations()
    av.clear_facts()
    yield
    av.clear_cache()
    av.clear_observations()
    av.clear_facts()


@pytest.fixture
def calls() -> List[Tuple[str, str]]:
    """Every probe the pass dialled, in order, as (base_url, path)."""
    return []


@pytest.fixture
def toasts(monkeypatch) -> list:
    """Every warning the bridge handed the app's bus, in order, as (title, message, kind)."""
    import app.domain.messaging.services as messaging

    sent: list = []
    monkeypatch.setattr(
        messaging,
        "publish_warning",
        lambda title, message, kind="provider-fallback": sent.append((title, message, kind)),
    )
    return sent


def _probe_from(answers, seen=None):
    """A `probe_json` stand-in answering per (base_url, path); a missing key = no answer."""

    async def probe(base_url: str, path: str, headers=None):
        if seen is not None:
            seen.append((base_url, path))
        return answers.get((base_url, path))

    return probe


class _Session:
    """The pass opens its own session; nothing inside it is read through the fake."""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


class _FakeConfigService:
    """Stands in for `ProviderConfigService` — the pass builds one, so the rows are on the class."""

    rows: List[Any] = []
    fail: bool = False

    async def list_providers(self, db, include_inactive: bool = True):
        if type(self).fail:
            raise RuntimeError("the database is not answering")
        return list(type(self).rows)


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    """No database, and no real probe: the pass gets a session, the rows, and the stand-in."""
    _FakeConfigService.rows, _FakeConfigService.fail = list(ALL_ROWS), False
    monkeypatch.setattr(
        "app.domain.providers.config_service.ProviderConfigService", _FakeConfigService
    )
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _Session())
    yield
    _FakeConfigService.rows, _FakeConfigService.fail = [], False


# ── THE SCOPE — the ruling, pinned ───────────────────────────────────────────────────────────────

def test_only_this_machines_services_are_pollable() -> None:
    """The intersection: LOCAL-class AND the loopback, which is what keeps the idle timer honest."""
    names = [row["name"] for row in av.pollable_rows(ALL_ROWS)]

    assert names == ["ollama", "llama"], "the LAN daemon and every cloud row stay out"


def test_a_lan_daemon_is_local_class_and_still_never_polled() -> None:
    """The two answers that deliberately differ, named in one place so neither looks like a bug.

    `is_local` answers "is this the user's own service?" — the news rule and the class seam need
    that, and a LAN daemon is. `pollable_rows` answers "may the app touch this while nobody is
    looking?" — and that one is the ruling, so the address decides it.
    """
    lan = {"provider_type": "ollama", "base_url": "http://192.168.1.50:11434"}

    assert av.is_local(lan) is True, "the class seam counts any LAN daemon as local"
    assert av.is_loopback_destination(lan["base_url"]) is False
    assert av.pollable_rows([LAN_OLLAMA]) == [], "and the poll still leaves it alone"


def test_a_row_declaring_cloud_on_a_loopback_address_stays_out() -> None:
    """The poll must never route a row into the CLOUD probe — it needs a key and reports
    configuration states, neither of which is the poll's business."""
    assert av.pollable_rows([LOOPBACK_ROW_DECLARED_CLOUD]) == []


# ── THE PASS — what it dials, what it warms, and what it says ────────────────────────────────────

@pytest.mark.anyio
async def test_the_pass_dials_only_the_loopback(monkeypatch, calls) -> None:
    monkeypatch.setattr(av, "probe_json", _probe_from(ANSWERS, calls))

    result = await av.poll_local_rows()

    assert set(result) == {"llama", "ollama"}, "the two rows this machine hosts"
    assert calls, "it did probe — a poll that dialled nothing would pass this vacuously"
    assert all(av.is_loopback_destination(base) for base, _ in calls), (
        "every request stayed on this machine: " + repr(sorted({b for b, _ in calls}))
    )


@pytest.mark.anyio
async def test_the_pass_reports_what_this_machine_serves(monkeypatch, calls) -> None:
    monkeypatch.setattr(av, "probe_json", _probe_from(ANSWERS, calls))

    result = await av.poll_local_rows()

    assert result["llama"].state == av.STATE_AVAILABLE
    assert result["llama"].models_served == ("bonsai-8b",)
    assert result["ollama"].state == av.STATE_AVAILABLE


@pytest.mark.anyio
async def test_the_pass_warms_the_memo_the_pre_turn_refusal_reads(monkeypatch, calls) -> None:
    """The second-order win, and the reason the timer earns its place: the refusal reads the CACHE
    only (a turn never pays a probe), so before this pass it had nothing to refuse with."""
    monkeypatch.setattr(av, "probe_json", _probe_from(ANSWERS, calls))

    await av.poll_local_rows()

    warmed = av.cached(6)
    assert warmed is not None and warmed.state == av.STATE_AVAILABLE
    assert av.cached_by_name("llama") is warmed, "the same memo a page's read would leave"


@pytest.mark.anyio
async def test_a_dead_daemon_on_this_machine_speaks_on_the_first_pass(
    monkeypatch, calls, toasts
) -> None:
    """The poll is a producer like any other: the memo's write announces, and a first sight that IS a
    problem is news — which is the whole point of watching while nobody is looking."""
    monkeypatch.setattr(av, "probe_json", _probe_from({}, calls))

    await av.poll_local_rows()

    assert sorted(t[0] for t in toasts) == ["llama is not running", "ollama is not running"]
    assert all(t[2] == av.PROVIDER_STATE_KIND for t in toasts)


@pytest.mark.anyio
async def test_a_second_pass_inside_the_ttl_pays_nothing_and_says_nothing(
    monkeypatch, calls, toasts
) -> None:
    """The tick and the cache agree instead of arguing: the read's own TTL decides whether a probe is
    paid, so a minute-timer over a 60s memo is not a probe a minute."""
    monkeypatch.setattr(av, "probe_json", _probe_from({}, calls))
    await av.poll_local_rows()
    first = list(toasts)
    calls.clear()

    await av.poll_local_rows()

    assert calls == [], "the memo answered, so no probe was paid"
    assert toasts == first, "and a re-observation is not news"


@pytest.mark.anyio
async def test_a_failing_pass_does_not_raise(monkeypatch, calls) -> None:
    """A maintenance job has no caller to raise to, and the next tick is a minute away."""
    monkeypatch.setattr(av, "probe_json", _probe_from(ANSWERS, calls))
    _FakeConfigService.fail = True

    assert await av.poll_local_rows() == {}


# ── THE WIRING — it ships ON, and nothing can gate it ────────────────────────────────────────────

class _RecordingScheduler:
    """The two doors the poll uses, and nothing else. `jobs` is what the assertions read."""

    def __init__(self) -> None:
        self.maintenance: list = []
        self.oneshots: list = []
        self.accept = True

    def add_maintenance_job(self, job_id, cron_expression, callback, description=""):
        self.maintenance.append((job_id, cron_expression, callback, description))
        return self.accept

    def schedule_once(self, job_id, callback, delay_seconds=300):
        self.oneshots.append((job_id, callback, delay_seconds))


def test_the_poll_ships_enabled_and_gated_by_nothing() -> None:
    """No setting, no opt-in, no per-row flag: the SCOPE is what makes it safe, not a switch.

    A bridge that ships switched off is the defect this arc exists to close — the RSS monitor's
    dormancy was diagnosed for exactly that reason — so the assertion is that registration happens
    unconditionally and that the job's callback IS the pass.
    """
    scheduler = _RecordingScheduler()

    assert av.register_idle_poll(scheduler) is True

    job_id, cron, callback, description = scheduler.maintenance[0]
    assert job_id == av.IDLE_POLL_JOB_ID
    assert cron == "* * * * *" and len(cron.split()) == 5, "a cron APScheduler will accept"
    assert callback is av.poll_local_rows
    assert "this machine" in description.lower(), "the scope is stated where a reader looks"

    boot_id, boot_callback, delay = scheduler.oneshots[0]
    assert boot_id == av.IDLE_POLL_BOOT_JOB_ID and boot_callback is av.poll_local_rows
    assert delay == av.IDLE_POLL_BOOT_DELAY_SECONDS


def test_a_refused_tick_is_reported_rather_than_hidden() -> None:
    """The scheduler answers False when it cannot take the job; a caller must be able to tell."""
    scheduler = _RecordingScheduler()
    scheduler.accept = False

    assert av.register_idle_poll(scheduler) is False
