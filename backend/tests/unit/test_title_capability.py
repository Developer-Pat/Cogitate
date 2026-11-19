"""The title service resolves through THE capability resolver — and never falls back quietly.

Phase 2 of the service-capability arc: `title` is the first CONSUMER of
`domain/providers/capabilities.resolve()`. What these tests hold still:

1. The resolution RIDES THE RESOLVER's ladder — override, the capability's own chain, then the
   global default row. The service passes NO AGENT, so the per-agent rung stays out of the title
   path (that is what keeps its behaviour unchanged).
2. The row the resolution NAMES supplies the connection details, and the validation that was there
   before (active? key? model?) still decides — an inactive row is still refused.
3. NO silent fallback — an unresolved capability is a LOUD marker, never a quiet second-best
   provider.
4. The alias rule is untouched: a local-server row (the `llama` alias) NEVER gets
   `reasoning_effort` (the openai adapter rejects the kwarg — proven 2026-09-02).
5. The per-request override rides the ladder's OVERRIDE rung, and a slashless override is still
   IGNORED.
6. A generation FAILURE is not silent: it reaches the toast seam, in the one wording, naming the
   provider and model it was sent to — and only on the AUTO path, and only for a real failure
   (phase 6, group 3 / A2).

The resolution is exercised against the TEST DATABASE with the REAL resolver, on rows this file
creates (unique `zz-` keys), so nothing here depends on the seeded capability rows or on the live
provider list. Discriminators: each test must go red when its behaviour is reverted.
"""
from __future__ import annotations

import logging
import time
import uuid
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import capabilities as cap
from app.domain.messaging import services as messaging_services
from app.domain.providers.config_service import DefaultProviderService
from app.domain.title import services as title_services
from app.domain.title.services import TitleService
from app.infrastructure.database.models import Capability, CapabilityService, Provider


async def _provider_row(
    session: AsyncSession,
    name: str,
    provider_type: str = "groq",
    base_url: Optional[str] = None,
    default_model: Optional[str] = "zz-title-model",
    is_active: bool = True,
) -> Provider:
    """A provider row of the class the test needs."""
    row = Provider(
        name=name,
        display_name=name,
        provider_type=provider_type,
        base_url=base_url,
        is_active=is_active,
        priority=99,
        config={"default_model": default_model} if default_model else {},
    )
    session.add(row)
    await session.flush()
    return row


async def _title_capability(
    session: AsyncSession,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    service_name: Optional[str] = None,
) -> str:
    """A `title`-shaped capability with one candidate; the KEY is unique per call."""
    key = f"zz-title-{uuid.uuid4().hex[:8]}"
    row = Capability(key=key, label="Test title", kind=cap.KIND_LLM, enabled=True)
    session.add(row)
    await session.flush()
    session.add(
        CapabilityService(
            capability_id=row.id,
            ordinal=0,
            enabled=True,
            provider_id=provider_id,
            model=model,
            service_name=service_name,
        )
    )
    await session.flush()
    return key


@pytest.mark.anyio
async def test_the_resolution_rides_the_capability_chain(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chain's primary IS the service — `DefaultProviderService` is not consulted by the service.

    The provider name/model come from the resolver's answer (`provider_type='groq'` is a
    cloud-classed row that carries no key requirement, so this test does not depend on a .env key).
    """
    provider = await _provider_row(test_session, f"zz-title-cloud-{uuid.uuid4().hex[:6]}")
    key = await _title_capability(test_session, provider_id=provider.id)
    monkeypatch.setattr(title_services, "TITLE_CAPABILITY_KEY", key)

    ts = TitleService()
    ok = await ts.load_config_from_database(test_session)

    assert ok is True
    assert ts.provider == provider.name
    assert ts.model == "zz-title-model"  # the row's own default_model, through the resolver
    # ...and the simple-task anti-reasoning rule fires for the cloud family
    assert ts.reasoning_effort == "none"


@pytest.mark.anyio
async def test_a_per_capability_model_beats_the_rows_default(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resolver's rule reaches the service: a pinned candidate model wins over the row's."""
    provider = await _provider_row(test_session, f"zz-title-pinned-{uuid.uuid4().hex[:6]}")
    key = await _title_capability(test_session, provider_id=provider.id, model="zz-pinned-model")
    monkeypatch.setattr(title_services, "TITLE_CAPABILITY_KEY", key)

    ts = TitleService()
    ok = await ts.load_config_from_database(test_session)

    assert ok is True
    assert ts.model == "zz-pinned-model"


