"""A provider row's endpoint — and what happens when it declares none.

The service-literals arc's rule, as the user stated it: *the app should never write down the
name of a model, an endpoint or a service*, and what decides a borderline case is whether the
literal is a **decision** or a **definition**.

- A DECISION is the app choosing, on the user's behalf, which service does the work. The row
  carries that answer, and code must not hold a copy of it — *not even as a backup*: a backup
  is how a configuration gap passes for a deliberate address.
- A DEFINITION is a utility describing the one service it exists to talk to. That is
  legitimate, and it belongs in ONE named constant rather than inline.

The endpoint the app dials is the decision half. So: the row's ``base_url`` wins; when a row
declares none, the provider TYPE's canonical endpoint (`provider_endpoints`) answers — and the
omission is REPORTED, so silence in the config cannot pass for an address somebody chose.

The old per-adapter ``base_url or "<the vendor>"`` literals are what these tests replace: a
second copy of that table, already drifted from it, at the point of dispatch.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.domain.providers.config_service import ProviderConfig
from app.domain.providers.llm_factory import get_llm_from_config, single_served_model
from app.domain.providers.provider_endpoints import PROVIDER_ENDPOINTS, canonical_endpoint

# A stand-in for what a local server reports (the path it was launched with — never a value the
# app should store in a row).
SERVED = "/models/Bonsai-27B-Q1_0.gguf"


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _probe(monkeypatch, *ids: str) -> list[str]:
    """Stub the single-model probe; return the URLs it was asked for."""
    asked: list[str] = []

    def fake_get(url: str, timeout: float | None = None) -> _Response:
        asked.append(url)
        return _Response({"data": [{"id": i} for i in ids]})

    monkeypatch.setattr("httpx.get", fake_get)
    return asked


def _stub_client(monkeypatch, helper: str) -> dict[str, Any]:
    """Replace one adapter constructor; capture the kwargs it was handed."""
    seen: dict[str, Any] = {}

    def fake_create(model: str, **kwargs: Any) -> object:
        seen["model"] = model
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(f"app.domain.providers.llm_factory.{helper}", fake_create)
    return seen


def _row(provider_type: str, base_url: str | None = None, model: str = "some-model") -> ProviderConfig:
    return ProviderConfig(
        name=provider_type,
        provider_type=provider_type,
        base_url=base_url,
        config={"default_model": model},
    )


# ── the rule: the row decides, the registry answers only for silence ────────

# The type → the helper it dispatches to. The EXPECTED address is read from the REGISTRY rather
# than repeated here: the registry is the one home for it, and a table that copies the value drifts
# the moment the registry moves — which it did on 2026-10-12, when deepseek's entry was corrected.
ADAPTER_CASES = [
    ("ollama", "_create_ollama_client"),
    ("ollama_cloud", "_create_ollama_cloud_client"),
    ("openrouter", "_create_openrouter_client"),
    ("deepseek", "_create_deepseek_client"),
    ("groq", "_create_groq_client"),
]


def test_the_registry_holds_the_addresses_this_install_can_point_at():
    """The vendors' roots, keyed by TYPE — one home for the fact, with its sources.

    `deepseek` is the BARE host: its current docs name it as the OpenAI base_url and never mention
    `/v1`, the live row carries the bare host, and this install runs its agents and Exa on it.
    `ollama_cloud` is the COMPAT root (the arc's ruling: the row carries the native host, and a
    client that speaks the compatible protocol needs `/v1`). `openai` and `anthropic` are ABSENT by
    design — each names a hosted vendor AND any self-hosted compatible server, so a ROW declares it.
    """
    assert PROVIDER_ENDPOINTS["deepseek"] == "https://api.deepseek.com"
    assert PROVIDER_ENDPOINTS["ollama_cloud"] == "https://ollama.com/v1"
    assert PROVIDER_ENDPOINTS["ollama"] == "http://localhost:11434"
    assert canonical_endpoint("openai") is None
    assert canonical_endpoint("anthropic") is None


def test_a_declared_endpoint_is_the_one_the_client_is_built_with(monkeypatch, caplog):
    """The row's own address — nothing is overruled, and nothing is reported."""
    _probe(monkeypatch)
    seen = _stub_client(monkeypatch, "_create_deepseek_client")

    with caplog.at_level(logging.WARNING):
        get_llm_from_config(
            _row("deepseek", base_url="https://deepseek.internal/v1"), api_key="k"
        )

    assert seen["base_url"] == "https://deepseek.internal/v1"
    assert not [r for r in caplog.records if "declares no base_url" in r.getMessage()]


