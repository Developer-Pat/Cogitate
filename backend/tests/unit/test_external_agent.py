"""The external-agent ACP client — the protocol round-trip and the policy gates.

The round-trip runs against a FAKE subprocess speaking JSON-RPC 2.0 over stdio —
no real hermes needed, so it is deterministic and fast.
"""

import asyncio
import json
import sys

import pytest

mark = pytest.mark

from app.domain.external_agent import AcpClient

FAKE_ACP = r"""
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"agentInfo": {"name": "fake", "version": "0.0.1"}}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "fake-session-1"}})
        # mirror hermes: startup usage_update = session-ready signal
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "fake-session-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        # stream a reply, chunk by chunk
        for chunk in ["Hel", "lo ", "world!"]:
            send({"jsonrpc": "2.0", "method": "session/update", "params": {
                "sessionId": "fake-session-1",
                "update": {"content": {"type": "text", "text": chunk}, "sessionUpdate": "agent_message_chunk"},
            }})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "fake-session-1",
            "update": {"size": 1000, "used": 5, "sessionUpdate": "usage_update"},
        }})
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn", "usage": {}}})
    elif msg["method"] == "session/close":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


RECORDER_ACP = r"""
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"agentInfo": {"name": "fake", "version": "0.0.1"}}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "fake-session-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "fake-session-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        with open(sys.argv[1], "a") as f:
            f.write(str(msg["params"].get("value", "")) + "\n")
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn", "usage": {}}})
    elif msg["method"] == "session/close":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


@pytest.mark.asyncio
async def test_edit_approval_policy_set_on_start(tmp_path):
    """start() requests the edit-approval policy: workspace_session
    when fix granted, ask (deny) when read-only. The fake records the
    values so we can assert them."""
    from app.domain.external_agent.services import AcpClient

    script = tmp_path / "recorder_acp.py"
    script.write_text(RECORDER_ACP, encoding="utf-8")
    side = tmp_path / "policies.txt"

    # read-only (default) → ask
    ro = AcpClient(command=["python3", str(script), str(side)], cwd=str(tmp_path))
    await ro.start()
    await ro.close()

    # fix granted → workspace_session
    fx = AcpClient(command=["python3", str(script), str(side)], cwd=str(tmp_path), fix_mode=True)
    await fx.start()
    await fx.close()

    policies = side.read_text().splitlines() if side.exists() else []
    assert policies == ["ask", "workspace_session"]


def test_strict_tools_gate_on_fix_mode():
    """The THREE-tier spawn gate (2026-08-21): fix-granted sessions
    omit strictTools (write tools allowed). The DEFAULT state (chat
    authorization) ALSO omits strictTools — the write tools must be
    AVAILABLE so an edit proposal can reach the permission requester
    (the per-edit Approve/Deny card is the gate, not a tool-layer
    block). Read-only-ness for the consult surface comes from the
    directive + the 60s-denial of an unapproved edit."""
    from app.domain.external_agent.services import AcpClient
    # default (chat authorization) → no strictTools (the card gates)
    ro = AcpClient(cwd="/tmp")
    params = ro._session_new_params()
    assert "capabilities" not in params, (
        "the default tier omits strictTools so edit proposals can "
        "reach the permission requester (chat authorization)"
    )
    # fix granted → no strictTools (write tools allowed, broad grant)
    fx = AcpClient(cwd="/tmp", fix_mode=True)
    assert "capabilities" not in fx._session_new_params()
    # yolo → no strictTools either (the everything-tier)
    y = AcpClient(cwd="/tmp", permission_tier="yolo")
    assert "capabilities" not in y._session_new_params()
    # default is the chat tier, not the broad grant
    assert AcpClient().permission_tier == "chat"


@pytest.fixture
def fake_acp(tmp_path):
    script = tmp_path / "fake_acp.py"
    script.write_text(FAKE_ACP, encoding="utf-8")
    return ["python3", str(script)]


