"""A single-model LOCAL server names itself.

llama.cpp is launched with one `-m` and serves that model to every request; the model string
on the wire is decorative to it. The app nevertheless has to send one, and it used to fall
back to the provider's NAME (`model="openai"` went out on the wire) or to a `default_model`
somebody typed once — a short alias, while the server was launched with a full path.

So: when a loopback server reports exactly ONE model on `/v1/models`, that is the answer, and
a configured name it does not report is logged rather than quietly sent. A server holding
SEVERAL models is left alone — there the configured name is how one is selected.

Every test stubs `httpx.get`, so nothing here needs a running server.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.providers.config_service import ProviderConfig
from app.domain.providers.llm_factory import get_llm_from_config, single_served_model

# A STAND-IN for what a local server reports: llama-server echoes the path it was launched
# with, which on a real machine is an absolute path in somebody's home directory — precisely
# the value the app should NOT store in a provider row, and precisely why this rule exists.
# A generic path keeps the SHAPE under test without shipping a real layout.
SERVED = "/models/Bonsai-27B-Q1_0.gguf"


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _serving(monkeypatch, *ids: str) -> list[str]:
    """Stub the probe; return the URLs it was asked for."""
    asked: list[str] = []

    def fake_get(url: str, timeout: float | None = None) -> _Response:
        asked.append(url)
        return _Response({"data": [{"id": i} for i in ids]})

    monkeypatch.setattr("httpx.get", fake_get)
    return asked


def _local_row(model: str = "") -> ProviderConfig:
    """The live `llama` row's shape: openai adapter on the loopback."""
    return ProviderConfig(
        name="llama",
        provider_type="openai",
        base_url="http://127.0.0.1:8080/v1",
        has_api_key=False,
        config={"default_model": model} if model else {},
    )


# ── the rule itself ─────────────────────────────────────────────────────────


def test_a_local_server_with_one_model_names_it(monkeypatch):
    _serving(monkeypatch, SERVED)

    assert single_served_model(_local_row("Bonsai-27B-Q1_0.gguf")) == SERVED


def test_the_probe_does_not_double_the_api_root(monkeypatch):
    """`/v1` + `/v1/models` is the trap that made a live daemon read as down once."""
    asked = _serving(monkeypatch, SERVED)

    single_served_model(_local_row())

    assert asked == ["http://127.0.0.1:8080/v1/models"]


def test_a_server_holding_several_models_is_left_alone(monkeypatch):
    """Ollama is the real case: there the configured name SELECTS one, so it must win."""
    _serving(monkeypatch, "phi4-mini:latest", "llama3.2:latest")

    assert single_served_model(_local_row("phi4-mini:latest")) == ""


def test_a_cloud_provider_is_never_probed(monkeypatch):
    """The rule is about a server that MOUNTS its model — a hosted API is told which to run."""
    asked = _serving(monkeypatch, "whatever")
    cloud = ProviderConfig(
        name="deepseek", provider_type="deepseek", base_url="https://api.deepseek.com"
    )

    assert single_served_model(cloud) == ""
    assert asked == [], "a cloud provider must not pay for a probe"


def test_an_unreachable_server_yields_nothing(monkeypatch):
    def refuse(url: str, timeout: float | None = None) -> _Response:
        raise RuntimeError("connection refused")

    monkeypatch.setattr("httpx.get", refuse)

    assert single_served_model(_local_row()) == ""


def test_a_provider_with_no_endpoint_yields_nothing(monkeypatch):
    asked = _serving(monkeypatch, SERVED)

    assert single_served_model(ProviderConfig(name="x", provider_type="openai")) == ""
    assert asked == []


# ── the wiring: the served model is what the client is built with ───────────


def test_the_served_model_is_what_the_client_is_built_with(monkeypatch, caplog):
    """The whole point — and the disagreement is logged, not swallowed."""
    _serving(monkeypatch, SERVED)
    seen: dict[str, Any] = {}

    def fake_create(model: str, **kwargs: Any) -> object:
        seen["model"] = model
        return object()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory._create_openai_client", fake_create
    )

    with caplog.at_level(logging.WARNING):
        get_llm_from_config(_local_row("Bonsai-27B-Q1_0.gguf"))

    assert seen["model"] == SERVED, "the short alias must not be what goes out"
    assert any(
        "but the server serves" in r.getMessage() for r in caplog.records
    ), "a stale configured name has to be REPORTED, not silently overruled"


def test_an_empty_local_model_is_filled_from_the_server(monkeypatch):
    """No configured model at all: the server's answer beats the provider's NAME."""
    _serving(monkeypatch, SERVED)
    seen: dict[str, Any] = {}

    def fake_create(model: str, **kwargs: Any) -> object:
        seen["model"] = model
        return object()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory._create_openai_client", fake_create
    )

    get_llm_from_config(_local_row())

    assert seen["model"] == SERVED


def test_a_cloud_provider_keeps_its_configured_model(monkeypatch):
    """The guarded half: nothing about a hosted provider changes."""
    _serving(monkeypatch, "not-asked-for")
    seen: dict[str, Any] = {}

    def fake_create(model: str, **kwargs: Any) -> object:
        seen["model"] = model
        return object()

    monkeypatch.setattr(
        "app.domain.providers.llm_factory._create_deepseek_client", fake_create
    )
    cloud = ProviderConfig(
        name="deepseek",
        provider_type="deepseek",
        base_url="https://api.deepseek.com",
        has_api_key=True,
        config={"default_model": "deepseek-v4-flash"},
    )

    get_llm_from_config(cloud)

    assert seen["model"] == "deepseek-v4-flash"
