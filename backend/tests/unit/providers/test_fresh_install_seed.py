"""A FRESH INSTALL SEEDS NO MODEL.

The last shipped model choice in the app. `DefaultProviderService.initialize_default_provider`
created the first-run `ollama` row carrying `default_model: llama3.2:latest` — a model nobody
chose, on an install where nothing is running yet. The user's ruling this session: *which model
runs is the user's and Exa's to decide*, and setting up a curated fresh install is work for Exa
(an installation skill), not for a seed compiled into the app.

Same precedent as the A2 shrink: fresh installs boot with an EMPTY curated table, never a shipped
seed.

**Not part of this:** the row's `base_url`. An endpoint on a row IS the decision about which
server answers, and the row is the one place the user edits it — so it stays.

The seed's collaborators are stubbed rather than a real providers table being emptied: the test
database is session-scoped and shared, so deleting rows to fake a fresh install would take the
other tests' providers with it.
"""

from __future__ import annotations

import logging

import pytest

from app.domain.providers.config_service import (
    DefaultProviderService,
    ProviderConfigService,
    ProviderConfig,
)


def _fresh_install(monkeypatch) -> dict:
    """Stub the seed's world as an EMPTY install; return what it asks to create."""
    captured: dict = {}

    async def _no_default(self, db):
        return None

    async def _no_providers(self, db):
        return []

    async def _capture_create(self, **kwargs):
        captured.update(kwargs)
        return ProviderConfig(
            id=1,
            name=kwargs.get("name", ""),
            provider_type=kwargs.get("provider_type", ""),
            base_url=kwargs.get("base_url"),
            config=kwargs.get("config"),
        )

    async def _record_default(self, db, provider_id):
        captured["default_set_for"] = provider_id
        return True

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _no_default)
    monkeypatch.setattr(DefaultProviderService, "set_default_provider", _record_default)
    monkeypatch.setattr(ProviderConfigService, "list_providers", _no_providers)
    monkeypatch.setattr(ProviderConfigService, "create_provider", _capture_create)
    return captured


@pytest.mark.asyncio
async def test_a_fresh_install_creates_the_row_naming_no_model(monkeypatch, test_session):
    captured = _fresh_install(monkeypatch)

    await DefaultProviderService().initialize_default_provider(test_session)

    assert captured["name"] == "ollama"
    assert captured["provider_type"] == "ollama"
    assert not (captured.get("config") or {}).get("default_model"), (
        "the seed must not choose a model — which one runs is the user's, and Exa's, to decide"
    )


@pytest.mark.asyncio
async def test_a_fresh_install_keeps_the_rows_own_endpoint(monkeypatch, test_session):
    """The endpoint is a DECISION that belongs to the row (the user edits it there) — the seed
    declares it so the row is usable out of the box, and it is not this landing's business."""
    captured = _fresh_install(monkeypatch)

    await DefaultProviderService().initialize_default_provider(test_session)

    assert captured["base_url"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_the_seed_still_makes_the_row_the_installs_default(monkeypatch, test_session):
    """The control: the row is created AND promoted, so a fresh install is out-of-the-box usable
    the moment a model is chosen."""
    captured = _fresh_install(monkeypatch)

    await DefaultProviderService().initialize_default_provider(test_session)

    assert captured["default_set_for"] == 1
    assert captured["is_active"] is True


@pytest.mark.asyncio
async def test_nothing_the_seed_says_names_a_model(monkeypatch, caplog, test_session):
    """The seed used to LOG the model it had chosen (`... with model llama3.2:latest`), which is
    the same literal in a second home — a log line is read by users and by Exa."""
    _fresh_install(monkeypatch)

    with caplog.at_level(logging.INFO):
        await DefaultProviderService().initialize_default_provider(test_session)

    for record in caplog.records:
        assert "llama3.2" not in record.getMessage(), f"a model is named: {record.getMessage()}"
