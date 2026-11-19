"""Workflow node factories resolve through THE capability resolver, never falling back quietly.

Phase 4 of the service-capability arc: `workflow-llm` becomes the capability the workflow LLM
factories ask, and `llm_factory.get_llm_for_capability()` is the seam that turns a resolution into a
client. What these tests hold still — each goes red when its behaviour is reverted:

1. The client is built from **the row the resolution NAMES** — not from the default row, which is
   merely one rung of the same ladder and happens to be what `workflow-llm` is seeded with today.
2. **The resolution's model wins.** A candidate that pins a model must reach the factory, or the
   row's own `default_model` silently answers a question the capability already decided.
3. **No silent fallback.** A capability that resolves to nothing usable — a candidate naming no
   provider row, or a row that is switched off — yields None, and the FACTORY turns that into a loud
   `NoProviderConfiguredError`. The `ChatOpenAI(model="gpt-4o-mini")` environment fallback that used
   to sit in both factories is gone; `test_the_enhanced_planner_raises_when_nothing_resolves` is the
   discriminator for that.
4. The factories ask **the capability**, by key — `workflow-llm`.

The seam tests run against the TEST DATABASE with the REAL resolver, on rows this file creates
(unique `zz-` keys), so nothing here depends on the seeded capability rows or the live provider list.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import llm_factory
from app.domain.providers import capabilities as cap
from app.infrastructure.database.models import Capability, CapabilityService, Provider
from app.workflows.nodes import default_provider_test_nodes, enhanced_nodes
from app.workflows.utils.run_failure import run_failure_statement


# ── fixtures: rows this file owns ───────────────────────────────────────────────────────────────

async def _provider_row(
    session: AsyncSession,
    *,
    name: Optional[str] = None,
    provider_type: str = "groq",
    base_url: Optional[str] = None,
    default_model: Optional[str] = "zz-wf-model",
    is_active: bool = True,
) -> Provider:
    row = Provider(
        name=name or f"zz-wf-{uuid.uuid4().hex[:8]}",
        display_name="zz workflow capability test",
        provider_type=provider_type,
        base_url=base_url,
        is_active=is_active,
        priority=99,
        config={"default_model": default_model} if default_model else {},
    )
    session.add(row)
    await session.flush()
    return row


async def _workflow_capability(
    session: AsyncSession,
    *,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    service_name: Optional[str] = None,
) -> str:
    """A `workflow-llm`-SHAPED capability with one candidate; the KEY is unique per call."""
    key = f"zz-workflow-{uuid.uuid4().hex[:8]}"
    row = Capability(key=key, label="zz workflow steps", kind=cap.KIND_LLM, enabled=True)
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


class _Spy:
    """Stand in for `get_llm_from_config`: record what the seam handed it, return a sentinel."""

    def __init__(self) -> None:
        self.config: Any = None
        self.kwargs: dict[str, Any] = {}

    def __call__(self, config: Any, **kwargs: Any) -> str:
        self.config = config
        self.kwargs = kwargs
        return "SENTINEL-CLIENT"


# ── the seam: resolution → a client ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_the_client_is_built_from_the_row_the_resolution_names(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row the answer NAMES supplies the client — and the caller's sampling rides through."""
    provider = await _provider_row(test_session)
    key = await _workflow_capability(test_session, provider_id=provider.id)
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    llm = await llm_factory.get_llm_for_capability(
        test_session, key, temperature=0.1, top_p=0.5, max_tokens=2000
    )

    assert llm == "SENTINEL-CLIENT"
    assert spy.config is not None, "the factory was never called"
    assert spy.config.id == provider.id
    assert spy.config.name == provider.name
    assert spy.kwargs["temperature"] == 0.1
    assert spy.kwargs["top_p"] == 0.5
    assert spy.kwargs["max_tokens"] == 2000


