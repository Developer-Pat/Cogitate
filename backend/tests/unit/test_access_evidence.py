"""The access-evidence and verify-http-evidence tests.

- the middleware writes `method path status` lines to the journal
- the journal rotates (the startup call)
- verify-http-evidence finds evidence by method + path substring
- the negative case (no matching request) reports found: False
"""
import asyncio
import pytest

from app.core.access_evidence import AccessEvidenceMiddleware, rotate_access_file


class _FakeCallNext:
    def __init__(self, status=200):
        self.status = status

    async def __call__(self, request):
        class _Resp:
            status_code = self.status
        return _Resp()


class _FakeRequest:
    def __init__(self, method="GET", path="/api/v1/x", query=""):
        self.method = method
        self.url = type("U", (), {"path": path, "query": query})()


@pytest.mark.asyncio
async def test_middleware_writes_the_journal(tmp_path):
    journal = tmp_path / "access.log"
    mw = AccessEvidenceMiddleware(None, journal)  # the app is unused in dispatch
    await mw.dispatch(_FakeRequest("POST", "/api/v1/agents", ""), _FakeCallNext(201))
    lines = journal.read_text().strip().splitlines()
    assert len(lines) == 1
    assert "POST /api/v1/agents 201" in lines[0]


@pytest.mark.asyncio
async def test_middleware_records_query_strings(tmp_path):
    journal = tmp_path / "access.log"
    mw = AccessEvidenceMiddleware(_FakeCallNext(200), journal)
    await mw.dispatch(_FakeRequest("GET", "/api/v1/agents", "page=1"), _FakeCallNext())
    lines = journal.read_text().strip().splitlines()
    assert "GET /api/v1/agents?page=1 200" in lines[0]


def test_rotation(tmp_path):
    journal = tmp_path / "access.log"
    journal.write_text("x" * 100)
    rotate_access_file(journal, max_bytes=10, backups=2)
    assert not journal.exists()
    assert (tmp_path / "access.log.1").exists()


@pytest.mark.asyncio
async def test_verify_http_evidence_tool(tmp_path, monkeypatch):
    from app.domain.tools.registry import ToolRegistry, init_default_registry
    import app.domain.tools.registry as reg_mod
    # point the journal at the temp file + write evidence
    monkeypatch.setattr(reg_mod, "_fix_mode_granted", lambda: True)
    import app.core.config as cfg_mod
    monkeypatch.setattr(cfg_mod.Paths, "access_log", tmp_path / "access.log")
    # write two evidence lines
    (tmp_path / "access.log").write_text(
        "2026-08-20T21:00:00+00:00 | GET /api/v1/system/audit/consistency 200\n"
        "2026-08-20T21:00:01+00:00 | POST /api/v1/triggers/3 200\n"
    )
    # monkeypatch the module-level Paths too (the handler reads it)
    from app.core.config import Paths as _Paths
    monkeypatch.setattr(_Paths, "access_log", tmp_path / "access.log")

    ToolRegistry.reset()
    reg_mod._DEFAULT_REGISTRY_INITIALIZED = False
    init_default_registry()
    reg = ToolRegistry.get_instance()
    assert "verify-http-evidence" in reg.get_all_slugs()

    r = await reg.execute_tool("verify-http-evidence", {}, {"method": "GET", "path": "/api/v1/system/audit"})
    assert r.get("found") is True
    assert r.get("count") == 1

    r2 = await reg.execute_tool("verify-http-evidence", {}, {"method": "DELETE", "path": "/api/v1/whatever"})
    assert r2.get("found") is False
