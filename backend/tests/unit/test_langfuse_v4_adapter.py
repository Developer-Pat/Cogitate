"""The v4 Langfuse adapter — what the app actually sends, read back with no keys and no network.

THE PROPERTY UNDER TEST is not "tracing is configured". It is that **the app speaks v4's language**:

* a trace id **derivable on both sides of the seam** (the app's record and the SDK's spans agree
  without either asking the other),
* **one root span per unit of work**, with its session and its name on it,
* the terminal values attached where v4 accepts them, and
* a tracing fault that changes nothing — the request's outcome, and the block around it, survive.

THE WITNESS is the SDK's own in-memory span exporter: a `Langfuse` client built with one records
what it *would* have sent, and the LangChain callback handler resolves the same per-project resource
manager, so the exported spans are the application's real output rather than a mock's opinion.

Nothing here needs keys or a network. That is the line the repair has to be honest about (see
`local/studies/langfuse-repair/01-what-v4-offers.md` §4): the call shapes are provable offline; that
the traces *arrive* is the keyed pass.
"""

import hashlib
import os
import uuid

import pytest

from app.workflows.observability.langfuse_config import LangfuseManager

_FAKE_HOST = "http://127.0.0.1:1"  # unreachable ON PURPOSE — a passing test must not need the network

_LANGFUSE_ENV = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_TRACING_ENABLED",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_HOST",
    "LANGFUSE_ENVIRONMENT",
)


def _clear_langfuse_environment(monkeypatch) -> None:
    """Take the whole LANGFUSE_* family out of ``os.environ``.

    ``litellm`` calls ``load_dotenv()`` at import, so the developer's ``.env`` is copied into the
    environment, and ``_setting`` falls back to the environment when Settings has no value. A test
    that stands in for ``Settings`` alone is therefore overruled by the machine it runs on: a
    developer with tracing switched off in ``.env`` sees these assertions fail while CI passes.
    The adapter's own docstring states the rule — a caller that redirects tracing must clear the
    family from the environment as well as stand in for Settings.
    """
    for name in _LANGFUSE_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_settings_credentials(monkeypatch):
    """Keep the Settings source empty for the environment-based tests.

    `.env` is the FIRST source the adapter asks (it reaches the Settings object and never
    `os.environ`), so a developer holding real keys in `.env` would otherwise silently override every
    `monkeypatch.setenv` here and make these tests pass for the wrong reason. A test that wants the
    Settings path re-patches `get_settings` itself, which wins over this fixture.
    """

    class _Empty:
        langfuse_public_key = ""
        langfuse_secret_key = ""
        langfuse_host = ""
        langfuse_tracing_enabled = None

    monkeypatch.setattr("app.core.config.get_settings", lambda: _Empty())


@pytest.fixture
def span_exporter(monkeypatch):
    """A real Langfuse client whose exported spans can be read, injected into the adapter.

    A **unique public key per test**, deliberately: the SDK registers its resources (tracer provider
    and exporter) per public key in a process-global manager, so a reused key would hand this test
    the previous test's exporter and make it pass for the wrong reason.
    """
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    key = f"pk-lf-test-{uuid.uuid4().hex}"
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", key)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", _FAKE_HOST)
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)

    exporter = InMemorySpanExporter()
    client = Langfuse(public_key=key, secret_key="sk-lf-test", host=_FAKE_HOST, span_exporter=exporter)
    monkeypatch.setattr(LangfuseManager, "_client", client)

    yield exporter

    LangfuseManager.shutdown()


def _exported(exporter):
    """Drain the SDK's batch processor, then read what it exported."""
    LangfuseManager.flush()
    return exporter.get_finished_spans()


# ── The id is derivable, not fetchable ───────────────────────────────────────


