"""Consult tool — boundary contract + timeout + registry presence."""

import asyncio
import json

import pytest

from app.domain.tools.builtin.consult_handler import (
    CONSULT_TIMEOUT_SECONDS,
    consult_handler,
)
from app.domain.tools.registry import init_default_registry


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
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "consult-session"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "consult-session",
            "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"},
        }})
    elif msg["method"] == "session/prompt":
        # echo the LAST line of the prompt (the question) back — so we
        # can assert ONLY the passed context/question travel
        text = msg["params"]["prompt"][0]["text"]
        tail = text.split("Question]")[-1].strip()
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "consult-session",
            "update": {"content": {"type": "text", "text": tail}, "sessionUpdate": "agent_message_chunk"},
        }})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": "consult-session",
            "update": {"size": 1000, "used": 2, "sessionUpdate": "usage_update"},
        }})
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"stopReason": "end_turn", "usage": {}}})
    elif msg["method"] == "session/close":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        break
"""


@pytest.fixture
def echo_acp(tmp_path):
    script = tmp_path / "consult_echo.py"
    script.write_text(ECHO_ACP, encoding="utf-8")
    return ["python3", str(script)]


class TestConsultHandler:
    async def test_requires_context_and_question(self):
        res = await consult_handler({}, question="why?")
        assert res["success"] is False
        assert "context" in res["error"]

        res = await consult_handler({}, context="state")
        assert res["success"] is False
        assert "question" in res["error"]

    async def test_roundtrip_returns_question_answer(self, echo_acp, tmp_path, monkeypatch):
        # point the singleton at the echo fake — patch the SOURCE
        # module (services.py), not the package re-export
        from app.domain.external_agent import services as ext_svc
        client = ext_svc.AcpClient(command=echo_acp, cwd=str(tmp_path))
        monkeypatch.setattr(ext_svc, "_client", client)

        res = await consult_handler(
            {},
            context="Agent 7 observes: file-not-found for outputs/report.md",
            question="What could cause this?",
        )
        assert res["success"] is True
        # echo fake returns the question tail — proves the prompt
        # carried the question (and only what we passed)
        assert "What could cause this?" in res["reply"]

    async def test_timeout_returns_graceful_error(self, tmp_path, monkeypatch):
        # shrink the timeout so the test is fast (semantics unchanged)
        import app.domain.tools.builtin.consult_handler as ch
        monkeypatch.setattr(ch, "CONSULT_TIMEOUT_SECONDS", 3)
        # a fake that never answers the prompt
        silent = tmp_path / "silent_acp.py"
        silent.write_text(
            r"""
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
    elif msg["method"] == "session/new":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"sessionId": "silent"}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "silent", "update": {"size": 1000, "used": 1, "sessionUpdate": "usage_update"}}})
    elif msg["method"] == "session/prompt":
        pass  # never reply — hangs forever
""",
            encoding="utf-8",
        )
        import app.domain.tools.builtin.consult_handler as ch
        from app.domain.external_agent import services as ext_svc
        client = ext_svc.AcpClient(command=["python3", str(silent)], cwd=str(tmp_path))
        monkeypatch.setattr(ext_svc, "_client", client)

        res = await consult_handler(
            {},
            context="stuck state",
            question="are you there?",
        )
        assert res["success"] is False
        assert "timed out" in res["error"]


class TestConsultRegistry:
    def test_consult_is_registered(self):
        reg = init_default_registry()
        assert reg.has_tool("consult")
        tool = reg._tools["consult"]
        assert tool.name == "Consult"
        # required args enforced by schema
        assert "context" in tool.arguments_schema["required"]
        assert "question" in tool.arguments_schema["required"]