class TestAcpClient:
    async def test_full_roundtrip(self, fake_acp, tmp_path):
        client = AcpClient(command=fake_acp, cwd=str(tmp_path))
        await client.start()
        assert client.session_id == "fake-session-1"
        reply = await client.prompt("hello")
        assert reply == "Hello world!"
        await client.close()

    async def test_stream_prompt_events(self, fake_acp, tmp_path):
        client = AcpClient(command=fake_acp, cwd=str(tmp_path))
        await client.start()
        events = []
        async for ev in client.stream_prompt("hi"):
            events.append(ev)
            if ev.kind == "usage":
                break
        kinds = [e.kind for e in events]
        assert "message" in kinds
        text = "".join(e.text for e in events if e.kind == "message")
        assert text == "Hello world!"
        await client.close()

    async def test_session_new_requires_cwd(self, fake_acp, tmp_path):
        # a fake that REJECTS session/new without cwd (mirrors hermes)
        script = tmp_path / "reject_no_cwd.py"
        script.write_text(
            r"""
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {}}) + "\n"); sys.stdout.flush()
    elif msg["method"] == "session/new":
        if "cwd" not in msg.get("params", {}):
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": "Invalid params"}}) + "\n"); sys.stdout.flush()
            break
        else:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "ok"}}) + "\n"); sys.stdout.flush()
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "ok", "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"}}}) + "\n"); sys.stdout.flush()
""",
            encoding="utf-8",
        )
        # our client always sends cwd — so it should succeed
        client = AcpClient(command=["python3", str(script)], cwd=str(tmp_path))
        await client.start()
        assert client.session_id == "ok"
        await client.close()


class TestNoInterleave:
    """Phase-1 queue rework: concurrent prompts serialize on the
    lock and each consumer receives ONLY its own events."""

    ECHO_ACP = r"""
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "echo-session"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "echo-session",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        text = msg["params"]["prompt"][0]["text"]
        # echo the prompt text back, chunk by chunk — each prompt's
        # reply is DISTINCT, so cross-talk would be caught
        for i in range(0, len(text), 3):
            chunk = text[i:i+3]
            send({"jsonrpc": "2.0", "method": "session/update", "params": {
                "sessionId": "echo-session",
                "update": {"content": {"type": "text", "text": chunk}, "sessionUpdate": "agent_message_chunk"},
            }})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "echo-session",
            "update": {"size": 1000, "used": 2, "sessionUpdate": "usage_update"},
        }})
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn", "usage": {}}})
    elif msg["method"] == "session/close":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""

    @pytest.fixture
    def echo_acp(self, tmp_path):
        script = tmp_path / "echo_acp.py"
        script.write_text(self.ECHO_ACP, encoding="utf-8")
        return ["python3", str(script)]

    async def test_concurrent_prompts_no_interleave(self, echo_acp, tmp_path):
        client = AcpClient(command=echo_acp, cwd=str(tmp_path))
        await client.start()
        assert client.session_id == "echo-session"

        async def run(prompt_text: str) -> str:
            parts = []
            async for ev in client.stream_prompt(prompt_text):
                if ev.kind == "message":
                    parts.append(ev.text)
                if ev.kind == "usage":
                    break
            return "".join(parts)

        # launch both concurrently — the lock serializes them; each
        # must receive ONLY its own echo
        a, b = await asyncio.gather(run("alpha-request"), run("beta-request"))
        assert a == "alpha-request"
        assert b == "beta-request"
        await client.close()

    async def test_prompt_after_stream_waits_for_lock(self, echo_acp, tmp_path):
        """A prompt() call issued while stream_prompt is mid-turn waits
        for the lock and still gets its own reply."""
        client = AcpClient(command=echo_acp, cwd=str(tmp_path))
        await client.start()

        async def streamer() -> str:
            parts = []
            async for ev in client.stream_prompt("stream-me"):
                if ev.kind == "message":
                    parts.append(ev.text)
                if ev.kind == "usage":
                    break
            return "".join(parts)

        s, p = await asyncio.gather(streamer(), client.prompt("prompt-me"))
        assert s == "stream-me"
        assert p == "prompt-me"
        await client.close()


STDERR_ACP = r"""
import json, sys
def _send(obj):
    sys.stdout.write(json.dumps(obj) + chr(10))
    sys.stdout.flush()
# announce on stderr at startup, then idle (responds to session/close)
sys.stderr.write("agent-stderr-line: starting up" + chr(10))
sys.stderr.flush()
for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "stderr-1"}})
        _send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "stderr-1", "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/close":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


