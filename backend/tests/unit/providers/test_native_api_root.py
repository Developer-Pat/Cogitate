"""TWO API ROOTS, ONE SERVICE — a native path composes against the NATIVE root.

The ruling (`wiki/issues/resolved/embedded-service-literals/ollama-cloud-two-api-roots.md`, option A): **a provider row's `base_url` names
the API root the app DIALS.** For a type dialled through an OpenAI-compatible client that root is the
compat one — `https://ollama.com/v1` — and the same service's NATIVE API is NOT beneath it: measured on
`ollama.com`, `/api/tags` answers **200** while `/v1/api/tags` answers **404**.

So a consumer that speaks the native protocol derives its root (`provider_endpoints.native_root`)
instead of pasting `/api/*` onto a compat root and dialling outside the service. What this replaces: the
two browsers' `DEFAULT_BASE_URL` class attributes and the discovery service's signature defaults —
addresses nobody configured, kept as a backup under the row's value.

**The row still decides WHERE the service is** (`resolve_endpoint`); nothing here is a second answer to
that. And the LOCAL `ollama` row is deliberately untouched: every consumer of it is native
(`ChatOllama`, litellm's ``ollama_chat`` handler), so `http://localhost:11434` already IS the root the
app dials it at — deriving there would break it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.providers.provider_endpoints import PROVIDER_ENDPOINTS, native_root


# ── the rule ────────────────────────────────────────────────────────────────


def test_a_compat_root_drops_its_v1() -> None:
    assert native_root("https://ollama.com/v1") == "https://ollama.com"


def test_a_bare_host_is_returned_as_it_stands() -> None:
    """The local ollama row is the case that must NOT change."""
    assert native_root("http://localhost:11434") == "http://localhost:11434"


def test_a_trailing_slash_is_not_a_root_of_its_own() -> None:
    assert native_root("https://ollama.com/v1/") == "https://ollama.com"


def test_a_segment_that_merely_ends_in_v1_is_left_alone() -> None:
    """"/v1" is a segment, not a suffix to strip from anything ending in those two characters."""
    assert native_root("https://host/v1beta") == "https://host/v1beta"


def test_the_registry_still_carries_the_compat_root_for_the_type() -> None:
    """The two homes now agree: the registry's entry IS what a row of that type should carry."""
    assert PROVIDER_ENDPOINTS["ollama_cloud"] == "https://ollama.com/v1"


# ── the join: a native path never lands under the compat root ───────────────


def test_a_native_path_is_composed_against_the_native_root() -> None:
    from app.domain.providers.availability import join_probe_url

    assert join_probe_url("https://ollama.com/v1", "/api/tags") == "https://ollama.com/api/tags"
    assert join_probe_url("https://ollama.com/v1", "/api/chat") == "https://ollama.com/api/chat"


def test_a_bare_host_still_serves_its_native_paths() -> None:
    from app.domain.providers.availability import join_probe_url

    assert join_probe_url("http://localhost:11434", "/api/tags") == (
        "http://localhost:11434/api/tags"
    )


def test_the_compat_case_that_was_already_handled_still_holds() -> None:
    """The 2026-09-09 find: a managed local base_url IS the API root, so the path's leading /v1 goes."""
    from app.domain.providers.availability import join_probe_url

    assert join_probe_url("http://127.0.0.1:8080/v1", "/v1/models") == (
        "http://127.0.0.1:8080/v1/models"
    )


# ── the discovery paths: what actually goes on the wire ─────────────────────


def _recording_client(dialled: list) -> AsyncMock:
    """A stand-in for httpx.AsyncClient that records the URL each GET dialled."""
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"models": []})

    client = AsyncMock()

    async def _get(url: str, **kwargs) -> AsyncMock:
        dialled.append(url)
        return response

    client.get = _get
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_cloud_discovery_dials_the_native_root_when_the_row_carries_the_compat_root() -> None:
    from app.domain.providers.discovery_service import provider_discovery_service

    dialled: list[str] = []
    db = AsyncMock()
    db.commit = AsyncMock()

    with patch("httpx.AsyncClient", return_value=_recording_client(dialled)):
        await provider_discovery_service.discover_ollama_cloud_models(
            db, provider_id=5, api_key="k", base_url="https://ollama.com/v1"
        )

    assert dialled == ["https://ollama.com/api/tags"], "the native API is not beneath the /v1 root"


@pytest.mark.asyncio
async def test_local_discovery_is_untouched_by_the_derivation() -> None:
    """A bare root keeps its own native paths — the derivation is an identity here, not a rewrite."""
    from app.domain.providers.discovery_service import provider_discovery_service

    dialled: list[str] = []
    db = AsyncMock()
    db.commit = AsyncMock()

    with patch("httpx.AsyncClient", return_value=_recording_client(dialled)):
        await provider_discovery_service.discover_ollama_models(
            db, provider_id=1, base_url="http://localhost:11434"
        )

    assert dialled == ["http://localhost:11434/api/tags"]


# ── the browser routes: an address is RESOLVED, or the row is reported ──────


def _a_row(name: str, provider_type: str, base_url: str | None):
    from app.infrastructure.database.models import Provider

    return Provider(name=name, provider_type=provider_type, base_url=base_url)


def test_a_cloud_row_that_declares_nothing_gets_the_types_compat_root() -> None:
    from app.api.v1.providers.models_router import _endpoint_or_refuse

    assert _endpoint_or_refuse(_a_row("ollama_cloud", "ollama_cloud", None)) == (
        "https://ollama.com/v1"
    )


