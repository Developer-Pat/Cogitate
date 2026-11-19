"""Exa workspace delivery: the inbox routes to the desktop, and unknown recipients fail.

- the exa-inbox delivery mode files a product into the workspace
  inbox (not a DB agent's folder)
- the recipient 'external' (the external-agent surface id) also
  routes to the desktop
- an unknown recipient still fails via the registry (the strict
  white pages — the desktop special-case doesn't weaken it)
"""
import pytest

from app.workflows.distribution.distributors import AgentDistributor
from app.workflows.distribution.models import WorkflowProduct


def _product(recipient):
    return WorkflowProduct(
        product_type="system-check",
        title="System Check",
        body="Status: inconsistent.",
        source_template="system-audit",
        created_at="2026-08-20T00:00:00Z",
        meta={"recipient_agent": recipient},
    )


def test_exa_inbox_delivery(tmp_path, monkeypatch):
    # point the workspace at the temp dir
    from app.core.config import Paths as _Paths
    monkeypatch.setattr(_Paths, "exa_workspace", tmp_path / ".exa-workspace")

    d = AgentDistributor()
    r = d.deliver(_product("exa"))
    assert r.success is True
    assert "desktop" in r.detail
    # the file exists in the workspace inbox
    files = list((tmp_path / ".exa-workspace" / "inbox").glob("*.md"))
    assert len(files) == 1
    assert "System Check" in files[0].read_text()


def test_external_recipient_routes_to_the_desktop(tmp_path, monkeypatch):
    from app.core.config import Paths as _Paths
    monkeypatch.setattr(_Paths, "exa_workspace", tmp_path / ".exa-workspace")

    d = AgentDistributor()
    r = d.deliver(_product("external"))
    assert r.success is True
    assert (tmp_path / ".exa-workspace" / "inbox").exists()


def test_unknown_recipient_still_fails(tmp_path, monkeypatch):
    # the desktop special-case must NOT weaken the strict registry
    d = AgentDistributor()
    r = d.deliver(_product("no-such-agent-xyz"))
    assert r.success is False
    assert "registry" in r.detail or "resolve" in r.detail


def test_paths_exa_workspace_exists():
    from app.core.config import Paths
    assert str(Paths.exa_workspace).endswith(".exa-workspace")