def test_the_trace_id_is_derivable_without_a_client_or_a_network():
    """The app can name the trace it would have sent, with tracing off.

    This is what lets a workflow run's node spans and the app's own run record be joined: both
    compute the id from the run's id.
    """
    seed = "workflow:wf-abc123"

    assert LangfuseManager.create_trace_id(seed) == hashlib.sha256(seed.encode()).hexdigest()[:32]
    assert len(LangfuseManager.create_trace_id(seed)) == 32
    assert LangfuseManager.create_trace_id(seed).isalnum()


def test_the_derived_id_is_the_id_the_sdk_itself_would_produce():
    """The cross-check: our pure function and the SDK's own `create_trace_id(seed=...)` agree."""
    from langfuse import Langfuse

    client = Langfuse(public_key="pk-lf-crosscheck", secret_key="sk-lf-crosscheck")
    for seed in ("workflow:wf-1", "chat:sess-9:1730000000.0", "x"):
        assert LangfuseManager.create_trace_id(seed) == client.create_trace_id(seed=seed)


def test_a_seedless_call_does_not_collapse_every_trace_into_one():
    """`""` is not a seed.

    The SDK reads a falsy seed as "no seed" and generates a random id; hashing the empty string
    instead would give every seedless caller the SAME id — the failure mode that looks like success,
    because the traces exist and are simply all one trace.
    """
    empty = LangfuseManager.create_trace_id("")

    assert empty != hashlib.sha256(b"").hexdigest()[:32]
    assert len(empty) == 32 and empty.isalnum()
    assert empty != LangfuseManager.create_trace_id("")
    assert LangfuseManager.create_trace_id(None) != LangfuseManager.create_trace_id(None)


# ── The switch is the SDK's own ──────────────────────────────────────────────


def test_tracing_off_when_the_keys_are_absent(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED", raising=False)

    assert LangfuseManager.is_enabled() is False
    assert LangfuseManager.get_client() is None


def test_the_keys_can_come_from_the_apps_settings(monkeypatch):
    """`.env` reaches the Settings object — and the adapter asks it FIRST.

    `Settings` reads `.env` through pydantic's `env_file`, which populates the model and not the
    environment; but the environment is not empty either, because litellm copies the whole `.env`
    into `os.environ` at import time in any process that touches the providers layer. The adapter
    resolves Settings first and passes the values to the SDK explicitly, so a declaration outranks
    that copy.
    """
    from types import SimpleNamespace

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    _clear_langfuse_environment(monkeypatch)  # the .env copy in os.environ outranks Settings
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            langfuse_public_key="pk-lf-from-settings",
            langfuse_secret_key="sk-lf-from-settings",
            langfuse_host="https://langfuse.example",
            langfuse_tracing_enabled=None,
        ),
    )

    assert LangfuseManager.is_enabled() is True

    monkeypatch.setattr(LangfuseManager, "_client", None)
    client = LangfuseManager.get_client()
    assert client is not None, "a .env-configured install must actually get a client"


def test_the_switch_can_also_come_from_settings_and_is_passed_to_the_sdk(monkeypatch):
    """One switch, resolved once — and handed to the SDK.

    Reading the switch from Settings while the SDK read its own environment variable would leave the
    two able to disagree. Resolving it in `is_enabled()` and passing `tracing_enabled=True` when the
    client is built makes that single resolution authoritative.
    """
    from types import SimpleNamespace

    base = dict(
        langfuse_public_key="pk-lf-x",
        langfuse_secret_key="sk-lf-x",
        langfuse_host="https://langfuse.example",
    )
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(**base, langfuse_tracing_enabled=False),
    )
    assert LangfuseManager.is_enabled() is False

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(**base, langfuse_tracing_enabled=True),
    )
    assert LangfuseManager.is_enabled() is True


def test_the_sdk_switch_wins_and_the_old_invented_name_is_not_consulted(monkeypatch):
    """ONE switch, the SDK's own.

    The facade used to read `LANGFUSE_ENABLED`, a name the SDK has never heard of — so the app's
    guard and the SDK's behaviour could disagree in both directions. Setting the invented name must
    no longer turn tracing back on.
    """
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-x")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-x")
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")

    assert LangfuseManager.is_enabled() is False

    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    assert LangfuseManager.is_enabled() is True


