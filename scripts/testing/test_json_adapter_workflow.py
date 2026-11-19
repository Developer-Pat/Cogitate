#!/usr/bin/env python3
"""
End-to-end test script for the JSON adapter (Agent Chat API) workflow.

Demonstrates the full lifecycle:
  1. Enable external access
  2. Create a session with cognitive config
  3. Send a message and inspect the response (trace, metrics, memory delta)
  4. Retrieve the persisted trace from the cognitive_traces table
  5. Delete the session
  6. Disable external access

Usage:
    uv run python scripts/testing/test_json_adapter_workflow.py

Prerequisites:
    - Backend server running at http://localhost:8000
    - At least one agent exists in the database (uses agent_id=1 by default,
      override with --agent-id)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional

import httpx

BASE_URL = "http://localhost:8000/api/v1/agent-chat"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Make an HTTP request and return the response."""
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", 60.0)
    resp = httpx.request(method, url, **kwargs)
    return resp


def _print_step(step: int, label: str) -> None:
    """Print a step header."""
    print(f"\n{'=' * 70}")
    print(f"  Step {step}: {label}")
    print(f"{'=' * 70}")


def _print_json(label: str, data: Any) -> None:
    """Pretty-print a JSON object with a label."""
    print(f"\n  {label}:")
    print(f"  {json.dumps(data, indent=2, default=str)}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step1_enable_external_access() -> bool:
    """Enable external access via PUT /status."""
    _print_step(1, "Enable External Access")

    resp = _req("PUT", "/status", json={"enabled": True})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["enabled"] is True, f"Expected enabled=true, got {data}"
    _print_json("External access enabled", data)
    return True


def step2_create_session(agent_id: int) -> int:
    """Create a new agent chat session with cognitive config."""
    _print_step(2, "Create Session")

    cognitive_config = {
        "context_builder": "augmented",
        "executor": "default",
        "memory_manager": "default",
        "response_formatter": "default",
    }

    resp = _req(
        "POST",
        "/session",
        json={
            "agent_id": agent_id,
            "title": "JSON Adapter E2E Test",
            "cognitive_config": cognitive_config,
        },
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    session_id = data["id"]
    _print_json("Session created", data)
    print(f"\n  → Session ID: {session_id}")
    return session_id


def step3_send_message(session_id: int) -> Dict[str, Any]:
    """Send a message and inspect the full response."""
    _print_step(3, "Send Message")

    resp = _req(
        "POST",
        "/message",
        json={
            "session_id": session_id,
            "message": "Hello! Please respond with a brief greeting.",
        },
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    _print_json("Message response", data)

    # Validate response structure
    assert "session_id" in data, "Missing session_id"
    assert "message_id" in data, "Missing message_id"
    assert "response" in data, "Missing response"
    assert "trace" in data, "Missing trace"
    assert "metrics" in data, "Missing metrics"

    # Validate trace structure
    trace = data["trace"]
    assert "context_builder" in trace, "Missing context_builder in trace"
    assert "executor" in trace, "Missing executor in trace"
    assert "memory_manager" in trace, "Missing memory_manager in trace"
    assert "response_formatter" in trace, "Missing response_formatter in trace"
    assert "total_duration_ms" in trace, "Missing total_duration_ms in trace"
    assert "total_tokens" in trace, "Missing total_tokens in trace"

    # Validate metrics structure
    metrics = data["metrics"]
    assert "total_duration_ms" in metrics, "Missing total_duration_ms in metrics"
    assert "total_tokens" in metrics, "Missing total_tokens in metrics"
    assert "llm_calls" in metrics, "Missing llm_calls in metrics"

    print(f"\n  ✅ Response: {data['response'][:80]}...")
    print(f"  ✅ Trace total_duration_ms: {trace['total_duration_ms']}")
    print(f"  ✅ Metrics llm_calls: {metrics['llm_calls']}")

    return data


def step4_get_trace(session_id: int) -> Dict[str, Any]:
    """Retrieve the persisted cognitive trace."""
    _print_step(4, "Get Persisted Trace")

    resp = _req("GET", f"/session/{session_id}/trace")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    _print_json("Persisted trace", data)

    # Validate that the trace has real data (not empty defaults)
    trace = data["trace"]
    assert trace["total_duration_ms"] > 0 or trace["total_tokens"] > 0, (
        f"Expected non-empty trace, got total_duration_ms={trace['total_duration_ms']}"
    )

    print(f"  ✅ Trace persisted and retrieved successfully")
    return data


def step5_delete_session(session_id: int) -> None:
    """Delete the session."""
    _print_step(5, "Delete Session")

    resp = _req("DELETE", f"/session/{session_id}")
    assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
    print("  ✅ Session deleted successfully (204 No Content)")


def step6_disable_external_access() -> bool:
    """Disable external access via PUT /status."""
    _print_step(6, "Disable External Access")

    resp = _req("PUT", "/status", json={"enabled": False})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["enabled"] is False, f"Expected enabled=false, got {data}"
    _print_json("External access disabled", data)
    return True


def step7_verify_access_blocked() -> None:
    """Verify that requests are blocked when external access is disabled."""
    _print_step(7, "Verify Access Blocked (403)")

    resp = _req("POST", "/session", json={"agent_id": 1, "title": "Should Fail"})
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    data = resp.json()
    _print_json("Blocked response", data)
    print("  ✅ External access correctly blocked (403 Forbidden)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test the JSON adapter (Agent Chat API) end-to-end workflow."
    )
    parser.add_argument(
        "--agent-id",
        type=int,
        default=1,
        help="Agent ID to use (default: 1)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000/api/v1/agent-chat",
        help="Base URL for the agent-chat API (default: http://localhost:8000/api/v1/agent-chat)",
    )
    args = parser.parse_args()

    # pylint: disable=global-statement
    global BASE_URL  # noqa: PLW0603
    BASE_URL = args.base_url

    print(f"\n  🧪 JSON Adapter E2E Test")
    print(f"  Agent ID: {args.agent_id}")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Started:  {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    try:
        # Step 1: Enable external access
        step1_enable_external_access()

        # Step 2: Create session
        session_id = step2_create_session(args.agent_id)

        # Step 3: Send message
        step3_send_message(session_id)

        # Step 4: Get persisted trace
        step4_get_trace(session_id)

        # Step 5: Delete session
        step5_delete_session(session_id)

        # Step 6: Disable external access
        step6_disable_external_access()

        # Step 7: Verify access is blocked
        step7_verify_access_blocked()

        print(f"\n{'=' * 70}")
        print(f"  ✅ ALL TESTS PASSED")
        print(f"  Finished: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        print(f"{'=' * 70}\n")
        return 0

    except AssertionError as e:
        print(f"\n  ❌ TEST FAILED: {e}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as e:
        print(f"\n  ❌ HTTP ERROR: {e}", file=sys.stderr)
        if e.response.text:
            print(f"     Response: {e.response.text}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n  ❌ UNEXPECTED ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
