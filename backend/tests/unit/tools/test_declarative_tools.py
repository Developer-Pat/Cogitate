"""The declarative tool tier — the endpoint executor and the trust rule.

Covers the two things this arc adds:
  1. a tool described by a database row can be EXECUTED by calling its endpoint;
  2. it CANNOT reach the keyed tier (design §6 — installation is wiring, not
     authority).

The built-in path is deliberately not touched here; its own suite covers it.
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.domain.tools.declarative import (
    DEFAULT_TIMEOUT_MS,
    MAX_TIMEOUT_MS,
    execute_declarative_tool,
    is_declarative,
)


def _tool(**kw) -> SimpleNamespace:
    """A stand-in for a `Tool` row — only the declarative fields matter."""
    base = {
        "slug": "probe-declarative",
        "type": "http",
        "endpoint": "https://example.invalid/probe",
        "requires_auth": False,
        "timeout_ms": None,
        "capability": "web-search",
    }
    base.update(kw)
    return SimpleNamespace(**base)


class TestIsDeclarative:
    def test_builtin_is_not_declarative(self):
        # every seeded row carries "builtin" (measured 45/45) — the discriminator
        assert is_declarative("builtin") is False

    def test_declarative_kinds(self):
        for t in ("http", "declarative", "endpoint", "webhook"):
            assert is_declarative(t) is True

    def test_case_and_whitespace_tolerated(self):
        assert is_declarative("  HTTP  ") is True

    def test_absent_or_unknown_is_not_declarative(self):
        # an unknown type must not become a licence to guess
        assert is_declarative(None) is False
        assert is_declarative("") is False
        assert is_declarative("built-in") is False


class TestTimeoutResolution:
    def test_default_when_absent(self):
        from app.domain.tools.declarative import _resolve_timeout_ms
        assert _resolve_timeout_ms(None) == DEFAULT_TIMEOUT_MS

    def test_non_numeric_falls_back_loudly(self):
        from app.domain.tools.declarative import _resolve_timeout_ms
        assert _resolve_timeout_ms("soon") == DEFAULT_TIMEOUT_MS

    def test_non_positive_falls_back(self):
        from app.domain.tools.declarative import _resolve_timeout_ms
        assert _resolve_timeout_ms(0) == DEFAULT_TIMEOUT_MS
        assert _resolve_timeout_ms(-5) == DEFAULT_TIMEOUT_MS

    def test_clamped_to_the_cap(self):
        from app.domain.tools.declarative import _resolve_timeout_ms
        assert _resolve_timeout_ms(99_999_999) == MAX_TIMEOUT_MS

    def test_valid_passes_through(self):
        from app.domain.tools.declarative import _resolve_timeout_ms
        assert _resolve_timeout_ms(2500) == 2500


class TestExecution:
    @pytest.mark.asyncio
    async def test_executes_and_returns_the_payload(self):
        """The happy path: the endpoint's JSON comes back as the tool result."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            return httpx.Response(200, json={"success": True, "answer": 42})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as _:
            # execute_declarative_tool builds its own client; patch the class call
            import app.domain.tools.declarative as mod

            original = httpx.AsyncClient

            class Patched(original):
                def __init__(self, **kw):
                    kw["transport"] = transport
                    super().__init__(**kw)

            mod.httpx.AsyncClient = Patched
            try:
                result = await execute_declarative_tool(
                    tool=_tool(), arguments={"q": "x"}, config={}
                )
            finally:
                mod.httpx.AsyncClient = original

        assert result["success"] is True
        assert result["answer"] == 42

    @pytest.mark.asyncio
    async def test_no_endpoint_is_a_configuration_error(self):
        result = await execute_declarative_tool(
            tool=_tool(endpoint=None), arguments={}, config={}
        )
        assert result["success"] is False
        assert result["error_type"] == "missing_endpoint"

    @pytest.mark.asyncio
    async def test_requires_auth_without_a_credential_is_refused(self, monkeypatch):
        """An endpoint that needs auth must NOT be called without a credential."""
        monkeypatch.delenv("COGITATE_DECLARATIVE_TOOL_TOKEN", raising=False)
        result = await execute_declarative_tool(
            tool=_tool(requires_auth=True), arguments={}, config={}
        )
        assert result["success"] is False
        assert result["error_type"] == "missing_credential"

    @pytest.mark.asyncio
    async def test_unreachable_is_shaped_not_raised(self):
        """A dead endpoint must never escape as an exception into a chat turn."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        transport = httpx.MockTransport(handler)
        import app.domain.tools.declarative as mod

        original = httpx.AsyncClient

        class Patched(original):
            def __init__(self, **kw):
                kw["transport"] = transport
                super().__init__(**kw)

        mod.httpx.AsyncClient = Patched
        try:
            result = await execute_declarative_tool(
                tool=_tool(), arguments={}, config={}
            )
        finally:
            mod.httpx.AsyncClient = original

        assert result["success"] is False
        assert result["error_type"] == "unreachable"


class TestTheTrustRule:
    """Design §6: installation is wiring, not authority.

    A tool that arrives as a database row may NOT reach the keyed tier. The
    reviewed, code-registered admin tools (`restart-backend`) are keyed precisely
    because they are dangerous; an installed tool must not inherit that by
    declaring a capability.

    Enforced in `_execute_tool`, so the test drives that method directly with a
    minimal service object — no registry, no database needed for this branch.
    """

    def _service(self):
        from app.domain.tools.execution_service import ToolExecutionService

        svc = ToolExecutionService.__new__(ToolExecutionService)
        return svc

    @pytest.mark.asyncio
    async def test_declarative_keyed_tool_is_refused(self):
        svc = self._service()
        result = await svc._execute_tool(
            "installed-admin-tool",
            {},
            {},
            _tool(capability="agent-admin"),  # agent-admin is KEYED
        )
        assert result["success"] is False
        assert result["error_type"] == "declarative_keyed_refused"
        # the refusal names the reason, so the operator can act on it
        assert "keyed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_declarative_gras_tool_is_allowed_through(self):
        """A GRAS declarative tool passes the guard (and then fails on the call,
        which is what proves it got PAST the guard rather than being refused)."""
        svc = self._service()
        result = await svc._execute_tool(
            "installed-readonly-tool",
            {},
            {},
            _tool(capability="web-search", endpoint=None),
        )
        # reached the executor, which reports the missing endpoint — NOT a refusal
        assert result["error_type"] == "missing_endpoint"

    @pytest.mark.asyncio
    async def test_builtin_is_unaffected_by_the_guard(self):
        """A builtin must still route to the registry, never near this rule."""
        import app.domain.tools.declarative as decl

        svc = self._service()
        seen = {}

        class FakeRegistry:
            async def execute_tool(self, tool_slug, tool_config, arguments):
                seen["slug"] = tool_slug
                return {"success": True, "via": "registry"}

        svc.tool_registry = FakeRegistry()
        result = await svc._execute_tool(
            "datetime", {}, {}, _tool(type="builtin", capability="agent-admin")
        )
        assert seen["slug"] == "datetime"
        assert result["via"] == "registry"