# ── With tracing off, every verb is a no-op that cannot raise ────────────────


def test_every_verb_is_a_safe_no_op_when_tracing_is_off(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    with LangfuseManager.create_trace("agent-chat", session_id="s1", trace_id="0" * 32) as span:
        assert span is None
        LangfuseManager.update(span, output={"status": "completed"})

    assert LangfuseManager.get_langfuse_handler(trace_id="0" * 32) is None
    assert LangfuseManager.run_metadata(session_id="s1") == {}
    assert LangfuseManager.with_run_metadata({"configurable": {}}, session_id="s1") == {"configurable": {}}
    assert LangfuseManager.trace_url("0" * 32) is None
    LangfuseManager.flush()


# ── One root span per unit of work ───────────────────────────────────────────


def test_a_chat_turn_exports_one_span_named_by_its_derived_id(span_exporter):
    """The chat turn's shape: the root span, its id, its session, its name, and its outcome."""
    session_id = "sess-42"
    trace_id = LangfuseManager.chat_trace_id(session_id, 1730000000.0)

    with LangfuseManager.create_trace(
        "agent-chat", session_id=session_id, trace_id=trace_id, metadata={"agent_id": 7}
    ) as span:
        assert span is not None
        LangfuseManager.update(span, output={"status": "completed"})

    spans = _exported(span_exporter)
    assert len(spans) == 1, "one root span, not a trace object plus a span"

    root = spans[0]
    assert root.name == "agent-chat"
    assert f"{root.context.trace_id:032x}" == trace_id, "the app's id IS the sent trace id"
    assert root.attributes.get("session.id") == session_id
    assert root.attributes.get("langfuse.trace.name") == "agent-chat"


def test_the_span_ends_itself_even_when_the_body_raises(span_exporter):
    """An abandoned or exploding turn still closes its span — the context manager owns that."""
    with pytest.raises(RuntimeError):
        with LangfuseManager.create_trace("agent-chat", session_id="s1") as span:
            raise RuntimeError("the turn blew up")

    spans = _exported(span_exporter)
    assert [s.name for s in spans] == ["agent-chat"]


@pytest.mark.anyio
async def test_a_streaming_turn_exports_its_outcome_and_survives_being_abandoned(span_exporter):
    """The router's own shape: a sync `with` around an async generator.

    Two turns, the second abandoned mid-stream the way a client disconnect abandons one — and each
    records what actually happened to it, because a trace that calls an interrupted turn "completed"
    is a lie the reader has no way to catch.
    """

    async def _traced_stream(session_id: str, interrupt: bool):
        trace_id = LangfuseManager.chat_trace_id(session_id, uuid.uuid4().hex)
        with LangfuseManager.create_trace(
            "agent-chat", session_id=session_id, trace_id=trace_id
        ) as _lf_span:
            _outcome: dict = {"status": "interrupted"}
            try:
                yield "chunk"
                if interrupt:
                    return
                yield "chunk"
                _outcome = {"status": "completed"}
            finally:
                LangfuseManager.update(_lf_span, output=_outcome)

    async def _consume(generator, stop_after=None):
        seen = []
        async for chunk in generator:
            seen.append(chunk)
            if stop_after is not None and len(seen) == stop_after:
                await generator.aclose()
                break
        return seen

    assert await _consume(_traced_stream("sess-1", interrupt=False)) == ["chunk", "chunk"]
    assert await _consume(_traced_stream("sess-2", interrupt=True), stop_after=1) == ["chunk"]

    spans = _exported(span_exporter)
    assert [s.name for s in spans] == ["agent-chat", "agent-chat"]

    outcomes = sorted(str(s.attributes.get("langfuse.observation.output")) for s in spans)
    assert outcomes == ['{"status": "completed"}', '{"status": "interrupted"}']
    sessions = sorted(str(s.attributes.get("session.id")) for s in spans)
    assert sessions == ["sess-1", "sess-2"]


# ── The v2 shape is now impossible, not merely unused ────────────────────────


def test_the_terminal_values_go_through_update_because_end_rejects_them(span_exporter):
    """The control for defect 6.

    v4's `end()` takes nothing but an end time, so the v2 habit — `observation.end(output=...)` —
    raises. That is why `update` exists as its own verb, and why `end_observation`'s old body was
    silently wrong at every call site it had.
    """
    with LangfuseManager.create_trace("agent-chat", session_id="s1") as span:
        with pytest.raises(TypeError):
            span.end(output={"status": "completed"})
        span.update(output={"status": "completed"})


def test_a_faulty_client_degrades_to_a_no_op_instead_of_breaking_the_turn(monkeypatch, span_exporter):
    """Tracing is an observer. A broken observer must not take the request down with it."""

    class _Exploding:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError("the SDK is unhappy")

    monkeypatch.setattr(LangfuseManager, "_client", _Exploding())

    with LangfuseManager.create_trace("agent-chat", session_id="s1") as span:
        assert span is None


# ── The debug endpoint names the run's own trace ─────────────────────────────


@pytest.mark.anyio
async def test_the_debug_trace_endpoint_returns_the_runs_own_trace_id_with_tracing_off(monkeypatch):
    """With tracing off, the id is the one useful thing this endpoint can say — and it is free.

    It is the id the run's spans WOULD carry: the same derivation, with no client and no network.
    """
    from app.workflows.api.workflow_router import get_workflow_trace

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    payload = await get_workflow_trace("wf-abc123")

    assert payload["trace_id"] == LangfuseManager.run_trace_id("wf-abc123")
    assert payload["trace_url"] is None
    assert payload["langfuse_enabled"] is False


@pytest.mark.anyio
async def test_the_debug_trace_endpoint_degrades_when_the_link_cannot_be_resolved(span_exporter):
    """The UI link needs the network — the SDK fetches the project id to build it.

    The configured host is unreachable here, which is the state a developer is most likely in. The
    endpoint must answer with the id and no URL, never a 500: a debug endpoint that dies because a
    vendor's API is down is worse than one that says less.
    """
    from app.workflows.api.workflow_router import get_workflow_trace

    payload = await get_workflow_trace("wf-abc123")

    assert payload["langfuse_enabled"] is True
    assert payload["trace_url"] is None, "a failed lookup degrades to the id alone"
    assert payload["trace_id"] == LangfuseManager.run_trace_id("wf-abc123")


# ── The write-only mirror is gone, and cannot come back quietly ─────────────


def test_the_write_only_trace_mirror_is_gone():
    """`observability/trace_store.py` had four writers and **no reader**.

    Its three query methods (`get_recent`, `get_trace`, `get_by_session`) had zero callers anywhere
    in `backend/app`, so the ring buffer held observations nothing could serve — and `node_tracing.py`
    was not even wired: `trace_node` had zero callers and was `async def` only, against 44/45 sync
    node definitions. Fixing a fifth writer onto a buffer nobody opens would have added code, not
    observability. The app's own record of a run (and Langfuse, when keyed) is the destination.

    This pins the deletion: a module that comes back has to come back with a reader.
    """
    import importlib

    for module in (
        "app.workflows.observability.trace_store",
        "app.workflows.observability.node_tracing",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)


# ── The handler path: a run and its nodes, in ONE trace ──────────────────────


def test_a_workflow_run_links_its_nodes_to_the_runs_own_trace_id(span_exporter):
    """The run's node spans and the app's own record name the same trace, from the same derivation.

    This is the half that makes a workflow legible: the graph run and every node under it arrive as
    one trace, and the run config's `langfuse_*` metadata gives that trace its name and tags.
    """
    workflow_id = "wf-abc123"
    trace_id = LangfuseManager.run_trace_id(workflow_id)

    config = LangfuseManager.with_run_metadata(
        {"configurable": {"thread_id": workflow_id}},
        trace_name="workflow:tpl-9",
        tags=["tpl-9"],
    )
    assert config["configurable"] == {"thread_id": workflow_id}, "the checkpointer keys are untouched"
    assert config["metadata"]["langfuse_trace_name"] == "workflow:tpl-9"
    assert config["metadata"]["langfuse_tags"] == ["tpl-9"]

    handler = LangfuseManager.get_langfuse_handler(trace_id=trace_id)
    assert handler is not None

    meta = config["metadata"]
    root_run, node_run = uuid.uuid4(), uuid.uuid4()
    handler.on_chain_start(
        serialized={"name": "graph"}, inputs={"user_message": "hi"},
        run_id=root_run, parent_run_id=None, metadata=meta,
    )
    handler.on_chain_start(
        serialized={"name": "resolve_namespace"}, inputs={},
        run_id=node_run, parent_run_id=root_run, metadata=meta,
    )
    handler.on_chain_end(outputs={"ok": True}, run_id=node_run)
    handler.on_chain_end(outputs={"done": True}, run_id=root_run)

    spans = _exported(span_exporter)
    assert {s.name for s in spans} == {"graph", "resolve_namespace"}
    for span in spans:
        assert f"{span.context.trace_id:032x}" == trace_id, "the node spans belong to the RUN's trace"
        assert span.attributes.get("langfuse.trace.name") == "workflow:tpl-9"


def test_the_handler_links_by_trace_context_because_the_old_attribute_is_inert(span_exporter):
    """Defect 2's control: `setattr(handler, "trace_id", ...)` was never read by v4.

    The old code set two attributes the handler ignores, so its "link" silently did nothing and the
    run's spans would have landed in a trace of their own. The test asserts the old way does NOT
    work — otherwise the repair could pass while the defect is still there.

    The public key is passed here because a handler **without** one resolves nothing in a process
    holding more than one client ("Skipping tracing ... to avoid cross-project leakage") — which is
    a second, quieter reason the old call site was wrong: it built `CallbackHandler()` with no key,
    so in any multi-project process every workflow trace was dropped without a word. That is also
    why `test_a_workflow_run_links_its_nodes_to_the_runs_own_trace_id` is a real proof: this file
    creates a client per test, so a handler that did not carry its key would export nothing there.
    """
    from langfuse.langchain import CallbackHandler

    inflated = CallbackHandler(public_key=os.getenv("LANGFUSE_PUBLIC_KEY"))
    setattr(inflated, "trace_id", "1" * 32)
    setattr(inflated, "session_id", "not-a-session")

    run = uuid.uuid4()
    inflated.on_chain_start(serialized={"name": "graph"}, inputs={}, run_id=run, parent_run_id=None)
    inflated.on_chain_end(outputs={}, run_id=run)

    spans = _exported(span_exporter)
    assert len(spans) == 1
    assert f"{spans[0].context.trace_id:032x}" != "1" * 32, "the attribute it set was never read"


# ── The two defects the local sink found: a dropped kwarg and a dropped int ──


def _hello_world_state(workflow_id: str, template_id: str) -> dict:
    """The app's own Hello-World workflow state (its nodes are plain state transforms)."""
    from app.workflows.state.workflow_state import RunMetadata

    return {
        "messages": [],
        "workflow_id": workflow_id,
        "template_id": template_id,
        "inputs": {},
        "config": None,
        "current_step": None,
        "execution_result": None,
        "outputs": None,
        "approval_required": False,
        "approval_status": None,
        "metadata": RunMetadata(workflow_id=workflow_id, template_id=template_id),
        "tool_calls_history": [],
        "tool_loop_count": 0,
        "pending_tool_calls": None,
        "current_agent_step": None,
    }


def test_a_real_langgraph_run_reads_callbacks_from_the_config_not_a_kwarg(span_exporter):
    """Defect 7's mechanism, measured: `invoke(..., callbacks=[h])` is silently inert.

    LangGraph's ``Pregel.invoke/stream`` declare ``**kwargs: Unpack[DeprecatedKwargs]`` and read only
    ``checkpoint_during`` from that channel — so a ``callbacks=`` kwarg is dropped without a word,
    while ``config["callbacks"]`` registers handlers for real. This is why ``run_workflow_async`` puts
    the handler in the run config.

    The first half asserts the kwarg form does **not** work: without that control the test would pass
    for the wrong reason and a revert to the broken call site would go unnoticed.
    """
    from app.workflows.graphs.simple_workflow import create_simple_workflow

    compiled = create_simple_workflow().compile()
    state = _hello_world_state("wf-callbacks", "hello-world")
    trace_id = LangfuseManager.run_trace_id("wf-callbacks")

    # The kwarg form — what the producer used to do. Nothing reaches the exporter.
    compiled.invoke(
        state, {"configurable": {}}, callbacks=[LangfuseManager.get_langfuse_handler(trace_id=trace_id)]
    )
    assert _exported(span_exporter) == (), "a `callbacks=` kwarg must not be enough to trace a run"

    # The config form — the one LangGraph reads. The graph run and its nodes arrive as one trace.
    compiled.invoke(
        state,
        {
            "configurable": {},
            "callbacks": [LangfuseManager.get_langfuse_handler(trace_id=trace_id)],
        },
    )
    spans = _exported(span_exporter)
    assert {"planner", "executor"} <= {s.name for s in spans}
    for span in spans:
        assert f"{span.context.trace_id:032x}" == trace_id


@pytest.mark.anyio
async def test_a_workflow_run_reaches_the_wire_through_the_real_producer(span_exporter, monkeypatch):
    """The control for that defect at the producer's own seam.

    Drives the app's real ``run_workflow_async`` — the function that owns the handler, the run
    metadata and the flush — around a compiled ``create_simple_workflow()`` graph, and asserts the
    run's node spans arrive under ``run_trace_id(workflow_id)``. Reverting the handler to the
    ``callbacks=`` kwarg makes this test fail; the rest of this file cannot see the regression because
    it hands the handler its events directly.

    The run's execution-history write is neutralized so the suite touches no database.
    """
    import importlib

    from langgraph.checkpoint.memory import MemorySaver

    workflow_router = importlib.import_module("app.workflows.api.workflow_router")
    monkeypatch.setattr(workflow_router, "record_execution_complete", lambda *a, **k: None)

    from app.workflows.graphs.simple_workflow import create_simple_workflow

    workflow_id, template_id = "wf-producer", "hello-world"
    compiled = create_simple_workflow().compile(checkpointer=MemorySaver())
    await workflow_router.run_workflow_async(
        compiled,
        _hello_world_state(workflow_id, template_id),
        {"configurable": {"thread_id": workflow_id}},
        workflow_id,
        trace_level="release",
    )

    spans = _exported(span_exporter)
    names = {s.name for s in spans}
    assert {"planner", "executor"} <= names, f"the run's nodes never reached the exporter: {sorted(names)}"
    for span in spans:
        assert f"{span.context.trace_id:032x}" == LangfuseManager.run_trace_id(workflow_id)
        assert span.attributes.get("langfuse.trace.name") == f"workflow:{template_id}"


def test_an_int_session_id_reaches_the_trace_as_its_string(span_exporter):
    """Defect 8's control: the chat route holds an INT session id, and the SDK drops non-strings.

    ``propagate_attributes`` requires a string and silently discards anything else, so
    ``session_id=request.session_id`` (``int | None``) meant no chat trace ever carried its session —
    a warning in the log and nothing on the wire. The other chat test here uses a string session and
    could never have seen it. The adapter coerces; this pins that it does.
    """
    session_id = 4242  # the type the route actually passes

    with LangfuseManager.create_trace(
        "agent-chat", session_id=session_id, trace_id=LangfuseManager.chat_trace_id(session_id, 1730000000.0)
    ) as span:
        LangfuseManager.update(span, output={"status": "completed"})

    spans = _exported(span_exporter)
    assert len(spans) == 1
    assert spans[0].attributes.get("session.id") == "4242"


# ── The destination: the current variable name, not the deprecated alias ─────


def test_the_destination_prefers_the_current_variable_and_keeps_the_deprecated_alias(monkeypatch):
    """`LANGFUSE_BASE_URL` is the SDK's current name; `LANGFUSE_HOST` is deprecated but still read.

    The adapter passes the destination to the SDK **explicitly**, and the SDK resolves
    ``base_url or LANGFUSE_BASE_URL or host or LANGFUSE_HOST or default`` — so a default chosen here
    beats every variable the SDK would have read itself. Reading only the deprecated name is how an
    installation on a regional host (``us.``/``eu.`` cloud, or self-hosted) shipped every trace to
    ``cloud.langfuse.com`` while holding the keys for the right one.
    """
    from app.workflows.observability.langfuse_config import _base_url

    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_HOST", "https://eu.cloud.langfuse.com")
    assert _base_url() == "https://us.cloud.langfuse.com", "the current name must win"

    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    assert _base_url() == "https://eu.cloud.langfuse.com", "the deprecated alias stays a source"

    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    assert _base_url() == "https://cloud.langfuse.com"


def test_the_client_is_built_for_the_configured_destination_and_environment(monkeypatch):
    """What the client is actually constructed with — the destination and the environment tag."""
    from types import SimpleNamespace

    _clear_langfuse_environment(monkeypatch)  # the .env copy in os.environ outranks Settings
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            langfuse_public_key=f"pk-lf-dest-{uuid.uuid4().hex}",
            langfuse_secret_key="sk-lf-dest",
            langfuse_base_url="https://us.cloud.langfuse.com",
            langfuse_host="https://eu.cloud.langfuse.com",
            langfuse_environment="staging",
            langfuse_tracing_enabled=None,
        ),
    )
    monkeypatch.setattr(LangfuseManager, "_client", None)

    client = LangfuseManager.get_client()
    assert client is not None
    assert client._base_url == "https://us.cloud.langfuse.com"
    assert client._environment == "staging"

    LangfuseManager.shutdown()


