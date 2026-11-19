#!/usr/bin/env python3
"""Langfuse rung 1 — the local sink: does the payload our code builds cross the wire?

THE QUESTION THIS ANSWERS. The Langfuse adapter is repaired and pinned **offline**: its tests read the
SDK's own in-memory span exporter, so the exported spans ARE the app's output — but an in-memory
exporter proves the client *recorded* the spans, never that they *left the process*. The one claim the
repair does not make is that a trace **arrives**.

This fixture closes that gap with no account, no real keys and nothing leaving the box. The SDK posts
its spans as OTLP **protobuf** to ``POST {LANGFUSE_HOST}/api/public/otel/v1/traces`` (see
``langfuse/_client/span_processor.py``), so a sink on loopback accepts that exact payload, decodes it,
and answers the questions the repair promises:

  * the workflow run's node spans carry ``run_trace_id(workflow_id)`` — the **derived** id, the same one
    the run's own record and ``/debug/trace`` name, not a random one;
  * the chat turn's root span carries its ``session.id`` and its trace name;
  * the graph's spans are parented under the run's trace, hanging from **one** root — not in a trace of
    their own (the defect the v4 ``trace_context`` linking exists to prevent);
  * nothing else crossed: exactly the two traces the two producers opened.

TWO MODES
    python3 scripts/diagnostics/langfuse_sink.py                        # the self-test (default)
    python3 scripts/diagnostics/langfuse_sink.py --serve --port 3111    # a sink to point a backend at

The self-test starts a sink on an ephemeral port, points the adapter at it, and drives the app's **two
real producers**: the chat endpoint (``api/v1/chat/router.py``, with only its LLM stream stubbed — a
model call is not what is under test) and ``run_workflow_async``
(``workflows/api/workflow_router.py``) around a compiled ``create_simple_workflow()`` graph. The single
app write that is not under test — the run's own execution-history row — is neutralized, so the
operator's database is untouched. Nothing touches the network, nothing costs anything, and no LLM is
called: only the tracing payload is under test.

WHY THE ADAPTER'S OWN SETTINGS SOURCE IS NEUTRALIZED. The adapter asks the app's ``Settings`` object
before the environment. A developer holding real keys in ``.env`` would otherwise divert the probe to a
real destination — the exact opposite of "nothing leaves the box". The self-test blanks the Settings
source for its duration and supplies the sink address through the environment only.

KEEP IT AS A FIXTURE, NOT A ONE-OFF. The arrival check has to be repeatable: this script is the
mechanism proof, and it fails loudly (non-zero exit) if a span arrives with a random trace id, a missing
parent, or a trace of its own.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import uuid
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, NamedTuple

# The app package root is backend/ — reached the same way the sweep and the other diagnostics reach it.
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# The two paths the SDK's exporter and its trace-URL builder hit, measured from the installed SDK.
_OTLP_TRACES_PATH = "/api/public/otel/v1/traces"
_PROJECTS_PATH = "/api/public/projects"
_SINK_PROJECT_ID = "local-sink"

logger = logging.getLogger("langfuse_sink")

# The project body the SDK's `api.projects.get()` parses: `Projects{data:[Project{id,name,organization,
# metadata}]}`. Hand-written from the installed models so the sink keeps no Langfuse import of its own.
_PROJECTS_BODY = json.dumps(
    {
        "data": [
            {
                "id": _SINK_PROJECT_ID,
                "name": "Local Sink",
                "organization": {"id": "org-local-sink", "name": "Local Sink"},
                "metadata": {},
            }
        ]
    }
).encode()


# ── Decoding the OTLP payload ────────────────────────────────────────────────


def _otel_value(value: Any) -> Any:
    """One protobuf ``AnyValue`` → a plain Python value (strings, numbers, bools, lists)."""
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [_otel_value(v) for v in value.array_value.values]
    if kind == "kvlist_value":
        return {kv.key: _otel_value(kv.value) for kv in value.kvlist_value.values}
    return getattr(value, kind)


def _otel_attributes(attributes: Any) -> dict[str, Any]:
    return {kv.key: _otel_value(kv.value) for kv in attributes}


def decode_export(body: bytes) -> list[dict[str, Any]]:
    """``ExportTraceServiceRequest`` bytes → a flat list of span dicts.

    Flattened so the assertions read the same shape regardless of how the SDK grouped the spans into
    resource/scope batches. ``trace_id`` / ``span_id`` / ``parent_span_id`` are hex (``parent_span_id``
    is empty on a root), which is how they must be compared against ``run_trace_id``.
    """
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    request = ExportTraceServiceRequest()
    request.ParseFromString(body)

    spans: list[dict[str, Any]] = []
    for resource_spans in request.resource_spans:
        # `scope_spans` is the current field name; the older alias is accepted defensively.
        scopes = getattr(resource_spans, "scope_spans", None) or getattr(
            resource_spans, "instrumentation_library_spans", []
        )
        for scope in scopes:
            for span in scope.spans:
                spans.append(
                    {
                        "trace_id": span.trace_id.hex(),
                        "span_id": span.span_id.hex(),
                        "parent_span_id": span.parent_span_id.hex(),
                        "name": span.name,
                        "kind": int(span.kind),
                        "attributes": _otel_attributes(span.attributes),
                    }
                )
    return spans


# ── The sink ─────────────────────────────────────────────────────────────────


class Sink:
    """In-memory collector for the OTLP batches the SDK posts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.spans: list[dict[str, Any]] = []
        self.batches = 0
        self.other_paths: list[str] = []

    def add(self, spans: list[dict[str, Any]]) -> None:
        with self._lock:
            self.spans.extend(spans)
            self.batches += 1
        logger.info("sink: batch #%d — %d span(s), %d total", self.batches, len(spans), len(self.spans))

    def note(self, path: str) -> None:
        with self._lock:
            self.other_paths.append(path)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            traces = defaultdict(int)
            for span in self.spans:
                traces[span["trace_id"]] += 1
            return {
                "batches": self.batches,
                "spans": len(self.spans),
                "traces": dict(traces),
                "other_paths": list(self.other_paths),
            }