DIER_ACP = r"""
import json, sys, time

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "dier-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "dier-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        # DIES MID-PROMPT (the 2026-09-08 hang class): one chunk, then
        # an unannounced exit — no session/close, no error frame. The
        # pipes EOF and the client must notice + alarm.
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "dier-1",
            "update": {"content": {"type": "text", "text": "hi"}, "sessionUpdate": "agent_message_chunk"},
        }})
        sys.stdout.flush()
        time.sleep(0.1)
        sys.exit(3)
"""


RUNAWAY_ACP = r"""
import json, sys, time

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "runaway-1"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "runaway-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/prompt":
        # runaway: stream chunks forever until the pipe dies — mimics an
        # agent stuck in a tool loop (never reads stdin again)
        while True:
            send({"jsonrpc": "2.0", "method": "session/update", "params": {
                "sessionId": "runaway-1",
                "update": {"content": {"type": "text", "text": "x"}, "sessionUpdate": "agent_message_chunk"},
            }})
            time.sleep(0.05)
    elif msg["method"] == "session/close":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


class TestStderrEvidence:
    """INCIDENT 2026-08-13: the agent's stderr was DEVNULL, so deaths
    left no trail. It must now be piped and drained into the log (and
    the pipe drained so the subprocess never blocks on a full buffer)."""

    @pytest.fixture
    def stderr_acp(self, tmp_path):
        script = tmp_path / "stderr_acp.py"
        script.write_text(STDERR_ACP, encoding="utf-8")
        return ["python3", str(script)]

    async def test_stderr_is_drained_and_logged(self, stderr_acp, tmp_path, caplog):
        import logging
        client = AcpClient(command=stderr_acp, cwd=str(tmp_path))
        with caplog.at_level(logging.INFO, logger="app.domain.external_agent.services"):
            await client.start()
            # give the drain task a beat to read the stderr line
            for _ in range(50):
                if any("agent-stderr-line" in r.message for r in caplog.records):
                    break
                await asyncio.sleep(0.02)
            await client.close()
        assert any(
            "agent-stderr-line: starting up" in r.message for r in caplog.records
        ), "stderr line must be captured in the backend log"

    async def test_close_kills_subprocess(self, stderr_acp, tmp_path):
        client = AcpClient(command=stderr_acp, cwd=str(tmp_path))
        await client.start()
        assert client.connected
        assert client._proc is not None
        proc = client._proc
        await client.close()
        # terminate (grace 3s) then kill — the process must be gone.
        # close() nulls self._proc immediately (the respawn race fix),
        # so assert via the captured proc + the connected flag.
        assert proc.returncode is not None
        assert client._proc is None
        assert client.connected is False

    async def test_close_bounded_when_agent_busy(self, tmp_path):
        """close() must NOT hang on an agent that never answers
        session/close (mid-prompt runaway) — the graceful attempt is
        capped at 2s, then terminate/kill takes over."""
        script = tmp_path / "busy_acp.py"
        script.write_text(RUNAWAY_ACP, encoding="utf-8")
        client = AcpClient(command=["python3", str(script)], cwd=str(tmp_path))
        await client.start()
        # put the agent into the runaway prompt branch (never reads stdin)
        task = asyncio.create_task(client.prompt("go"))
        await asyncio.sleep(0.3)
        assert not task.done()
        start = asyncio.get_running_loop().time()
        await client.close()
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed < 10, f"close() hung {elapsed:.1f}s on a busy agent"
        assert client.connected is False
        task.cancel()


class TestProcessExitAlarm:
    """INCIDENT 2026-09-08 (the process-exit alarm): the drain loops broke
    silently on EOF — when Exa died, the backend didn't know until the
    next prompt and the in-flight stream hung on the dead process. The
    EOF must alarm: log the exit + end the stream + fail the pending
    futures."""

    @pytest.fixture
    def dier_acp(self, tmp_path):
        script = tmp_path / "dier_acp.py"
        script.write_text(DIER_ACP, encoding="utf-8")
        return ["python3", str(script)]

    async def test_unexpected_exit_alarms_and_ends_the_stream(self, dier_acp, tmp_path, caplog):
        import logging
        client = AcpClient(command=dier_acp, cwd=str(tmp_path))
        await client.start()
        # the prompt hits the dying branch — the stream must END (the
        # closed sentinel), not hang
        events = []
        with caplog.at_level(logging.WARNING, logger="app.domain.external_agent.services"):
            async for ev in client.stream_prompt("go"):
                events.append(ev.kind)
        # the alarm logged
        assert any(
            "EXITED unexpectedly" in r.message and "returncode=3" in r.message
            for r in caplog.records
        ), "the process exit must be logged with the returncode"
        # the stream ended (usage or closed) instead of hanging
        assert events, "the stream must yield its events"
        assert client.connected is False, "the client must know the process is gone"
        assert client._proc is None, "the once-guard must null the proc"

    @pytest.fixture
    def quiet_acp(self, tmp_path):
        # the same idle-agent script the stderr tests use (class-scoped
        # there — this class needs its own)
        script = tmp_path / "quiet_acp.py"
        script.write_text(STDERR_ACP, encoding="utf-8")
        return ["python3", str(script)]

    async def test_intentional_close_stays_quiet(self, quiet_acp, tmp_path, caplog):
        import logging
        client = AcpClient(command=quiet_acp, cwd=str(tmp_path))
        await client.start()
        with caplog.at_level(logging.WARNING, logger="app.domain.external_agent.services"):
            await client.close()
        assert not any(
            "EXITED unexpectedly" in r.message for r in caplog.records
        ), "an intentional close must NOT alarm"


# THE 3-WAY PERMISSION TIER (2026-08-21): chat / fix / yolo maps to
# the ACP edit_approval_policy — ask (per-edit cards) / workspace_
# session (cwd auto-approve) / session (everything auto-approve).
# The tier is the field of truth; the old fix_mode bool is the
# DEPRECATED compat view (True == the fix tier).


def test_permission_tier_policy_mapping():
    from app.domain.external_agent.services import AcpClient

    assert AcpClient.PERMISSION_TIERS == ("chat", "fix", "yolo")
    assert AcpClient.POLICY_BY_TIER == {
        "chat": "ask",
        "fix": "workspace_session",
        "yolo": "session",
    }


def test_permission_tier_defaults_to_chat():
    from app.domain.external_agent.services import AcpClient

    client = AcpClient(cwd="/tmp")
    assert client.permission_tier == "chat"
    assert client.POLICY_BY_TIER[client.permission_tier] == "ask"


def test_fix_mode_bool_is_the_compat_view():
    from app.domain.external_agent.services import AcpClient

    # the OLD callers pass fix_mode=True -> the fix tier
    fx = AcpClient(cwd="/tmp", fix_mode=True)
    assert fx.permission_tier == "fix"
    assert fx.POLICY_BY_TIER[fx.permission_tier] == "workspace_session"
    # the NEW callers pass the tier directly
    y = AcpClient(cwd="/tmp", permission_tier="yolo")
    assert y.permission_tier == "yolo"
    assert y.POLICY_BY_TIER[y.permission_tier] == "session"
    # the tier WINS over the compat bool
    both = AcpClient(cwd="/tmp", fix_mode=True, permission_tier="chat")
    assert both.permission_tier == "chat"


def test_unknown_permission_tier_rejected():
    from app.domain.external_agent.services import AcpClient

    import pytest as _pytest
    with _pytest.raises(AssertionError):
        AcpClient(cwd="/tmp", permission_tier="runaway")


def test_yolo_tier_reports_fix_granted():
    """The router's fix_granted (the directive + the badge) is True
    for BOTH fix and yolo — the write permission is granted either
    way; only the granularity differs."""
    assert {"fix", "yolo"} == {t for t in ("chat", "fix", "yolo") if t in ("fix", "yolo")}


ENV_ACP = r"""#!/usr/bin/env python3
import json, sys, os


