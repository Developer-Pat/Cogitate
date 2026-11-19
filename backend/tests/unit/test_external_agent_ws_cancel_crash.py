"""A cancel racing a crash closes the broken subprocess instead of leaking it.

LIVE FINDING: a cancel racing a naturally-ending turn crashed the ACP
supervisor's background task (RequestError: Internal error) — the
stream ended with an EXCEPTION, not a clean interrupt. The old
_halt_agent saw 'stream ended' and wrongly concluded the gentle
interrupt worked, leaving a broken-but-alive subprocess for the next
prompt (the freeze).

THE FIX: the stream flags stream_crashed when it dies with an
exception AFTER a cancel; _halt_agent then CLOSES (kills) the
subprocess so the next prompt respawns fresh.

This test drives the real router with a fake `hermes acp` that:
- answers initialize/session-new normally
- streams one message on prompt (mid-turn)
- on session/cancel emits a MALFORMED line (the reader raises —
  the ACP supervisor crash) while KEEPING the process alive
  (still reading stdin) — the freeze pattern exactly.
"""
import asyncio
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.external_agent import AcpClient
from app.api.v1.external_agent_router import router as external_agent_router

app = FastAPI()
app.include_router(external_agent_router)

CRASH_ON_CANCEL = r"""
import json, sys


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "crashy-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "crashy-1",
            "update": {"size": 100, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        # stream ONE chunk (mid-turn), then wait for the cancel
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "crashy-1",
            "update": {"content": {"type": "text", "text": "starting..."}, "sessionUpdate": "agent_message_chunk"},
        }})
        for line in sys.stdin:
            msg2 = json.loads(line)
            if msg2["method"] == "session/cancel":
                # THE CRASH: a malformed line makes the reader raise
                # (the supervisor's RequestError) while we STAY ALIVE
                # reading stdin — the broken-but-alive freeze.
                sys.stdout.write("this is not json\n")
                sys.stdout.flush()
"""


def _patch(monkeypatch, client):
    """Force the router's runtime-imported get_acp_client to return our client."""
    import app.api.v1.external_agent_router as rtr
    import app.domain.external_agent as domain

    monkeypatch.setattr(rtr, "get_acp_client", lambda *a, **k: client)
    monkeypatch.setattr(domain, "get_acp_client", lambda *a, **k: client)

    # the ACTIVE path: Exa ships inactive (2026-11-18)
    async def _fake_get_config(_db):
        return domain.ExternalAgentConfig(enabled=True)

    async def _fake_db():
        yield None

    monkeypatch.setattr(rtr, "get_config", _fake_get_config)
    monkeypatch.setattr(rtr, "_db", _fake_db)


def _next_status(ws, timeout=12.0):
    """Read WS events until a status arrives."""
    import threading
    end = time.time() + timeout
    while time.time() < end:
        ev = ws.receive_json()
        if ev.get("type") == "status":
            return ev["status"]
    raise AssertionError("no status within timeout")


def _wait_for(fn, timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.1)
    return False


def test_ws_cancel_racing_crash_closes_the_broken_subprocess(monkeypatch, tmp_path):
    """The crash-on-cancel: the stream dies with an exception after the
    cancel -> the subprocess is CLOSED (killed), not left alive-but-frozen."""
    import pathlib
    script = pathlib.Path(tmp_path) / "crashy_acp.py"
    script.write_text(CRASH_ON_CANCEL, encoding="utf-8")

    client = AcpClient(command=["python3", str(script)], cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            ev = ws.receive_json()
            assert ev["type"] in ("message", "thought", "tool_call")
            # cancel — the fake crashes its stream but stays alive
            ws.send_json({"type": "cancel"})
            assert _next_status(ws) == "cancelled"
            # THE POINT: the broken subprocess is closed, not reused.
            # (with the old code, client.connected stayed True — the
            # frozen client — and the next prompt would hang)
            assert _wait_for(lambda: client.connected is False, timeout=12.0)
            assert client.session_id is None
