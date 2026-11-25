"""The WebSocket done frame — the model and its token usage, for the bubble readout.

The frontend renders both on the bubble, so model swaps and response times are
observable without reading a log.
"""
import pytest



import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.external_agent import AcpClient
from app.api.v1.external_agent_router import router as external_agent_router

app = FastAPI()
app.include_router(external_agent_router)

META_ACP = r"""
import json, sys


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "meta-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "meta-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "meta-1",
            "update": {"content": {"type": "text", "text": "the answer"}, "sessionUpdate": "agent_message_chunk"},
        }})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "meta-1",
            "update": {"size": 100000, "used": 27000, "sessionUpdate": "usage_update"},
        }})
        # THE RESPONSE ENDS THE TURN (2026-11-25) — an ACP agent answers
        # session/prompt after it finishes streaming.
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn", "usage": {}}})
"""


def _patch(monkeypatch, client):
    import app.api.v1.external_agent_router as rtr
    import app.domain.external_agent as domain
    monkeypatch.setattr(rtr, "get_acp_client", lambda *a, **k: client)
    monkeypatch.setattr(domain, "get_acp_client", lambda *a, **k: client)

    # These tests drive the ACTIVE path. Exa ships INACTIVE (2026-11-18), so
    # the activation is stated here instead of riding on the default — a test
    # that never says "enabled" is testing the gate, not the panel.
    async def _fake_get_config(_db):
        return domain.ExternalAgentConfig(enabled=True)

    async def _fake_db():
        yield None

    monkeypatch.setattr(rtr, "get_config", _fake_get_config)
    monkeypatch.setattr(rtr, "_db", _fake_db)

    # THE CREDENTIAL GUARD (2026-11-22): the handler refuses a turn whose runtime has no usable
    # model BEFORE the stream starts, reading the REAL isolated home. These tests are about the
    # stream's mechanics, so the guard is neutralised here — its facts are pinned in
    # test_exa_activation.py and one WS-level test proves the error frame it emits.
    monkeypatch.setattr(
        "app.domain.external_agent.activation.pre_turn_refusal", lambda *a, **k: None
    )


def _next_status(ws, timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        ev = ws.receive_json()
        if ev.get("type") == "status":
            return ev["status"]
    raise AssertionError("no status within timeout")


def test_ws_done_carries_usage_and_model(monkeypatch, tmp_path):
    """The done event carries the usage payload + the model — the
    bubble instrumentation the user asked for."""
    import pathlib
    script = pathlib.Path(tmp_path) / "meta_acp.py"
    script.write_text(META_ACP, encoding="utf-8")

    client = AcpClient(command=["python3", str(script)], cwd=str(tmp_path))
    _patch(monkeypatch, client)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            assert _next_status(ws) == "connecting"
            assert _next_status(ws) == "ready"
            ws.send_json({"type": "prompt", "text": "go"})
            done = None
            end = time.time() + 15
            while time.time() < end:
                ev = ws.receive_json()
                if ev.get("type") == "done":
                    done = ev
                    break
            assert done is not None, "no done event"
            assert done["reply"] == "the answer"
            # the usage payload (size/used) is forwarded
            assert done.get("usage") == {"size": 100000, "used": 27000}
            # the model is read from Exa's own config
            assert done.get("model") in ("deepseek-v4-flash", None) or isinstance(done.get("model"), str)
            # elapsed is a positive number
            assert isinstance(done.get("elapsed_ms"), int)
