"""WHERE A PROVIDER LIVES — the row's endpoint, else the type's, else a report.

The service-literals arc's #11, on the user's ruling: **row only**. An endpoint on a provider row
IS the decision about which server answers, so it comes from the row; when a row declares none, the
provider TYPE's canonical endpoint (`provider_endpoints`) answers and the omission is LOGGED — the
same house rule the inference path already applies. A type with no canonical endpoint (``openai``,
``anthropic`` — each names a hosted vendor AND any self-hosted server) resolves to NOTHING, and the
caller reports that rather than dialling a guessed address.

What this replaces: `provider.base_url or "http://localhost:11434"` (and the `127.0.0.1:8080/v1`
twin) repeated across the model-discovery paths — an address written into code as a backup. The
live `llama` row declares `127.0.0.1:8080/v1` itself, so those fallbacks never fired here; they were
what a fresh install or a mis-configured row would silently get instead of an answer.

Each resolution goes through `provider_endpoints.resolve_endpoint`, so there is ONE place that knows
the rule and one place that logs the omission.
"""

from __future__ import annotations

import logging

import pytest

from app.domain.providers.config_service import ProviderConfig
from app.domain.providers.provider_endpoints import resolve_endpoint

from tests import conftest as cf


# ── the rule ────────────────────────────────────────────────────────────────


def test_the_rows_own_endpoint_wins():
    assert resolve_endpoint("deepseek", "https://deepseek.internal/v1", "deepseek") == (
        "https://deepseek.internal/v1"
    )


def test_a_row_that_declares_nothing_gets_its_types_canonical_endpoint(caplog):
    with caplog.at_level(logging.WARNING):
        resolved = resolve_endpoint("ollama", None, "ollama")

    assert resolved == "http://localhost:11434"
    reported = [r.getMessage() for r in caplog.records if "declares no base_url" in r.getMessage()]
    assert reported, "the omission must be reported, not passed off as configuration"
    assert "ollama" in reported[0] and "http://localhost:11434" in reported[0]


def test_an_empty_string_is_silence_too(caplog):
    """The API accepts `""` as readily as `None`."""
    with caplog.at_level(logging.WARNING):
        assert resolve_endpoint("groq", "", "groq") == "https://api.groq.com/openai/v1"
    assert [r for r in caplog.records if "declares no base_url" in r.getMessage()]


def test_a_type_with_no_canonical_endpoint_resolves_to_nothing(caplog):
    """`openai` and `anthropic` answer with None: the row has to declare its endpoint, and a caller
    that gets None REPORTS it instead of dialling a guess."""
    with caplog.at_level(logging.WARNING):
        assert resolve_endpoint("openai", None, "llama") is None

    assert [r for r in caplog.records if "declares no base_url" in r.getMessage()]


# ── the discovery path: a row that declares nothing is REPORTED, not guessed ─


@pytest.mark.asyncio
async def test_the_refresh_reports_a_row_that_declares_no_endpoint(monkeypatch, test_session):
    """The `openai`-typed local row (llama.cpp) with no endpoint: used to dial
    `http://127.0.0.1:8080/v1` — an address nobody configured."""
    from app.domain.providers import curated_models_service as cms

    called: list[str] = []

    class _Discovery:
        async def discover_openai_compat_models(self, db, provider_id, base_url, force):
            called.append(base_url)
            return {"total": 0}

    # the module attribute is what the refresh imports at CALL time
    monkeypatch.setattr(
        "app.domain.providers.discovery_service.provider_discovery_service", _Discovery()
    )

    row = ProviderConfig(id=1, name="llama", provider_type="openai", base_url=None)
    reason = await cms.CuratedModelService()._refresh_provider_models(test_session, row)

    assert called == [], "nothing may be dialled when the row declares no endpoint"
    assert reason and "endpoint" in reason.lower()


# ── the API dependency: the row is what the service dials ──────────────────