def _make_handler(sink: Sink):
    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "langfuse-sink"

        def log_message(self, format: str, *args: Any) -> None:  # keep the sink's own output readable
            pass

        def _respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _json(self, payload: Any) -> None:
            self._respond(200, json.dumps(payload).encode(), "application/json")

        def do_POST(self) -> None:  # noqa: N802 — the stdlib's spelling
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            path = self.path.split("?", 1)[0].rstrip("/")
            if path.endswith(_OTLP_TRACES_PATH):
                try:
                    sink.add(decode_export(body))
                except Exception as exc:  # a decode fault must not look like a transport failure
                    sink.note(f"DECODE-FAILED {path}: {exc}")
                # Any 2xx is a success to the exporter; the body is not parsed by it.
                self._respond(200, b"", "application/x-protobuf")
            else:
                sink.note(f"POST {path}")
                self._respond(200, b"{}", "application/json")

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/")
            if path.endswith(_PROJECTS_PATH):
                # What `client.get_trace_url()` fetches to resolve the project id — answered so the UI
                # link resolves here exactly as it would against a real project.
                self._respond(200, _PROJECTS_BODY, "application/json")
            elif path.endswith("/sink/summary"):
                self._json(sink.summary())
            elif path.endswith("/sink/spans"):
                self._json({"spans": sink.spans})
            else:
                self._json({"ok": True, "sink": True, "path": path})

    return _Handler


def serve(sink: Sink, host: str, port: int) -> ThreadingHTTPServer:
    """Start the sink in a daemon thread; return the server so the caller can read the port and stop it."""
    server = ThreadingHTTPServer((host, port), _make_handler(sink))
    threading.Thread(target=server.serve_forever, name="langfuse-sink", daemon=True).start()
    return server


# ── The assertions — what "the repair works" means, in observable terms ──────


class Check(NamedTuple):
    label: str
    ok: bool
    detail: str