# ── A model call is a generation, hanging from the turn's span ───────────────


def _completion(text: str = "hi there", *, prompt: int = 7, completion: int = 3):
    """A minimal non-streamed litellm response (choices + usage)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage={"prompt_tokens": prompt, "completion_tokens": completion},
    )


def _text_chunk(piece: str):
    from types import SimpleNamespace

    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))], usage=None)


def _usage_chunk(prompt: int, completion: int):
    """The final, text-free chunk some providers send to report usage."""
    from types import SimpleNamespace

    return SimpleNamespace(choices=[], usage={"prompt_tokens": prompt, "completion_tokens": completion})


def _attr(span, key):
    import json

    raw = span.attributes.get(key)
    if isinstance(raw, str) and raw.startswith(("{", "[")):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


@pytest.mark.anyio
async def test_a_model_call_inside_a_turn_arrives_as_a_generation_under_it(span_exporter, monkeypatch):
    """The tracing baseline on the chat path: model, input, output and tokens, on a `generation`.

    A generation — not a span — because that is the observation type Langfuse prices and groups by
    model. It hangs from the turn's span, so a chat trace reads as one turn with the model calls it
    made rather than an empty root.
    """
    import app.api.v1.chat.llm_utils as llm_utils

    async def fake(**_kwargs):
        return _completion("hello there")

    monkeypatch.setattr(llm_utils, "acompletion", fake)

    trace_id = LangfuseManager.chat_trace_id("sess-1", 1.0)
    with LangfuseManager.create_trace("agent-chat", session_id="sess-1", trace_id=trace_id):
        response = await llm_utils.acompletion_with_retry(model="m", messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0].message.content == "hello there"

    spans = _exported(span_exporter)
    names = {s.name for s in spans}
    assert names == {"agent-chat", "generate-response"}, f"the turn and ONE generation: {sorted(names)}"

    root = next(s for s in spans if s.name == "agent-chat")
    generation = next(s for s in spans if s.name == "generate-response")
    assert generation.parent is not None and generation.parent.span_id == root.context.span_id, (
        "the generation hangs from the turn's span"
    )
    assert f"{generation.context.trace_id:032x}" == trace_id
    assert _attr(generation, "langfuse.observation.type") == "generation"
    assert _attr(generation, "langfuse.observation.model.name") == "m"
    assert _attr(generation, "langfuse.observation.input") == [{"role": "user", "content": "hi"}]
    assert _attr(generation, "langfuse.observation.output") == "hello there"
    assert _attr(generation, "langfuse.observation.usage_details") == {"input": 7, "output": 3}


@pytest.mark.anyio
async def test_a_streamed_model_call_is_traced_without_the_chunks_changing(span_exporter, monkeypatch):
    """The stream's generation spans the consumer's loop: the text is accumulated, the usage comes
    from the final chunk, and the caller's chunks are passed through untouched."""
    import app.api.v1.chat.llm_utils as llm_utils

    async def fake(**_kwargs):
        async def _stream():
            yield _text_chunk("Hel")
            yield _text_chunk("lo")
            yield _usage_chunk(5, 2)

        return _stream()

    monkeypatch.setattr(llm_utils, "acompletion", fake)

    with LangfuseManager.create_trace("agent-chat", session_id="sess-2", trace_id="c" * 32):
        stream = await llm_utils.acompletion_with_retry(
            model="m", messages=[{"role": "user", "content": "hi"}], stream=True
        )
        seen = [chunk async for chunk in stream]

    assert len(seen) == 3, "the chunks the provider sent are the chunks the caller gets"

    generation = next(s for s in _exported(span_exporter) if s.name == "generate-response")
    assert _attr(generation, "langfuse.observation.output") == "Hello"
    assert _attr(generation, "langfuse.observation.usage_details") == {"input": 5, "output": 2}