def _send(obj):
    sys.stdout.write(json.dumps(obj) + chr(10))
    sys.stdout.flush()


# announce the effective HERMES_HOME on stderr at startup — the drain
# loop logs it, so the tests can assert the spawn env from the log
sys.stderr.write("agent-stderr-line: HERMES_HOME=" + str(os.environ.get("HERMES_HOME")) + chr(10))
sys.stderr.flush()

for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "env-1"}})
        _send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "env-1",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/set_config_option":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {"configOptions": []}})
    elif msg["method"] == "session/close":
        _send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


class TestStateIsolation:
    """THE STATE ISOLATION (Phase 1, hardened 2026-09-08): the spawn
    env must carry HERMES_HOME=exa_home for ANY hermes-shaped command
    (the basename guard — bare "hermes" OR an absolute path), and
    nothing for the fake ACP scripts (python3 keeps its env). A
    command-shape change must never fall through to the operator's
    home."""

    @pytest.fixture
    def env_acp_script(self, tmp_path):
        script = tmp_path / "env_acp.py"
        script.write_text(ENV_ACP, encoding="utf-8")
        return str(script)

    async def test_basename_hermes_command_gets_the_isolated_home(
        self, env_acp_script, tmp_path, caplog
    ):
        import logging
        from app.core.config import Paths
        # the script NAMED "hermes" (an absolute path — the shape the
        # old exact-match guard would have MISSED)
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text(ENV_ACP, encoding="utf-8")
        hermes_bin.chmod(0o755)
        client = AcpClient(command=[str(hermes_bin), "acp"], cwd=str(tmp_path))
        with caplog.at_level(logging.INFO, logger="app.domain.external_agent.services"):
            await client.start()
            for _ in range(50):
                if any("HERMES_HOME=" in r.message for r in caplog.records):
                    break
                await asyncio.sleep(0.02)
            await client.close()
        assert any(
            f"agent-stderr-line: HERMES_HOME={Paths.exa_home}" in r.message
            for r in caplog.records
        ), f"the basename-hermes command must run with HERMES_HOME={Paths.exa_home}"

    async def test_non_hermes_command_keeps_the_env_clean(
        self, env_acp_script, tmp_path, caplog
    ):
        import logging
        # the same script via python3 (the fake-ACP test shape) — the
        # guard must NOT fire: HERMES_HOME stays unset
        client = AcpClient(command=["python3", env_acp_script], cwd=str(tmp_path))
        with caplog.at_level(logging.INFO, logger="app.domain.external_agent.services"):
            await client.start()
            for _ in range(50):
                if any("HERMES_HOME=" in r.message for r in caplog.records):
                    break
                await asyncio.sleep(0.02)
            await client.close()
        assert any(
            "agent-stderr-line: HERMES_HOME=None" in r.message
            for r in caplog.records
        ), "a non-hermes command must keep its env (no HERMES_HOME)"