def assert_payload(
    spans: list[dict[str, Any]],
    *,
    chat_session: str,
    run_trace_id: str,
    template_id: str,
    expect_tags: bool = True,
) -> list[Check]:
    """Every promise of the repair, read off what actually crossed the wire.

    Each check is a claim about the payload — the trace ids, the parenting, the attributes — never
    about intent. A failure here means the app sent something other than what it says it sends.

    The two traces are located differently on purpose. The run's id is the app's own derivation from
    the workflow id, so it is known up front and asserted by value. The chat turn's id is derived from
    a wall-clock stamp the route chooses itself, so it is located by the span that carries it — the
    name, the session and the shape are what the repair promises there.
    """
    checks: list[Check] = []
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in spans:
        by_trace[span["trace_id"]].append(span)

    # 1. The chat turn: exactly one root span, named, and carrying its session and its outcome.
    chat_spans = [s for s in spans if s["name"] == "agent-chat"]
    checks.append(
        Check(
            "the chat turn exported exactly one root span (" + "not a trace object plus a span)",
            len(chat_spans) == 1,
            f"chat spans={[s['name'] for s in chat_spans]} all names={sorted(s['name'] for s in spans)}",
        )
    )
    chat_trace_id = chat_spans[0]["trace_id"] if chat_spans else None
    if chat_spans:
        root = chat_spans[0]
        checks.append(
            Check(
                "the chat span carries the session it was opened with (session.id)",
                root["attributes"].get("session.id") == chat_session,
                f"session.id={root['attributes'].get('session.id')!r} expected={chat_session!r}",
            )
        )
        checks.append(
            Check(
                "the chat span carries its trace name ('agent-chat')",
                root["attributes"].get("langfuse.trace.name") == "agent-chat",
                f"name={root['attributes'].get('langfuse.trace.name')!r}",
            )
        )
        checks.append(
            Check(
                "the chat span carries the turn's outcome (attached with update, not end)",
                "langfuse.observation.output" in root["attributes"],
                f"output={root['attributes'].get('langfuse.observation.output')!r}",
            )
        )

    # 2. Exactly the two traces the two producers opened — a stray id is a span that lost its trace.
    expected = {tid for tid in (chat_trace_id, run_trace_id) if tid}
    stray = {tid: sorted(s["name"] for s in group) for tid, group in by_trace.items() if tid not in expected}
    checks.append(
        Check(
            "exactly two traces crossed (the chat turn and the run — nothing else)",
            set(by_trace) == expected and len(expected) == 2,
            f"traces={sorted(by_trace)} stray={stray}",
        )
    )

    # 3. The run's node spans carry the DERIVED id, not a random one.
    run_spans = by_trace.get(run_trace_id, [])
    run_names = {s["name"] for s in run_spans}
    checks.append(
        Check(
            f"the run's node spans arrived under run_trace_id({template_id!r})",
            bool(run_spans),
            f"spans under the derived id: {sorted(run_names)} (all traces={sorted(by_trace)})",
        )
    )
    checks.append(
        Check(
            "the compiled graph's nodes are the spans that arrived (planner + executor)",
            {"planner", "executor"} <= run_names,
            f"names={sorted(run_names)}",
        )
    )

    # 4. The graph's spans hang from ONE top-level span inside the run's trace. The top-level span's
    #    own parent is the SDK's synthetic remote-parent marker (a random id minted from the
    #    ``trace_context`` trace id — ``_create_remote_parent_span``), which is by design and never
    #    present in the export; if a second span's parent were outside the trace, that node opened a
    #    trace of its own, which is the defect the ``trace_context`` link exists to prevent.
    ids = {s["span_id"] for s in run_spans}
    tops = [s for s in run_spans if s["parent_span_id"] not in ids]
    node_parents = {
        s["parent_span_id"] for s in run_spans if s["name"] in {"planner", "executor"}
    }
    checks.append(
        Check(
            "the run's trace has ONE top-level span (the graph run is the root of its own trace)",
            len(tops) == 1,
            f"tops={[s['name'] for s in tops]} of {sorted(run_names)}",
        )
    )
    checks.append(
        Check(
            "the graph's nodes hang from one parent span that IS in the trace",
            len(node_parents) == 1 and all(p in ids for p in node_parents),
            f"node parents={sorted(node_parents)} trace span ids={sorted(ids)}",
        )
    )

    # 5. The trace identity the run config carries reached the wire: the name (and tags) on the spans.
    observed_names = {s["attributes"].get("langfuse.trace.name") for s in run_spans}
    checks.append(
        Check(
            f"the run's trace name is 'workflow:{template_id}' on every run span",
            observed_names == {f"workflow:{template_id}"} and bool(run_spans),
            f"observed={sorted(str(n) for n in observed_names)}",
        )
    )
    if expect_tags:
        tag_values = {tuple(s["attributes"].get("langfuse.trace.tags") or []) for s in run_spans}
        checks.append(
            Check(
                "the run's template tag reached the trace",
                tag_values == {(template_id,)} and bool(run_spans),
                f"observed={sorted(tag_values)}",
            )
        )

    return checks