@pytest.mark.anyio
async def test_a_local_alias_row_never_gets_reasoning_effort(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The adapter rule: a local-server row resolves WITHOUT `reasoning_effort`.

    What marks the row is its TYPE — the types litellm has no prefix for (`litellm_route.HANDLER_BY_TYPE`)
    — so the fixture uses the `llama` adapter type under a `zz-` name rather than colliding with the real
    `llama` row the installation already carries.
    """
    alias_name = f"zz-title-local-{uuid.uuid4().hex[:6]}"
    provider = await _provider_row(
        test_session,
        alias_name,
        provider_type="llama",
        base_url="http://127.0.0.1:4321/v1",
        default_model="local/zz-model.gguf",
    )
    key = await _title_capability(test_session, provider_id=provider.id)
    monkeypatch.setattr(title_services, "TITLE_CAPABILITY_KEY", key)

    ts = TitleService()
    ok = await ts.load_config_from_database(test_session)

    assert ok is True
    assert ts.provider == alias_name
    # The openai adapter rejects the kwarg — it must NEVER be set for a local row
    assert ts.reasoning_effort is None
    cfg = ts._get_llm_config()
    assert cfg["model"] == "openai/local/zz-model.gguf"
    # THE ROW's own address (2026-10-12, stage 2) — the fixture's 4321, not the old table's 8080:
    # an address in a table could not follow the row it belonged to.
    assert cfg["api_base"] == "http://127.0.0.1:4321/v1"
    assert "reasoning_effort" not in cfg


@pytest.mark.anyio
async def test_the_title_service_passes_NO_agent(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-agent rung stays OUT of the title path — the call shape is the contract.

    The chat path passes an agent (its behaviour today IS "the agent's model first"); the title
    service must not, which is exactly what keeps this migration behaviour-preserving.
    """
    provider = await _provider_row(test_session, f"zz-title-noagent-{uuid.uuid4().hex[:6]}")
    key = await _title_capability(test_session, provider_id=provider.id)
    monkeypatch.setattr(title_services, "TITLE_CAPABILITY_KEY", key)

    seen: dict[str, Any] = {}
    real_resolve = cap.resolve

    async def _spy(db, capability, *, agent=None, override=None):  # type: ignore[no-untyped-def]
        seen["capability"] = capability
        seen["agent"] = agent
        return await real_resolve(db, capability, agent=agent, override=override)

    monkeypatch.setattr(cap, "resolve", _spy)

    ts = TitleService()
    ok = await ts.load_config_from_database(test_session)

    assert ok is True
    assert seen["capability"] == key
    assert seen["agent"] is None


@pytest.mark.anyio
async def test_an_inactive_row_is_refused(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The validation that predates the resolver still decides: an inactive row does not generate."""
    provider = await _provider_row(
        test_session, f"zz-title-inactive-{uuid.uuid4().hex[:6]}", is_active=False
    )
    key = await _title_capability(test_session, provider_id=provider.id)
    monkeypatch.setattr(title_services, "TITLE_CAPABILITY_KEY", key)

    ts = TitleService()
    with caplog.at_level(logging.WARNING):
        ok = await ts.load_config_from_database(test_session)

    assert ok is False
    assert any("Provider is not active" in r.getMessage() for r in caplog.records), caplog.text


@pytest.mark.anyio
async def test_an_unresolved_capability_is_LOUD_and_never_a_silent_fallback(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Nothing configured at any rung: the service refuses, and says WHY."""
    monkeypatch.setattr(
        title_services, "TITLE_CAPABILITY_KEY", f"zz-missing-{uuid.uuid4().hex[:8]}"
    )

    async def _no_default(self: DefaultProviderService, db: AsyncSession) -> None:
        return None

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _no_default)

    ts = TitleService()
    with caplog.at_level(logging.WARNING):
        ok = await ts.load_config_from_database(test_session)

    assert ok is False
    assert ts.provider is None
    assert any(
        "No service resolved for the title capability" in r.getMessage() for r in caplog.records
    ), caplog.text


@pytest.mark.anyio
async def test_an_explicit_override_rides_the_resolvers_override_rung(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rung 1: `provider/model` is resolved by the ladder, and reaches the wire as its model string."""
    sent: dict[str, Any] = {}

    async def _fake_acompletion(**kwargs: Any) -> Any:
        sent.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="a title"))])

    monkeypatch.setattr(title_services, "acompletion", _fake_acompletion)

    ts = TitleService()
    ts.provider = "deepseek"
    ts.model = "deepseek-v4-flash"
    ts._config_loaded_at = time.time()  # fresh: the DB resolution is skipped, the override is not

    title = await ts.generate_title(
        messages=[{"role": "user", "content": "hello"}],
        db=test_session,
        model_override="zz-override/zz-override-model",
    )

    assert title == "a title"
    assert ts.provider == "zz-override"
    assert ts.model == "zz-override-model"
    assert ts.reasoning_effort == "none"  # the anti-reasoning rule, for a cloud override
    assert sent["model"] == "zz-override/zz-override-model"


@pytest.mark.anyio
async def test_a_slashless_override_is_ignored(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard that predates the resolver is preserved — a bare model name is not an override."""
    sent: dict[str, Any] = {}

    async def _fake_acompletion(**kwargs: Any) -> Any:
        sent.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="a title"))])

    monkeypatch.setattr(title_services, "acompletion", _fake_acompletion)

    ts = TitleService()
    ts.provider = "deepseek"
    ts.model = "deepseek-v4-flash"
    ts._config_loaded_at = time.time()

    await ts.generate_title(
        messages=[{"role": "user", "content": "hello"}],
        db=test_session,
        model_override="zz-slashless-model",
    )

    assert ts.provider == "deepseek"
    assert ts.model == "deepseek-v4-flash"
    assert sent["model"] == "deepseek/deepseek-v4-flash"