@pytest.mark.anyio
async def test_a_model_call_with_no_turn_open_manufactures_no_trace(span_exporter, monkeypatch):
    """The control for the skip rule: `chat_delegate` and `/completions` call the model outside any
    turn, and a generation there would become a trace of its own — one the app never opens."""
    import app.api.v1.chat.llm_utils as llm_utils

    async def fake(**_kwargs):
        return _completion()

    monkeypatch.setattr(llm_utils, "acompletion", fake)

    await llm_utils.acompletion_with_retry(model="m", messages=[{"role": "user", "content": "hi"}])

    assert _exported(span_exporter) == (), "no turn open, so nothing is traced"


@pytest.mark.anyio
async def test_each_attempt_is_its_own_generation_and_the_failed_one_is_marked(span_exporter, monkeypatch):
    """A retry is a second invocation, not a longer first one — and the attempt that was refused is
    the half of a rate-limit story that a single aggregated generation would hide."""
    import app.api.v1.chat.llm_utils as llm_utils
    from litellm.exceptions import RateLimitError

    calls = {"n": 0}

    async def fake(**_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError(message="slow down", llm_provider="openai", model="m")
        return _completion("second time")

    monkeypatch.setattr(llm_utils, "acompletion", fake)

    with LangfuseManager.create_trace("agent-chat", session_id="sess-3", trace_id="d" * 32):
        response = await llm_utils.acompletion_with_retry(
            max_retries=2, retry_delay=0, model="m", messages=[{"role": "user", "content": "hi"}]
        )

    assert response.choices[0].message.content == "second time"

    generations = [s for s in _exported(span_exporter) if s.name == "generate-response"]
    assert len(generations) == 2, "one generation per invocation"

    errored = [s for s in generations if _attr(s, "langfuse.observation.level") == "ERROR"]
    answered = [s for s in generations if _attr(s, "langfuse.observation.output") == "second time"]
    assert len(errored) == 1, "the refused attempt is marked errored"
    assert len(answered) == 1, "the retry carries the answer"
    assert "slow down" in str(_attr(errored[0], "langfuse.observation.status_message"))