def test_a_row_that_declares_its_own_endpoint_wins() -> None:
    from app.api.v1.providers.models_router import _endpoint_or_refuse

    assert _endpoint_or_refuse(_a_row("ollama_cloud", "ollama_cloud", "https://proxy.internal/v1")) == (
        "https://proxy.internal/v1"
    )


def test_a_type_with_no_canonical_endpoint_is_refused_rather_than_guessed() -> None:
    """The browsers used to answer here with `http://localhost:11434` / `https://ollama.com`."""
    from fastapi import HTTPException

    from app.api.v1.providers.models_router import _endpoint_or_refuse

    with pytest.raises(HTTPException) as raised:
        _endpoint_or_refuse(_a_row("llama", "openai", None))

    assert raised.value.status_code == 409
    assert "endpoint" in str(raised.value.detail)


# ── the REPORT half: a row carrying the native root, and the offer ──────────
# The user's ruling on stage 2 — *"report, then offer"*: the app says what it will dial and what to
# set, and never rewrites the row. `provider_endpoints.compat_root_offer` is the knowledge; the
# availability reason and the dispatch log are the two surfaces that render it.


def test_a_row_on_the_native_root_is_offered_the_compat_root() -> None:
    from app.domain.providers.provider_endpoints import compat_root_offer

    assert compat_root_offer("ollama_cloud", "https://ollama.com") == "https://ollama.com/v1"


def test_a_row_already_on_the_compat_root_is_left_alone() -> None:
    from app.domain.providers.provider_endpoints import compat_root_offer

    assert compat_root_offer("ollama_cloud", "https://ollama.com/v1") is None
    assert compat_root_offer("ollama_cloud", "https://ollama.com/v1/") is None


def test_a_row_on_another_host_is_left_alone() -> None:
    """A proxy or a mirror is not this app's business: it cannot know which root that host serves."""
    from app.domain.providers.provider_endpoints import compat_root_offer

    assert compat_root_offer("ollama_cloud", "https://proxy.internal") is None
    assert compat_root_offer("ollama_cloud", "https://proxy.internal/v1") is None


def test_a_type_that_speaks_one_protocol_is_left_alone() -> None:
    """The local `ollama` row is bare and CORRECT (its consumers are native); deepseek's row is
    `https://api.deepseek.com` while the registry's canonical endpoint carries `/v1` — but neither
    type has a native root, so nothing about them is right-for-one-protocol-and-wrong-for-the-other.
    This is the case that would have made the report fire on an install's DEFAULT row, every call."""
    from app.domain.providers.provider_endpoints import compat_root_offer

    assert compat_root_offer("deepseek", "https://api.deepseek.com") is None
    assert compat_root_offer("ollama", "http://localhost:11434") is None
    assert compat_root_offer("openai", "http://127.0.0.1:8080/v1") is None
    assert compat_root_offer("ollama_cloud", None) is None
    assert compat_root_offer("ollama_cloud", "") is None


def test_the_availability_report_names_what_is_dialled_and_what_to_set() -> None:
    """The surface: the provider test card and the capability read-out both render it.

    The card is the one that needed care — its HEALTHY branch builds its own sentence, so the report
    had to become a payload field (`Availability.note`), not only a longer `reason`.
    """
    from app.domain.providers.availability import (
        STATE_AVAILABLE,
        Availability,
        _endpoint_root_note,
        test_card,
    )

    note = _endpoint_root_note({"provider_type": "ollama_cloud", "base_url": "https://ollama.com"})

    assert note and "https://ollama.com/chat/completions" in note
    assert "https://ollama.com/v1" in note
    assert _endpoint_root_note(
        {"provider_type": "ollama_cloud", "base_url": "https://ollama.com/v1"}
    ) is None

    card = test_card(
        Availability(
            provider_id=5,
            name="ollama_cloud",
            state=STATE_AVAILABLE,
            reason="the provider answers and catalogues 18 model(s)",
            checked_at="now",
            models_served=("gpt-oss:20b",),
            note=note,
        ),
        "Ollama Cloud",
    )

    assert card["status"] == "connected", "the row IS reachable — the report is not a failure state"
    assert card["message"].startswith("Ollama Cloud is running with 1 model(s)")
    assert note in card["message"]
    assert "https://ollama.com/v1" in card["message"], "the offer must be on the card"


def test_a_healthy_row_without_a_note_gets_an_unadorned_card() -> None:
    """No stray separator on the ordinary case — every other provider's card is untouched."""
    from app.domain.providers.availability import STATE_AVAILABLE, Availability, test_card

    card = test_card(
        Availability(
            provider_id=3,
            name="deepseek",
            state=STATE_AVAILABLE,
            reason="the provider answers and catalogues 2 model(s)",
            checked_at="now",
            models_served=("a", "b"),
        ),
        "Deepseek",
    )

    assert card["message"] == "Deepseek is running with 2 model(s)"


def test_the_dispatch_reports_the_same_thing_before_it_dials(caplog) -> None:
    """A workflow node running an agent on such a row must be explicable in the log."""
    import logging as _logging

    from app.domain.providers.config_service import ProviderConfig
    from app.domain.providers.llm_factory import get_llm_from_config

    config = ProviderConfig(
        provider_type="ollama_cloud",
        base_url="https://ollama.com",
        name="ollama_cloud",
        config={"default_model": "gpt-oss:20b"},
        has_api_key=True,
    )

    with caplog.at_level(_logging.WARNING):
        get_llm_from_config(config, api_key="placeholder")

    reported = [
        r.getMessage() for r in caplog.records if "NATIVE root" in r.getMessage()
    ]
    assert reported, "the dispatch must say what it will dial"
    assert "https://ollama.com/chat/completions" in reported[0]
    assert "https://ollama.com/v1" in reported[0]