def test_the_choke_point_marker_is_loud() -> None:
    """No resolution -> unresolved state + the choke-point marker (the marker is not a quiet read)."""
    ts = TitleService()
    with patch("app.domain.title.services.logger") as mock_logger:
        ts.apply_fallback_config(reason="no_default_provider")
    assert ts.provider is None
    assert ts.model is None
    # The choke-point marker is logged at ERROR (not a quiet warning)
    mock_logger.error.assert_called_once()
    assert "TITLE-GEN CONFIG FAILED" in mock_logger.error.call_args[0][0]


def test_no_silent_fallback_env_reads_removed() -> None:
    """The TITLE_LLM_PROVIDER env universe is retired — no fallback attrs."""
    ts = TitleService()
    # These attributes no longer exist — resolution cannot quietly point
    # at a second-best env-configured provider
    assert not hasattr(ts, "fallback_provider")
    assert not hasattr(ts, "fallback_model")
    assert not hasattr(ts, "use_database_default")


@pytest.mark.anyio
async def test_generate_title_failure_logs_structured_marker(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generation failure carries the structured TITLE-GEN FAILED marker."""
    ts = TitleService()
    ts.provider = "deepseek"
    ts.model = "deepseek-v4-flash"
    ts.base_url = None
    ts.api_key = None
    ts.reasoning_effort = "none"
    # Config is "fresh" — skip re-resolution so the call reaches acompletion
    ts._config_loaded_at = time.time()

    async def _boom(**kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(title_services, "acompletion", _boom)

    with patch("app.domain.title.services.logger") as mock_logger:
        result = await ts.generate_title(
            messages=[{"role": "user", "content": "hello"}],
            user_enabled=True,
            db=test_session,
        )

    assert result is None
    # Find the structured marker among the logged errors
    markers = [c for c in mock_logger.error.call_args_list if "TITLE-GEN FAILED" in c[0][0]]
    assert markers, "expected the structured TITLE-GEN FAILED marker"


# ---------------------------------------------------------------------------
# 6. A real failure reaches a SURFACE — A2, the phase 6 group 3 landing
# ---------------------------------------------------------------------------
#
# The phase's site list named `finalization.py:416` and `:359`. Reading the target BEFORE building
# found neither is reachable for an LLM failure: `generate_title` catches its own exception and
# returns None, so the operative path is INSIDE the service — the caller holds only a `None`, which
# cannot name the offender nor even tell a failure from a benign refusal. These tests pin the report
# where the failure is known, and pin the two ways it must stay quiet.

def _resolved_service() -> TitleService:
    """A service pointed at a provider, with a FRESH config so the call reaches `acompletion`."""
    ts = TitleService()
    ts.provider = "deepseek"
    ts.model = "deepseek-v4-flash"
    ts.base_url = None
    ts.api_key = None
    ts.reasoning_effort = "none"
    ts._config_loaded_at = time.time()  # fresh — the DB re-resolution is skipped
    return ts


def _capture_toasts(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Intercept the toast seam `_report_failure` publishes through.

    Patched on the MESSAGING module because the service imports `publish_warning` locally inside the
    helper (the house's import-at-the-publish-site pattern), so the module attribute is what it
    resolves at call time. What is pinned is the CALL — its title, its kind and its words. The bus →
    SSE → toaster chain it rides is already exercised live by the executor's fallback notice;
    re-proving it here would measure the transport rather than this landing.
    """
    calls: list[dict[str, Any]] = []

    def _capture(title: str, message: str, kind: str = "provider-fallback") -> None:
        calls.append({"title": title, "message": message, "kind": kind})

    monkeypatch.setattr(messaging_services, "publish_warning", _capture)
    return calls


@pytest.mark.anyio
async def test_a_real_generation_failure_reaches_the_user(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure lands a toast naming the provider + model, AND keeps the log marker.

    Both halves are the checkpoint's own words: *"a real title failure reaches the toast, naming the
    resolved provider + model, with the same line in the app log."*
    """
    calls = _capture_toasts(monkeypatch)
    ts = _resolved_service()

    async def _boom(**kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(title_services, "acompletion", _boom)

    with patch("app.domain.title.services.logger") as mock_logger:
        result = await ts.generate_title(
            messages=[{"role": "user", "content": "hello"}],
            user_enabled=True,
            db=test_session,
            notify_failure=True,
        )

    assert result is None
    # (a) the LOG keeps its structured marker
    assert [c for c in mock_logger.error.call_args_list if "TITLE-GEN FAILED" in c[0][0]]
    # (b) the USER is told — once, and in the one wording
    assert len(calls) == 1, calls
    toast = calls[0]
    assert toast["title"] == "Session title not generated"
    assert toast["kind"] == "title-failure"
    # ...naming BOTH halves of the offender (a model alone leaves "on which provider?")
    assert "Deepseek V4 Flash (deepseek)" in toast["message"]
    # ...carrying the provider's own words, labelled as theirs
    assert "the provider reported: boom" in toast["message"]
    # ...and ending on the diagnosis OFFER: the statement has no slot for a recommendation
    assert toast["message"].endswith("You can have Exa attempt diagnosis (ask Exa).")


@pytest.mark.anyio
async def test_the_manual_path_publishes_nothing(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-call opt-out: without `notify_failure` the seam is untouched.

    The manual endpoint (`POST /chat/generate-title`) answers 500 + detail, which IS its surface —
    a toast on top would report one failure twice.
    """
    calls = _capture_toasts(monkeypatch)
    ts = _resolved_service()

    async def _boom(**kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(title_services, "acompletion", _boom)

    result = await ts.generate_title(
        messages=[{"role": "user", "content": "hello"}],
        user_enabled=True,
        db=test_session,
    )

    assert result is None
    assert calls == []


@pytest.mark.anyio
async def test_a_benign_refusal_publishes_nothing(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A REFUSAL is not a failure — auto-title switched off must not raise an alarm.

    `generate_title` returns None for five different reasons and only the LLM failure is reportable.
    A toast here would be the false positive that teaches the reader to ignore the channel.
    """
    calls = _capture_toasts(monkeypatch)
    ts = _resolved_service()

    async def _should_not_run(**kwargs: Any) -> Any:
        raise AssertionError("the LLM must not be called when auto-title is off")

    monkeypatch.setattr(title_services, "acompletion", _should_not_run)

    result = await ts.generate_title(
        messages=[{"role": "user", "content": "hello"}],
        user_enabled=False,
        db=test_session,
        notify_failure=True,
    )

    assert result is None
    assert calls == []


@pytest.mark.anyio
async def test_the_auto_path_asks_for_the_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE WIRING — `generate_title_if_needed` (the auto path) opts in; that is what makes it real.

    Without this one keyword the service stays silent and the whole landing is inert, so the
    call shape is pinned here rather than left to the live check.
    """
    from app.api.v1.chat import finalization

    seen: dict[str, Any] = {}

    class _SpyTitleService:
        async def generate_title(self, **kwargs: Any) -> Optional[str]:
            seen.update(kwargs)
            return None  # a failure that generated nothing to save

    monkeypatch.setattr(finalization, "get_title_service", lambda: _SpyTitleService())

    # `Any`-typed stand-ins: `generate_title_if_needed` only READS `.title` and calls the two
    # services, and building a real `ChatSession` + logger needs rows this test is not about
    # (the same stand-in shape `test_failure_statement.py` uses for the chat context).
    session: Any = SimpleNamespace(id=1, title="New Session 1")
    db: Any = None
    logger_service: Any = SimpleNamespace()

    await finalization.generate_title_if_needed(
        session=session,
        first_message="hello",
        db=db,
        logger_service=logger_service,
    )

    assert seen.get("notify_failure") is True