@pytest.mark.parametrize("provider_type,helper", ADAPTER_CASES)
def test_a_row_that_declares_no_endpoint_gets_its_type_canonical_one(
    monkeypatch, provider_type, helper
):
    """The registry is the ONE definition of where a type lives."""
    _probe(monkeypatch)
    seen = _stub_client(monkeypatch, helper)

    get_llm_from_config(_row(provider_type), api_key="k")

    assert seen["base_url"] == PROVIDER_ENDPOINTS[provider_type]


@pytest.mark.parametrize("provider_type", sorted(PROVIDER_ENDPOINTS))
def test_the_silence_is_reported_not_passed_off_as_configuration(monkeypatch, caplog, provider_type):
    """A row that declares none must not read as a row that chose one."""
    _probe(monkeypatch)
    _stub_client(monkeypatch, "_create_ollama_client")
    _stub_client(monkeypatch, "_create_ollama_cloud_client")

    with caplog.at_level(logging.WARNING):
        get_llm_from_config(_row(provider_type), api_key="k")

    reported = [r.getMessage() for r in caplog.records if "declares no base_url" in r.getMessage()]
    assert reported, "the omission has to be logged, not swallowed"
    assert PROVIDER_ENDPOINTS[provider_type] in reported[0]


def test_an_empty_string_is_silence_too(monkeypatch):
    """The API accepts `""` as readily as `None`; both mean the row declared nothing."""
    _probe(monkeypatch)
    seen = _stub_client(monkeypatch, "_create_groq_client")

    get_llm_from_config(_row("groq", base_url=""), api_key="k")

    assert seen["base_url"] == "https://api.groq.com/openai/v1"


# ── the types that deliberately have no canonical endpoint ──────────────────


def test_the_overloaded_type_is_not_sent_to_a_vendor(monkeypatch, caplog):
    """`openai` names a hosted vendor AND any self-hosted OpenAI-compatible server (the live
    `llama` row is exactly that), so there is no single address to answer with — an `openai`
    row that declares none must NOT be quietly dialled at the vendor."""
    _probe(monkeypatch)
    seen = _stub_client(monkeypatch, "_create_openai_client")

    assert canonical_endpoint("openai") is None
    assert canonical_endpoint("anthropic") is None

    with caplog.at_level(logging.WARNING):
        get_llm_from_config(_row("openai", base_url=None), api_key="k")

    assert seen["base_url"] is None
    assert [r for r in caplog.records if "declares no base_url" in r.getMessage()]


# ── one resolution, both consumers ──────────────────────────────────────────


def test_the_probe_asks_the_address_the_app_will_dial(monkeypatch):
    """A local row with no endpoint still gets the single-model rule: the endpoint is resolved
    ONCE, so the probe and the client cannot disagree about which server is being asked."""
    asked = _probe(monkeypatch, SERVED)
    seen = _stub_client(monkeypatch, "_create_ollama_client")

    get_llm_from_config(_row("ollama", base_url=None, model="phi4-mini:latest"))

    assert asked == ["http://localhost:11434/v1/models"]
    assert seen["model"] == SERVED, "the server's own answer beats a configured alias"
    assert seen["base_url"] == "http://localhost:11434"


def test_the_probe_still_refuses_a_row_with_no_endpoint_and_no_registry_entry(monkeypatch):
    asked = _probe(monkeypatch, SERVED)

    assert single_served_model(_row("openai", base_url=None)) == ""
    assert asked == []
