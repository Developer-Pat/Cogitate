"""Langfuse observability — the manager, the client, the traced compilation, and the debug routes.

The two route/composition tests run everywhere; the three Langfuse tests skip unless tracing is
configured, because "credentials are absent" is not a result — a test that passes whether or not it
worked is a test that cannot fail, which is what these five were before the skip marker.
"""

from __future__ import annotations

import os

import pytest

from app.workflows.observability import LangfuseManager

requires_langfuse = pytest.mark.skipif(
    not LangfuseManager.is_enabled(), reason="Langfuse is not configured on this machine"
)


@requires_langfuse
def test_langfuse_configuration() -> None:
    """The manager reports enabled only when both keys are present."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    assert LangfuseManager.is_enabled(), "the skip marker said enabled, the manager says not"
    assert public_key, "is_enabled() is true with no LANGFUSE_PUBLIC_KEY"
    assert secret_key, "is_enabled() is true with no LANGFUSE_SECRET_KEY"


@requires_langfuse
def test_langfuse_client() -> None:
    """get_client() builds a client rather than degrading to None."""
    client = LangfuseManager.get_client()
    assert client is not None, "tracing is enabled but get_client() returned None"


@requires_langfuse
def test_langfuse_handler() -> None:
    """The LangChain callback handler is built, linked to the trace the app passes it.

    The session and user ride the run config's `langfuse_*` metadata keys (see `with_run_metadata`),
    not this call — passing `session_id` here raised TypeError and the old test swallowed it.
    """
    handler = LangfuseManager.get_langfuse_handler(trace_id="test-workflow-123")
    assert handler is not None, "tracing is enabled but the callback handler was None"


def test_debug_endpoints() -> None:
    """The workflow debug routes are registered on the app the user-facing server runs.

    Checked against the MAIN app: the workflow module also builds a bare test app with no
    `/api/v1` prefix, so reading routes off that one reports every route missing.
    """
    from app.main import app

    routes = {route.path for route in app.routes}
    for path in (
        "/api/v1/workflows/{workflow_id}/debug/state",
        "/api/v1/workflows/{workflow_id}/debug/trace",
    ):
        assert path in routes, f"debug route not registered: {path}"


def test_workflow_compilation_with_tracing() -> None:
    """The workflow graph compiles with tracing wired in."""
    from app.workflows.api.workflow_router import compile_workflow

    compiled = compile_workflow()
    assert compiled is not None, "compile_workflow() returned None"