@mark.asyncio
async def test_big_pipe_line_skipped_no_false_alarm(caplog):
    """2026-09-08 (the LIVE false alarm): an oversized pipe line
    (over the asyncio StreamReader's 64KB limit) made the drainer's
    readline raise ValueError — the loop crashed and the finally
    raised the process-EXIT alarm while the process was ALIVE (the
    17:39 incident: the turn dropped mid-run, the user saw silence,
    pressed Stop, and the respawn lost the context). The guard
    skips the line, keeps draining, and alarms only at the REAL
    EOF."""
    from app.domain.external_agent import services as svc

    class FakeStream:
        def __init__(self):
            self._lines = [b"line one\n", "OVERSIZE", b"line three\n", b""]

        async def readline(self):
            nxt = self._lines.pop(0)
            if nxt == "OVERSIZE":
                raise ValueError("Separator is not found, and chunk exceed the limit")
            return nxt

    class FakeProc:
        returncode = -9
        stderr = FakeStream()

        async def wait(self):
            return -9

    client = svc.AcpClient(command=["python3", "-c", "pass"])
    client._proc = FakeProc()  # type: ignore[assignment]
    await client._stderr_loop()

    text = caplog.text
    assert "line one" in text and "line three" in text, "the lines around the oversize one must still drain"
    assert "exceeded the stream limit" in text, "the skip must be logged (visible, never silent)"
    assert "EXITED unexpectedly" in text, "the alarm fires at the REAL EOF (not at the big line)"
    assert client._proc is None, "the once-guard ran at the real EOF"
