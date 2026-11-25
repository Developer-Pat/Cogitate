"""The external-agent tool-call budget tests.

The runaway-turn class: silent 50+-call turns crash and hang. The
router counts the tool calls per turn; at the check-in cadence it
sends a 'working' beacon; at the hard cap it halts via the same
two-stage path as Stop and reports 'tool_call_limit'.

Drives the real router with a fake ACP subprocess that emits a
TOOL STORM (tool_call events forever, never a usage event — the
rabbit-hole shape) + a config with tiny caps.
"""

import json
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.external_agent import AcpClient
from app.domain.external_agent.schemas import ExternalAgentConfig
from app.api.v1.external_agent_router import router as external_agent_router

from tests.unit.test_external_agent_ws_cancel import _wait_for

app = FastAPI()
app.include_router(external_agent_router)

TOOLSTORM_ACP = r"""
import json, sys, time

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "storm-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "storm-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        # THE TOOL STORM: tool_call events forever, never a usage
        # event — the rabbit-hole shape. The router's budget must
        # beacon (working) then halt (tool_call_limit).
        n = 0
        while True:
            n += 1
            send({"jsonrpc": "2.0", "method": "session/update", "params": {
                "sessionId": "storm-1",
                "update": {"content": {"type": "text", "text": f"tool-{n}"},
                           "sessionUpdate": "tool_call"},
            }})
            time.sleep(0.02)
"""


@pytest.fixture
def storm_script(tmp_path):
    script = tmp_path / "storm_acp.py"
    script.write_text(TOOLSTORM_ACP, encoding="utf-8")
    return ["python3", str(script)]


def _patch(monkeypatch, client: AcpClient, config: ExternalAgentConfig):
    """Point the handler at our fake client + the tiny-cap config."""
    monkeypatch.setattr(
        "app.api.v1.external_agent_router.get_acp_client",
        lambda *a, **k: client,
    )

    async def _fake_get_config(db):
        # the ACTIVE path: Exa ships inactive (2026-11-18)
        return config.model_copy(update={"enabled": True})

    monkeypatch.setattr("app.api.v1.external_agent_router.get_config", _fake_get_config)

    async def _fake_db():
        yield None

    monkeypatch.setattr("app.api.v1.external_agent_router._db", _fake_db)

    # THE MACHINE IS NOT THE SUBJECT (2026-11-25). The router asks
    # `pre_turn_refusal` whether a turn can be attempted, and that is a set of
    # LOCAL reads: is `hermes` on PATH, does the isolated home have a model, does
    # its provider have a key. All three are true on a developer's box and false
    # on every runner, which is why these two tests passed here and failed there
    # with "Exa cannot answer: 'hermes' is not on PATH". The fake client IS the
    # agent, so the refusal must not decide anything — the same machine-
    # dependency `test_exa_activation` was fixed for, in a different place.
    monkeypatch.setattr(
        "app.domain.external_agent.activation.pre_turn_refusal",
        lambda cfg, home=None: None,
    )


class Frames:
    """The socket read in a BACKGROUND THREAD, so silence fails by name.

    A SILENT SOCKET USED TO BLOCK FOREVER (2026-11-25). `ws.receive_json()`
    waits on Starlette's portal with no timeout, so on GitHub's runners — where
    this file's storm never reaches the socket — both tests here blocked until
    the CI job was cancelled at 30 minutes. That is how a red build sat
    unnamed for two days. Reading in a thread lets the test enforce a deadline
    and, when it fails, say WHAT IT SAW.
    """

    def __init__(self, ws) -> None:
        self._ws = ws
        self._frames: list[dict] = []
        self._error: Exception | None = None
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            while True:
                self._frames.append(self._ws.receive_json())
        except Exception as exc:  # the socket closed — the reader's job is over
            self._error = exc

    def all(self) -> list[dict]:
        return list(self._frames)

    def statuses(self) -> list[str]:
        return [f["status"] for f in self.all() if f.get("type") == "status"]

    def wait_for(self, predicate, timeout: float, what: str) -> dict:
        """The first frame matching `predicate`, or a message naming what was seen."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for frame in self.all():
                if predicate(frame):
                    return frame
            if self._error is not None:
                raise AssertionError(
                    f"{what}: the socket closed before it arrived ({self._error!r}); "
                    f"frames seen: {_compact(self.all())}"
                )
            time.sleep(0.02)
        raise AssertionError(
            f"{what}: nothing arrived within {timeout}s. The turn produced "
            f"{len(self.all())} frame(s): {_compact(self.all())}"
        )


def _compact(frames: list[dict], limit: int = 600) -> str:
    """The frames as one line — including each status's MESSAGE, which is where
    the app puts the reason ('status: error' alone says nothing)."""
    return json.dumps(frames[:6], default=str)[:limit]


def test_tool_storm_hits_the_cap_with_checkins(monkeypatch, storm_script, tmp_path):
    """The tool storm must trigger the 'working' beacons (the enforced
    check-in) and then the 'tool_call_limit' halt — never run silent."""
    client = AcpClient(command=storm_script, cwd=str(tmp_path))
    config = ExternalAgentConfig(
        max_tool_calls_per_turn=3,
        tool_call_checkin_every=2,
        max_turn_seconds=0,  # the time cap off — the tool cap must fire
    )
    _patch(monkeypatch, client, config)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            frames = Frames(ws)
            frames.wait_for(
                lambda f: f.get("type") == "status" and f.get("status") == "ready",
                10.0, "the ready handshake",
            )
            ws.send_json({"type": "prompt", "text": "go"})
            frames.wait_for(
                lambda f: f.get("type") == "status" and f.get("status") == "tool_call_limit",
                20.0, "the tool_call_limit halt",
            )
            statuses = frames.statuses()
            assert "working" in statuses, (
                f"the check-in beacons never fired — statuses: {statuses}"
            )
            # the halt escalates (the storm ignores session/cancel) —
            # wait INSIDE the WS context for the subprocess death
            assert _wait_for(lambda: client.connected is False, timeout=12.0)


def test_tool_cap_zero_is_unlimited(monkeypatch, storm_script, tmp_path):
    """max_tool_calls_per_turn=0 disables the cap — the storm runs
    until the test tears it down (no tool_call_limit status)."""
    client = AcpClient(command=storm_script, cwd=str(tmp_path))
    config = ExternalAgentConfig(
        max_tool_calls_per_turn=0,
        tool_call_checkin_every=0,
        max_turn_seconds=0,
    )
    _patch(monkeypatch, client, config)

    with TestClient(app) as tc:
        with tc.websocket_connect("/external-agent/ws") as ws:
            frames = Frames(ws)
            frames.wait_for(
                lambda f: f.get("type") == "status" and f.get("status") == "ready",
                10.0, "the ready handshake",
            )
            ws.send_json({"type": "prompt", "text": "go"})
            # the storm is flowing: tool-call frames must arrive
            frames.wait_for(lambda f: f.get("type") == "tool_call", 20.0, "a tool_call frame")
            # the turn is still alive — the budget never fired
            assert "tool_call_limit" not in frames.statuses(), (
                f"a cap of 0 must not halt anything — statuses: {frames.statuses()}"
            )
            ws.send_json({"type": "nuke"})
