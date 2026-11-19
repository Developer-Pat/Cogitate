#!/usr/bin/env python3
"""
Helper script to make a synchronous HTTP POST to an SSE chat stream.

This runs as a subprocess to completely avoid async event loop and database
contention issues when called from within the SSE handler (which runs
inside uvicorn's event loop). A separate process has its own memory space,
event loop, and database connections.

Usage:
    python delegate_sse_fetch.py <url> <json_body> <params>

Output:
    First line:  HTTP_STATUS:<status_code>
    Remaining:   Response body text
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    if len(sys.argv) < 4:
        print("Usage: delegate_sse_fetch.py <url> <json_body> <params_json>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    body = json.loads(sys.argv[2])
    params = json.loads(sys.argv[3])

    # Build full URL with query params
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.status
            body_text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status = e.code
        body_text = e.read().decode("utf-8")
    except Exception as e:
        # Write error as response so the handler can log it
        print("HTTP_STATUS:0")
        print(f"ERROR:{type(e).__name__}:{e}", file=sys.stderr)
        sys.exit(1)

    # Output: first line is status, rest is body
    print(f"HTTP_STATUS:{status}")
    sys.stdout.flush()
    # Write body without any extra newlines
    sys.stdout.write(body_text)


if __name__ == "__main__":
    main()