async def _an_ollama_row(session, base_url: str | None):
    """The `ollama` row this test is about — the COPIED database already carries one.

    This used to be a plain insert, on a docstring that claimed "the test database carries no
    provider rows". It is a copy of a real installation (`conftest`), so `ollama` is normally
    there and the insert is `UNIQUE constraint failed: providers.name` — for the first test a
    worker runs, which is what made it look intermittent. `cf.get_or_create_provider` finds the
    row and restates the values this test declares. Nothing is committed: the session fixture
    rolls it back.
    """
    await cf.get_or_create_provider(
        session,
        name="ollama",
        provider_type="ollama",
        display_name="Ollama (Local)",
        base_url=base_url,
        is_active=True,
        priority=1,
        config={},
    )


@pytest.mark.asyncio
async def test_the_ollama_service_dials_the_address_the_row_declares(test_session):
    from app.api.v1.providers.router import get_ollama_service

    await _an_ollama_row(test_session, "http://127.0.0.1:9999")

    service = await get_ollama_service(test_session)

    assert service.base_url == "http://127.0.0.1:9999"


@pytest.mark.asyncio
async def test_a_row_that_declares_nothing_still_answers_with_the_canonical_endpoint(test_session):
    """The ollama TYPE has a canonical endpoint, so a silent row resolves — and logs."""
    from app.api.v1.providers.router import get_ollama_service

    await _an_ollama_row(test_session, None)

    service = await get_ollama_service(test_session)

    assert service.base_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_no_ollama_row_at_all_is_reported_not_guessed(test_session):
    """The 404 the dependency raises instead of dialling a literal — the same rule as the
    module's test route ("the app must not probe an address nobody configured")."""
    from fastapi import HTTPException

    from app.api.v1.providers.router import get_ollama_service

    with pytest.raises(HTTPException) as raised:
        await get_ollama_service(test_session)

    assert raised.value.status_code == 404


# ── the guard on the service itself ────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_ollama_service_refuses_to_dial_an_unresolved_address():
    """`OllamaService()` with no endpoint must fail loudly — `None/api/tags` is a request to
    nowhere, and it would read as a provider being down."""
    from app.domain.providers.services import OllamaService

    with pytest.raises(RuntimeError, match="endpoint"):
        await OllamaService(base_url=None).list_models()


# ── the DISCOVERY-ONLY clients: a DEFINITION, and the two things that keep it one ───────────
#
# F3 of the service-literals arc KEEPS the three discovery clients' `BASE_URL`s, because they are
# the vendor's own catalog address rather than a decision about who answers a completion. What
# makes that legitimate is measurable, so it is pinned here: (1) no endpoint can get IN — the
# constructor takes an API key only, so no provider row reaches the client; (2) the root cannot
# DRIFT from the registry without a test saying so — for two of the three it is the same address,
# and for deepseek the difference is the deliberate one (`/models` off the host vs the compat root).


def test_a_discovery_client_cannot_be_pointed_at_another_server():
    """The definition claim: an API key is the only way in. A client that grew an endpoint
    parameter would be a client a row could aim elsewhere — i.e. a second decision."""
    import inspect

    from app.domain.providers.deepseek_client import DeepseekClient
    from app.domain.providers.groq_client import GroqClient
    from app.domain.providers.openrouter_client import OpenRouterClient

    for cls in (DeepseekClient, GroqClient, OpenRouterClient):
        params = list(inspect.signature(cls.__init__).parameters)
        assert params == ["self", "api_key"], f"{cls.__name__} grew an endpoint parameter"


def test_the_discovery_clients_roots_agree_with_the_registry():
    """Same vendor, one address: the catalog reader and the dispatch path cannot drift apart."""
    from app.domain.providers.deepseek_client import DeepseekClient
    from app.domain.providers.groq_client import GroqClient
    from app.domain.providers.openrouter_client import OpenRouterClient
    from app.domain.providers.provider_endpoints import canonical_endpoint, native_root

    assert GroqClient.BASE_URL == canonical_endpoint("groq")
    assert OpenRouterClient.BASE_URL == canonical_endpoint("openrouter")

    # DeepSeek is ONE host with two roots: the registry names the OpenAI-compatible one a row-less
    # type resolves to, while this client reads `/models` off the host itself. The bare root is
    # deliberate — pinned so a later reader does not "fix" it into the compat one.
    assert DeepseekClient.BASE_URL == native_root(canonical_endpoint("deepseek") or "")
    assert DeepseekClient.BASE_URL == "https://api.deepseek.com"