@pytest.mark.anyio
async def test_the_stored_key_is_fetched_and_handed_to_the_factory(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row that says it HAS a key carries none — the seam fetches it from the secrets store.

    Measured live (2026-09-30): without this the factory built a keyless client and every workflow
    LLM step died at `Missing credentials` — on the default row, before this phase and after it.
    The house shape is the title service's and `workflow/nodes/agent_nodes.py`'s.
    """
    provider = await _provider_row(test_session)
    key = await _workflow_capability(test_session, provider_id=provider.id)
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    async def fake_get_api_key(self: Any, db: Any, provider_id: int) -> str:
        assert provider_id == provider.id, "the key must be fetched for the row that was resolved"
        return "zz-stored-key"

    monkeypatch.setattr(
        "app.domain.providers.config_service.ProviderConfigService.get_api_key", fake_get_api_key
    )

    await llm_factory.get_llm_for_capability(test_session, key)

    assert spy.kwargs["api_key"] == "zz-stored-key"


@pytest.mark.anyio
async def test_a_loopback_row_gets_the_house_placeholder(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A LOCAL service is keyless by nature, but its openai-shaped adapter still needs a value."""
    provider = await _provider_row(
        test_session, provider_type="openai", base_url="http://127.0.0.1:8080/v1"
    )
    key = await _workflow_capability(test_session, provider_id=provider.id)
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    async def no_key(self: Any, db: Any, provider_id: int) -> None:
        return None

    monkeypatch.setattr(
        "app.domain.providers.config_service.ProviderConfigService.get_api_key", no_key
    )

    await llm_factory.get_llm_for_capability(test_session, key)

    assert spy.kwargs["api_key"] == llm_factory.LOCAL_KEY_PLACEHOLDER


@pytest.mark.anyio
async def test_a_pinned_candidate_model_beats_the_rows_default_model(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE RESOLVER'S ANSWER IS THE MODEL: a candidate's pinned model reaches the factory.

    `get_llm_from_config` reads the model off the ROW, so without the seam's substitution the
    pinned model would be silently dropped and the row's `default_model` used instead — the two
    answers this arc exists to collapse into one.
    """
    provider = await _provider_row(test_session, default_model="zz-row-default")
    key = await _workflow_capability(test_session, provider_id=provider.id, model="zz-pinned")
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    await llm_factory.get_llm_for_capability(test_session, key)

    assert spy.config is not None
    assert spy.config.config["default_model"] == "zz-pinned"
    # ...and the row object itself is NOT mutated by the resolution
    await test_session.refresh(provider)
    assert provider.config["default_model"] == "zz-row-default"


@pytest.mark.anyio
async def test_a_candidate_naming_no_provider_row_yields_none(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `service_name` candidate (a speech engine, an external process) cannot answer an LLM call."""
    key = await _workflow_capability(test_session, service_name="zz-not-a-provider")
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    assert await llm_factory.get_llm_for_capability(test_session, key) is None
    assert spy.config is None, "a client must not be built for a service that names no row"


@pytest.mark.anyio
async def test_an_inactive_row_yields_none(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    """A switched-off row is not a service. The refusal is LOGGED, not silent."""
    provider = await _provider_row(test_session, is_active=False)
    key = await _workflow_capability(test_session, provider_id=provider.id)
    spy = _Spy()
    monkeypatch.setattr(llm_factory, "get_llm_from_config", spy)

    with caplog.at_level(logging.WARNING):
        assert await llm_factory.get_llm_for_capability(test_session, key) is None

    assert spy.config is None
    assert any("INACTIVE" in r.getMessage() for r in caplog.records), (
        "an inactive row must be named in the log — a silently skipped service is the defect class "
        "this arc removes"
    )


# ── the factories: they ask the capability ──────────────────────────────────────────────────────

def test_the_enhanced_planner_asks_the_workflow_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """`enhanced_nodes.get_llm()` resolves `workflow-llm` and returns the seam's client.

    The patch targets `llm_factory` because that module's name is imported INSIDE the function
    (`get_llm()` deliberately imports late to keep graph building light) — so the module attribute
    is what the call reads. Do not "fix" this to patch the node module: the node holds no such name.
    """
    asked: list[tuple[str, dict[str, Any]]] = []

    async def fake(db: Any, capability: str, **kwargs: Any) -> str:
        asked.append((capability, kwargs))
        return "SENTINEL-CLIENT"

    monkeypatch.setattr(llm_factory, "get_llm_for_capability", fake)

    assert enhanced_nodes.get_llm() == "SENTINEL-CLIENT"
    assert asked, "the factory did not ask the resolver-backed seam"
    assert asked[0][0] == "workflow-llm"
    assert asked[0][1] == {"temperature": 0.0, "max_tokens": 2000}


def test_the_enhanced_planner_raises_when_nothing_resolves(
    monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    """THE DISCRIMINATOR FOR THE RETIRED FALLBACK: no service is a LOUD error, not `gpt-4o-mini`.

    Two halves, because the raise alone is satisfiable by accident: the error must come from the
    RESOLUTION having nothing (the message names the capability), and the environment fallback must
    not have been attempted at all (its own log line is gone). On the reverted code the seam is
    unused, the DEFAULT ROW answers, and nothing raises — which is the behaviour this replaced.
    """
    from app.domain.providers.capabilities import NoProviderConfiguredError

    async def fake(db: Any, capability: str, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(llm_factory, "get_llm_for_capability", fake)

    with caplog.at_level(logging.INFO):
        with pytest.raises(NoProviderConfiguredError):
            enhanced_nodes.get_llm()

    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "No service resolved for the 'workflow-llm' capability" in m for m in messages
    ), "the error must name the capability that resolved to nothing"
    assert not any("fallback ChatOpenAI" in m for m in messages), (
        "a model written in code must not be attempted — the env fallback is the hardwiring this "
        "phase removes"
    )


@pytest.mark.anyio
async def test_the_provider_test_templates_ask_the_workflow_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`default_provider_test_nodes._get_default_llm()` asks the capability too, sampling included.

    This one patches the NODE module: its import is at module level (as it always was), so the name
    it calls lives in the node's own namespace.
    """
    asked: list[tuple[str, dict[str, Any]]] = []

    async def fake(db: Any, capability: str, **kwargs: Any) -> str:
        asked.append((capability, kwargs))
        return "SENTINEL-CLIENT"

    monkeypatch.setattr(default_provider_test_nodes, "get_llm_for_capability", fake)

    assert await default_provider_test_nodes._get_default_llm() == "SENTINEL-CLIENT"
    assert asked[0][0] == "workflow-llm"
    assert asked[0][1] == {"temperature": 0.1, "top_p": 0.5, "max_tokens": 2000}


# ── the node FAILURE path: the ONE wording, the SHARED taxonomy (Stage 4) ────────────────────────
#
# The retirement's own net. `llm_health.categorize_llm_error` used to wrap every node exception in
# an `LLMHealthError` whose "provider" was the CLIENT'S CLASS NAME (`ChatOpenAI`) — and both live
# callers passed no client at all, so a user-facing sentence came out "Provider 'Unknown' …". These
# tests are what goes red if the organ (or a copy of its list) creeps back: the node's failure now
# says the ONE sentence, naming the row the RUN resolved, and only when the provider layer failed.

class _ProviderError(Exception):
    """A stand-in for the provider layer's own error — the `llm_provider` signal G4-F5 reads."""

    llm_provider = "deepseek"


class _ConstructionError(Exception):
    """A distinctive failure for the factory paths — never a provider error."""


class _FailingLLM:
    """A client whose only call raises the error it was handed."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        raise self._error


def _state_with_resolution() -> dict:
    """A planner state whose run carried a resolved service — the shape every run has now."""
    from langchain_core.messages import HumanMessage

    from app.workflows.state.workflow_state import LLMResolution, RunMetadata

    return {
        "workflow_id": "wf-1",
        "template_id": "tpl-1",
        "messages": [HumanMessage(content="do a thing")],
        "metadata": RunMetadata(
            workflow_id="wf-1",
            template_id="tpl-1",
            llm_resolution=LLMResolution(
                provider="deepseek", model="deepseek-v4-flash", rung="capability config"
            ),
        ),
    }


def test_the_planner_hands_its_failure_to_the_run_when_the_provider_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plan_node is FATAL (node grades, 2026-10-07): the plan IS the node's purpose, so an LLM
    failure here is the RUN's, not a per-item detail. The node RE-RAISES the provider's own
    exception — never a categorised one — and the run-level gate says the ONE sentence, naming
    the row the run RESOLVED.

    The sentence is the guard that did not move: on the retired organ it was
    `Provider 'Unknown' operation failed: …` (the class-name "provider"), and the run-level gate
    is now its only voice.
    """
    error = _ProviderError("upstream refused")
    monkeypatch.setattr(enhanced_nodes, "get_llm", lambda: _FailingLLM(error))

    with pytest.raises(_ProviderError) as caught:
        enhanced_nodes.plan_node(_state_with_resolution())

    assert caught.value is error, "the node must hand the run the provider's own exception"

    statement = run_failure_statement(_state_with_resolution()["metadata"], caught.value)
    assert statement == (
        "Deepseek V4 Flash (deepseek) is not functioning properly — "
        "the provider reported: upstream refused. You can have Exa attempt diagnosis (ask Exa)."
    )
    assert "Unknown" not in statement


def test_the_run_names_nobody_when_the_failure_is_not_the_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An app error is not the provider's: the raw exception reaches the run unchanged (G4-F5).

    The run carries a resolution, so naming it here would finger an innocent service — the exact
    false name the gate exists to prevent.
    """
    error = RuntimeError("boom")
    monkeypatch.setattr(enhanced_nodes, "get_llm", lambda: _FailingLLM(error))

    with pytest.raises(RuntimeError) as caught:
        enhanced_nodes.plan_node(_state_with_resolution())

    assert caught.value is error
    assert run_failure_statement(_state_with_resolution()["metadata"], caught.value) is None


def test_retryability_is_the_shared_taxonomy_never_a_list_in_the_node() -> None:
    """`retryable` used to be a flag the planner RETURNED. Under the fatal grade the decision
    lives where it is acted on — the shared taxonomy, read by the kind's RetryPolicy
    (`error_handling/policy_injector.py`) before the run fails.
    """
    from app.workflows.error_handling.taxonomy import contract_for, is_retryable

    assert is_retryable(TimeoutError("took too long")) is True
    assert is_retryable(ValueError("bad config")) is False

    retry_on = contract_for("chain").to_retry_policy().retry_on
    assert retry_on(TimeoutError("took too long")) is True
    assert retry_on(ValueError("bad config")) is False


def test_a_failed_run_state_carries_the_message_shape_the_detail_reads() -> None:
    """The run detail reads `execution_result.error_details.message` — the UI's consumed shape.

    (`frontend/src/services/domains/llm/workflowService.ts` prefers it as the user-friendly
    message.) A fatal node no longer returns that state itself, so the FRAME writes it — one
    shape for both failure paths. Without it a fatal failure's detail held only the raw string.
    """
    from app.workflows.api.workflow_router import _failure_state

    initial = _state_with_resolution()

    raw = _failure_state(initial, "wf-1", "boom")
    assert raw["execution_result"]["error_details"]["message"] == "boom"
    assert raw["metadata"].status == "error"
    assert raw["metadata"].failure_statement is None

    named = _failure_state(
        initial, "wf-1", "upstream refused",
        failure_statement="Deepseek V4 Flash (deepseek) is not functioning properly",
    )
    assert named["execution_result"]["error_details"]["message"].startswith("Deepseek")
    assert named["metadata"].failure_statement is not None


def test_get_llm_re_raises_the_raw_exception_not_a_categorised_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retired organ wrapped every non-`NoProviderConfiguredError` in an `LLMHealthError`.

    The honest report is the exception itself, so the caller sees what actually happened.
    """
    boom = _ConstructionError("client construction exploded")

    async def fake(db: Any, capability: str, **kwargs: Any) -> Any:
        raise boom

    monkeypatch.setattr(llm_factory, "get_llm_for_capability", fake)

    with pytest.raises(_ConstructionError) as caught:
        enhanced_nodes.get_llm()

    assert caught.value is boom


def test_the_file_clerk_factory_re_raises_raw_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The flagged file-clerk family had the same wrap; it too now re-raises the original.

    NOTHING ELSE in that file is asserted here — its dead-port `ChatOllama` branch and its
    `gpt-4o-mini` fallback are the banked *EMBEDDED LLM LITERALS* item's, deliberately untouched.
    """
    from app.domain.providers.config_service import DefaultProviderService
    from app.workflows.nodes import file_clerk_nodes

    boom = _ConstructionError("default provider service exploded")

    def no_ollama(*args: Any, **kwargs: Any) -> Any:
        raise ImportError("ollama client unavailable")

    monkeypatch.setattr("langchain_ollama.ChatOllama", no_ollama)

    async def exploding(self: Any, db: Any) -> Any:
        raise boom

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", exploding)

    with pytest.raises(_ConstructionError) as caught:
        file_clerk_nodes._get_llm()

    assert caught.value is boom


def test_the_no_provider_error_speaks_the_capability_world() -> None:
    """Register #8: the refusal names the CAPABILITY and its page, not the old ladder's rung.

    The retired copy — "No default LLM provider configured … Initialize Default …
    OPENAI_API_KEY" — described a ladder rung that is no longer first: a capability names its
    own service, and `/providers/capabilities` is the page that changes it.
    """
    from app.domain.providers.capabilities import NoProviderConfiguredError

    text = str(NoProviderConfiguredError("workflow-llm"))

    assert "workflow-llm" in text
    assert "/providers/capabilities" in text
    for gone in ("default LLM provider", "Initialize Default", "OPENAI_API_KEY"):
        assert gone not in text, f"the old world's wording is back: {gone!r}"

    # The no-capability form (a factory that never asked the capability — file_clerk's) still
    # constructs and still points at the page.
    bare = NoProviderConfiguredError()
    assert bare.capability is None
    assert "/providers/capabilities" in str(bare)