# ── The two producers, driven for real ───────────────────────────────────────


async def drive_chat_turn(session_id: int, agent_id: int) -> None:
    """Run the app's real chat endpoint — the tracing wrapper around a stubbed LLM stream.

    ``chat_stream`` is called directly (its `Depends` service is never fabricated) with a single stub:
    ``generate_stream``, the LLM consumer. The tracing wrapper around it — the code under test — is the
    real one, byte for byte. The trace id is the route's own business (it derives it from its own
    clock), so this returns nothing: the payload is read back from the sink.
    """
    from app.api.v1.chat import router as chat_router

    request = chat_router.ChatRequestModel(agent_id=agent_id, message="langfuse sink probe", session_id=session_id)

    async def _stub_stream(_request: Any, _service: Any):
        yield "data: probe\n\n"
        yield "data: probe\n\n"

    original = chat_router.generate_stream
    chat_router.generate_stream = _stub_stream  # type: ignore[assignment]
    try:
        response = await chat_router.chat_stream(request, object())  # type: ignore[arg-type]
        async for _chunk in response.body_iterator:
            pass
    finally:
        chat_router.generate_stream = original  # type: ignore[assignment]


async def drive_workflow_run(workflow_id: str, template_id: str) -> None:
    """Run the app's real workflow producer around a compiled ``create_simple_workflow()`` graph.

    ``run_workflow_async`` is the function that owns the tracing producer (the handler, the run
    metadata, the flush). Its one non-tracing side effect — the execution-history row — is neutralized
    so this probe leaves the operator's database alone. The graph is the app's own Hello-World workflow
    (its nodes are plain state transforms, so no LLM is needed).
    """
    from importlib import import_module

    from langgraph.checkpoint.memory import MemorySaver

    from app.workflows.graphs.simple_workflow import create_simple_workflow
    from app.workflows.state.workflow_state import RunMetadata

    # `app.workflows.api.__init__` rebinds its `workflow_router` name to the APIRouter object, so the
    # module has to be fetched by name rather than through the package attribute.
    workflow_router = import_module("app.workflows.api.workflow_router")

    compiled = create_simple_workflow().compile(checkpointer=MemorySaver())
    initial_state = {
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
    config = {"configurable": {"thread_id": workflow_id}}

    original_complete = workflow_router.record_execution_complete
    workflow_router.record_execution_complete = lambda *a, **k: None  # type: ignore[assignment]
    try:
        await workflow_router.run_workflow_async(
            compiled, initial_state, config, workflow_id, trace_level="release"
        )
    finally:
        workflow_router.record_execution_complete = original_complete  # type: ignore[assignment]


# ── The self-test ────────────────────────────────────────────────────────────


class _BlankSettings:
    """An empty Settings stand-in: keeps a real `.env` from diverting the probe."""

    langfuse_public_key = ""
    langfuse_secret_key = ""
    langfuse_host = ""
    langfuse_tracing_enabled = None


def _print_spans(spans: list[dict[str, Any]]) -> None:
    print("\n  what crossed the wire")
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in spans:
        by_trace[span["trace_id"]].append(span)
    for trace_id, group in by_trace.items():
        print(f"  trace {trace_id}")
        for span in group:
            parent = span["parent_span_id"] or "(root)"
            attrs = {
                k: v
                for k, v in span["attributes"].items()
                if k in {"session.id", "langfuse.trace.name", "langfuse.trace.tags", "langfuse.observation.output"}
            }
            print(f"    {span['name']:<18} span={span['span_id']} parent={parent} {attrs}")


def self_test(show_spans: bool) -> int:
    """The rung-1 mechanism proof. Returns a process exit code (0 = every promise held)."""
    from app.core import config as app_config
    from app.workflows.observability.langfuse_config import LangfuseManager

    sink = Sink()
    server = serve(sink, "127.0.0.1", 0)
    host = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"  sink listening on {host}{_OTLP_TRACES_PATH}")

    public_key = f"pk-lf-sink-{uuid.uuid4().hex}"
    real_settings = app_config.get_settings

    # THE ENVIRONMENT IS NOT OURS TO ASSUME. Something in the app's OWN import chain copies the
    # whole `.env` into `os.environ`: litellm calls `load_dotenv()` at import time, and the app
    # imports litellm as soon as the providers layer is touched. So a developer's real keys AND
    # their destination are already in the environment here, and a probe that only overwrote the
    # names it thought about still went to the real project — measured: `.env`'s `LANGFUSE_BASE_URL`
    # outranked the sink's `LANGFUSE_HOST`, and the sink saw nothing while the real host answered
    # 401 for the dummy keys. Clearing the whole family for the probe's duration is the isolation.
    saved_env = {k: v for k, v in os.environ.items() if k.startswith("LANGFUSE")}
    for name in list(saved_env):
        os.environ.pop(name, None)

    os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
    os.environ["LANGFUSE_SECRET_KEY"] = f"sk-lf-sink-{uuid.uuid4().hex}"
    os.environ["LANGFUSE_HOST"] = host
    app_config.get_settings = lambda: _BlankSettings()  # type: ignore[assignment]

    # A fresh client against the sink: the SDK caches one per public key and reads the host at build time.
    LangfuseManager._client = None

    session_id = 4242
    agent_id = 1
    workflow_id = f"wf-sink-{uuid.uuid4().hex[:8]}"
    template_id = "hello-world"
    run_trace_id = LangfuseManager.run_trace_id(workflow_id)

    failures = 0
    try:
        import asyncio

        print("  driving the chat turn (the real chat endpoint, its LLM stream stubbed)…")
        asyncio.run(drive_chat_turn(session_id, agent_id))

        print(f"  driving the workflow run ({workflow_id} / {template_id})…")
        asyncio.run(drive_workflow_run(workflow_id, template_id))

        LangfuseManager.flush()
        spans = list(sink.spans)

        print(f"\n  {len(spans)} span(s) in {sink.batches} batch(es) arrived")
        if show_spans:
            _print_spans(spans)

        checks = assert_payload(
            spans,
            chat_session=str(session_id),
            run_trace_id=run_trace_id,
            template_id=template_id,
        )
        print("\n  assertions")
        for check in checks:
            mark = "PASS" if check.ok else "FAIL"
            print(f"    [{mark}] {check.label}")
            if not check.ok:
                print(f"           {check.detail}")
                failures += 1

        # The UI link this rung makes testable: get_trace_url resolves against the sink's project route.
        url = LangfuseManager.trace_url(run_trace_id)
        link_ok = bool(url) and url.endswith(run_trace_id)
        print(f"    [{'PASS' if link_ok else 'FAIL'}] get_trace_url resolves against the sink: {url}")
        if not link_ok:
            failures += 1
    finally:
        LangfuseManager.shutdown()
        app_config.get_settings = real_settings  # type: ignore[assignment]
        for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
            os.environ.pop(name, None)
        os.environ.update(saved_env)  # what the app's own imports had put there
        server.shutdown()
        server.server_close()

    print()
    if failures:
        print(f"  RESULT: FAIL — {failures} assertion(s) did not hold")
        return 1
    print("  RESULT: PASS — the payload the app builds is the payload that crosses the wire")
    return 0


# ── Entry point ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="  %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="run the sink as a server instead of the self-test (point LANGFUSE_HOST at it)",
    )
    parser.add_argument("--port", type=int, default=3111, help="port for --serve (default 3111; 0 picks a free one)")
    parser.add_argument("--host", default="127.0.0.1", help="host for --serve (default 127.0.0.1)")
    parser.add_argument("--print-spans", action="store_true", help="dump the decoded spans after the self-test")
    args = parser.parse_args(argv)

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Langfuse rung 1 — the local sink (nothing leaves the box) ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    if args.serve:
        sink = Sink()
        server = serve(sink, args.host, args.port)
        host = f"http://{args.host}:{server.server_address[1]}"
        print(f"  sink serving on {host}")
        print(f"  point the app at it:  LANGFUSE_HOST={host}  (plus any non-empty key pair)")
        print(f"  inspect what arrived: curl {host}/sink/summary  |  {host}/sink/spans")
        print("  Ctrl-C to stop\n")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            print("\n  stopping")
        finally:
            server.shutdown()
            server.server_close()
        return 0

    return self_test(args.print_spans)


if __name__ == "__main__":
    raise SystemExit(main())
