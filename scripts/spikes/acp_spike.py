"""
ACP spike — prove the full handshake works from a subprocess.

Protocol (JSON-RPC 2.0 over stdio):
  1. initialize            -> capabilities
  2. session/new           -> session_id
  3. session/prompt        -> stream of events (text, etc.)
  4. session/close         -> end

This is the exact plumbing the agent side panel will use. Run:
    python3 scripts/spikes/acp_spike.py "hello from cogitate"
"""
import json
import subprocess
import sys
import threading
import time


def main(prompt: str = "Say hello in one short sentence.") -> None:
    proc = subprocess.Popen(
        ["hermes", "acp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    messages: list[dict] = []

    def reader() -> None:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages.append(msg)

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    # 1. initialize
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": 1,
        "clientCapabilities": {"streaming": True},
        "clientInfo": {"name": "cogitate-spike", "version": "0.1.0"},
    }})
    time.sleep(2)

    # 2. session/new — Hermes REQUIRES cwd (working dir) AND
    # mcpServers as a LIST (dict -> "Input should be a valid
    # list"; missing -> "Field required"). Both pydantic-gated.
    import os as _os
    send({"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {
        "cwd": _os.getcwd(),
        "mcpServers": [],
    }})
    # runtime init can take several seconds (model lists, tools)
    for _ in range(15):
        time.sleep(1)
        if any(m.get("id") == 2 for m in messages):
            break

    session_id = None
    for m in messages:
        if m.get("id") == 2 and isinstance(m.get("result"), dict):
            session_id = m["result"].get("sessionId")
    print(f"session_id: {session_id}")
    if not session_id:
        print("SPIKE FAILED: no session_id (check params + stderr)")
        proc.terminate()
        sys.exit(1)

    # 3. session/prompt — Hermes' ACP adapter takes CONTENT BLOCKS
    # directly in the prompt list. Wrapping in {"role","content"}
    # is REJECTED by pydantic (missing "TextContentBlock.text").
    # This is the key protocol quirk discovered by the spike.
    send({"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {
        "sessionId": session_id,
        "prompt": [{"type": "text", "text": prompt}],
    }})
    # streamed turn: poll until the id:3 RESULT arrives (Hermes
    # signals completion via the session/prompt response with
    # stopReason, NOT a status=completed session/update event)
    for _ in range(90):
        time.sleep(1)
        if any(m.get("id") == 3 and "result" in m for m in messages):
            break

    # 4. session/close
    if session_id:
        send({"jsonrpc": "2.0", "id": 4, "method": "session/close", "params": {"sessionId": session_id}})
        time.sleep(1)

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    # Report what we got — events are session/update with
    # update.sessionUpdate = agent_message_chunk (the reply) or
    # agent_thought_chunk (thinking); the turn ends with a
    # session/prompt result {stopReason: end_turn}.
    reply_parts = []
    thought_parts = []
    for m in messages:
        if m.get("method") != "session/update":
            continue
        up = m.get("params", {}).get("update", {})
        if up.get("sessionUpdate") == "agent_message_chunk":
            content = up.get("content", {})
            if isinstance(content, dict) and content.get("text"):
                reply_parts.append(content["text"])
        elif up.get("sessionUpdate") == "agent_thought_chunk":
            content = up.get("content", {})
            if isinstance(content, dict) and content.get("text"):
                thought_parts.append(content["text"])
    stop = next((m.get("result", {}).get("stopReason") for m in messages if m.get("id") == 3), None)
    print(f"messages received: {len(messages)}")
    print(f"stopReason: {stop}")
    print(f"thought: {''.join(thought_parts)[:200]}")
    print(f"assistant reply: {''.join(reply_parts)[:300]}")
    print("SPIKE OK" if reply_parts else "SPIKE: no reply received")


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Say hello in one short sentence."
    main(prompt)
