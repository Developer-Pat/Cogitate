"""The acceptance check — one verdict, one number, honest exit codes.

`./cogitate.sh verify` is what the install page and the agent skill quote, so what it PRINTS
and what it EXITS must both be defensible: a stranger is told `remaining`, and a script that
calls it must not read a broken install as a working one.
"""

import socket
import sys
from pathlib import Path

import pytest

# scripts/ is at the project root; the sweep runs pytest from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root

from scripts.core import verify_readiness


def _payload(items: list[dict]) -> dict:
    remaining = sum(1 for i in items if i.get("counted", True) and i["state"] != "ok")
    return {"ready": remaining == 0, "remaining": remaining, "items": items}


OK_PROVIDER = {
    "key": "provider",
    "label": "Provider + key",
    "state": "ok",
    "detail": "1 of 1 provider(s) can be dialled.",
    "href": "/provider-dashboard",
    "counted": True,
}
UNMET_MODEL = {
    "key": "chat",
    "label": "Chat model",
    "state": "unmet",
    "detail": "Nothing answers chat yet.",
    "href": "/provider-dashboard",
    "counted": True,
}
BLOCKED_AGENTS = {
    "key": "agents",
    "label": "Agents",
    "state": "blocked",
    "detail": "Bob and Lois arrive once a chat model resolves.",
    "href": "/agent-profiles",
    "counted": True,
}
OPTIONAL_RUNTIME = {
    "key": "runtime",
    "label": "Exa runtime (optional)",
    "state": "optional",
    "detail": "Exa needs an external runtime.",
    "href": "/exa",
    "counted": False,
}


def test_a_ready_install_is_one_sentence_with_zero_remaining():
    lines = verify_readiness.render(_payload([OK_PROVIDER, OPTIONAL_RUNTIME]))

    assert len(lines) == 1, "a ready install is one line, not a report"
    assert "READY" in lines[0]
    assert "0 remaining" in lines[0]
    # the optional item is NOT counted, and the sentence says so
    assert "not counted" in lines[0]


def test_a_broken_install_is_named_item_by_item_with_its_door():
    lines = verify_readiness.render(_payload([OK_PROVIDER, UNMET_MODEL, BLOCKED_AGENTS]))
    text = "\n".join(lines)

    assert lines[0].startswith("NOT READY — 2 of 3")
    assert "Chat model" in text and "Nothing answers chat yet." in text
    # a blocked item is not the user's to fix yet — it must not be marked unmet
    assert "✗ Agents" not in text
    assert "· Agents" in text
    # every unmet item names the page that fixes it
    assert "→ /provider-dashboard" in text


def test_a_backend_that_is_not_answering_exits_2_with_the_fix(monkeypatch, capsys):
    # a port nothing listens on: bound, then closed, so the connect is refused
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    with pytest.raises(SystemExit) as exc:
        verify_readiness.main(["--url", f"http://127.0.0.1:{port}"])
    assert exc.value.code == 2
    printed = capsys.readouterr().out
    assert "not answering" in printed
    assert "./cogitate.sh start" in printed, "the refusal names the fix"


def test_main_exits_0_when_ready_and_1_when_not(monkeypatch, capsys):
    monkeypatch.setattr(
        verify_readiness, "fetch", lambda url: _payload([OK_PROVIDER, OPTIONAL_RUNTIME])
    )
    assert verify_readiness.main([]) == 0
    assert "READY" in capsys.readouterr().out

    monkeypatch.setattr(
        verify_readiness, "fetch", lambda url: _payload([UNMET_MODEL, BLOCKED_AGENTS])
    )
    assert verify_readiness.main([]) == 1
    assert "NOT READY" in capsys.readouterr().out


def test_json_mode_prints_the_payload_unchanged(monkeypatch, capsys):
    import json

    payload = _payload([OK_PROVIDER, OPTIONAL_RUNTIME])
    monkeypatch.setattr(verify_readiness, "fetch", lambda url: payload)

    assert verify_readiness.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out) == payload


def test_a_fix_it_link_names_the_TAB_that_fixes_it():
    """A page-level link is one tab away from its fix — measured on a from-zero install.

    The Provider Dashboard opens on CURATED (recommendations), so a chat item that linked to
    `/provider-dashboard` landed a stranger on a page about curated models, with the default-model
    picker one tab away. Each href must name the tab, not the page.
    """
    from app.domain.providers import readiness

    # The acts live on the SETUP page (ruled 2026-11-22, option 2): the cloud-providers page keeps
    # the tiles and the curated layer, and no longer hosts a second Keys or Default-model tab.
    assert readiness.HREF_PROVIDER == "/setup?tab=keys"
    assert readiness.HREF_MODEL == "/setup?tab=model"
    # the bare page is never the answer: its landing tab is Curated
    assert "/provider-dashboard" not in (readiness.HREF_PROVIDER, readiness.HREF_MODEL)
