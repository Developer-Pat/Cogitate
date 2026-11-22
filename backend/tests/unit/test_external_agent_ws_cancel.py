"""Cancelling an idle or in-flight run closes the subprocess, and a later prompt respawns.

The panel's WebSocket protocol now accepts {"type": "cancel"} both idle
(subprocess closed) and mid-prompt (subprocess killed — the only
reliable halt for an ACP turn that runs to completion otherwise).
Tests drive the real router with a fake `hermes acp` subprocess via
monkeypatched package names (the handler re-imports get_acp_client /
get_config from app.domain.external_agent at call time).
"""

import asyncio
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.external_agent import AcpClient
from app.domain.external_agent.schemas import ExternalAgentConfig
from app.api.v1.external_agent_router import router as external_agent_router

from tests.unit.test_external_agent import RUNAWAY_ACP


app = FastAPI()
app.include_router(external_agent_router)

RUNNING = "runaway-acp"
RUNNING_ACP = RUNAWAY_ACP.replace('"runaway-1"', f'"{RUNNING}-1"')


@pytest.fixture
def runaway_script(tmp_path):
    script = tmp_path / "runaway_acp.py"
    script.write_text(RUNNING_ACP, encoding="utf-8")
    return ["python3", str(script)]


def _patch(monkeypatch, client: AcpClient):
    """Point the handler at our fake client/config.

    The router imports get_acp_client at MODULE level, so the handler
    must be patched on the router module, not the package. get_config /
    command_parts are re-imported fresh inside the handler (package
    attrs), and _db() is the router's own dependency.
    """
    monkeypatch.setattr(
        "app.api.v1.external_agent_router.get_acp_client",
        lambda *a, **k: client,
    )

    async def _fake_get_config(db):
        # the ACTIVE path: Exa ships inactive (2026-11-18), so these tests say
        # so instead of riding on a default that is now False
        return ExternalAgentConfig(enabled=True)

    monkeypatch.setattr("app.api.v1.external_agent_router.get_config", _fake_get_config)

    async def _fake_db():
        yield None

    monkeypatch.setattr("app.api.v1.external_agent_router._db", _fake_db)

    # THE CREDENTIAL GUARD (2026-11-22): the handler refuses a turn whose runtime has no usable
    # model BEFORE the stream starts, reading the REAL isolated home. These tests are about the
    # stream's mechanics, and their fixture home has no model, so the guard is neutralised here —
    # its own facts are pinned in test_exa_activation.py, and one WS-level test below proves the
    # error frame it emits.
    monkeypatch.setattr(
        "app.domain.external_agent.activation.pre_turn_refusal", lambda *a, **k: None
    )


def _wait_for(fn, timeout=5.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return True
        time.sleep(interval)
    return False


def _next_status(ws) -> str:
    """Receive until a status frame arrives (skips streamed chunks)."""
    while True:
        msg = ws.receive_json()
        if msg.get("type") == "status":
            return msg["status"]


def test_ws_idle_cancel_closes_subprocess(monkeypatch, runaway_script, tmp_path):
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            # handler spawns the agent on first connect
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "cancel"})
            assert _next_status(ws) == "cancelled"
    # the subprocess was terminated by close()
    assert _wait_for(lambda: client.connected is False)
    assert client.session_id is None


def test_ws_in_flight_cancel_kills_runaway(monkeypatch, runaway_script, tmp_path):
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            # first streamed chunk arrives (agent is mid-turn)
            ev = ws.receive_json()
            assert ev["type"] in ("message", "thought", "tool_call")
            # halt mid-flight
            ws.send_json({"type": "cancel"})
            assert _next_status(ws) == "cancelled"
            # the runaway subprocess is dead — this is the whole point.
            # The runaway fake IGNORES session/cancel (it has no ACP
            # handling), so the halt escalates after CANCEL_GRACE_SECONDS
            # (5s) then closes. MUST wait INSIDE the WS context: the
            # receiver's _halt_agent is a background task on TestClient's
            # portal loop — exiting the context tears the loop down and
            # cancels it before the escalation can run.
            assert _wait_for(lambda: client.connected is False, timeout=12.0)
            assert client.session_id is None


def test_ws_nuke_kills_runaway_immediately(monkeypatch, runaway_script, tmp_path):
    """NUKE: process-group SIGKILL — the runaway dies without waiting
    for the cancel grace. Targeted by ownership (start_new_session),
    so it can never touch the backend / VS Code / CLI."""
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            ev = ws.receive_json()
            assert ev["type"] in ("message", "thought", "tool_call")
            # nuke mid-flight — no grace, no session/cancel, straight kill
            ws.send_json({"type": "nuke"})
            assert _next_status(ws) == "cancelled"
            # MUCH faster than the 5s cancel grace — nuke is immediate
            assert _wait_for(lambda: client.connected is False, timeout=3.0)
            assert client.session_id is None


def test_ws_turn_time_limit_halts_and_reports(monkeypatch, runaway_script, tmp_path):
    """Whole-turn cap (2026-08-14): a turn that exceeds max_turn_seconds
    is auto-halted via the same two-stage path as Stop and reports a
    DISTINCT 'time_limit' status (not 'cancelled') so the panel can
    explain WHY the run stopped."""
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)
    # override the fake config with a 1-second cap
    async def _capped_config(db):
        return ExternalAgentConfig(max_turn_seconds=1, enabled=True)
    monkeypatch.setattr("app.api.v1.external_agent_router.get_config", _capped_config)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            ev = ws.receive_json()
            assert ev["type"] in ("message", "thought", "tool_call")
            # the 1s cap fires while the runaway is mid-turn → the
            # panel gets time_limit, not cancelled (user didn't stop it)
            status = _next_status(ws)
            assert status == "time_limit"
            assert _wait_for(lambda: client.connected is False, timeout=12.0)
            assert client.session_id is None


def test_ws_prompt_after_cancel_respawns(monkeypatch, runaway_script, tmp_path):
    """A prompt after a cancel must respawn the agent fresh (the handler
    re-runs start() when the subprocess is gone)."""
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "cancel"})
            assert _next_status(ws) == "cancelled"
            assert _wait_for(lambda: client.connected is False)
            assert client.session_id is None

            # next prompt → handler respawns the agent
            ws.send_json({"type": "prompt", "text": "again"})
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ev = ws.receive_json()
            assert ev["type"] in ("message", "thought", "tool_call")
            assert _wait_for(lambda: client.connected is True)


def test_ws_a_refused_turn_ends_with_an_error_frame_and_no_stream(monkeypatch, runaway_script, tmp_path):
    """The credential guard is the difference between a named refusal and a silent 900s hang."""
    client = AcpClient(command=runaway_script, cwd=str(tmp_path))
    _patch(monkeypatch, client)
    monkeypatch.setattr(
        "app.domain.external_agent.activation.pre_turn_refusal",
        lambda *a, **k: "Exa's model cannot be called: ANTHROPIC_API_KEY is empty (test)",
    )

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            frame = ws.receive_json()
            assert frame["type"] == "status"
            assert frame["status"] == "error"
            assert "ANTHROPIC_API_KEY" in frame["message"]
