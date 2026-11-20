"""The install's acceptance check — one readiness sentence, from the one verdict.

`GET /api/v1/setup/readiness` measures the four facts that decide whether this installation can
answer a message at all: a provider with a key (or a local server), a chat model that resolves,
the shipped agents, and Exa's runtime (reported, never counted — Exa is a decision, not a
requirement). The Dashboard card and the Setup checklist both render that measurement; this
command prints it, so a person (or an agent) has ONE number to quote: `remaining`.

It is READ-ONLY. Nothing here starts a service, seeds an agent, probes a model or writes a file.

Usage:
    ./cogitate.sh verify                                  # this install's backend
    uv run python scripts/core/verify_readiness.py        # the default port
    uv run python scripts/core/verify_readiness.py --url http://localhost:8100
    uv run python scripts/core/verify_readiness.py --json # the raw payload

Exit codes:
    0  ready — nothing is left to do
    1  not ready — every item that is not `ok` is named, with its fix
    2  the backend did not answer (start it first: `./cogitate.sh start`)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_PORT = "8000"
TIMEOUT_SECONDS = 15

# How each state reads on one line. `optional` is not a failure and must not
# look like one — an unactivated Exa is a decision, not a missing step.
MARK = {"ok": "✓", "unmet": "✗", "blocked": "·", "optional": "·"}


def fetch(url: str) -> dict:
    """The readiness payload, or a SystemExit(2) that says what to do about it."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"The backend answered {exc.code} at {url} — the readiness read failed.")
        raise SystemExit(2) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"The backend is not answering at {url} ({exc}).")
        print("Start it with ./cogitate.sh start, then run this again.")
        raise SystemExit(2) from exc


def render(payload: dict) -> list[str]:
    items = payload.get("items", [])
    counted = [i for i in items if i.get("counted", True)]
    passing = [i for i in counted if i.get("state") == "ok"]
    remaining = payload.get("remaining", 0)
    optional = [i for i in items if not i.get("counted", True)]

    if payload.get("ready"):
        tail = (
            f" {optional[0]['label']} not counted."
            if optional
            else ""
        )
        return [f"READY — {len(passing)} of {len(counted)} checks pass, 0 remaining.{tail}"]

    lines = [f"NOT READY — {remaining} of {len(counted)} checks still need you:"]
    for item in items:
        mark = MARK.get(item.get("state", ""), "?")
        lines.append(f"  {mark} {item.get('label', '?'):<22} {item.get('detail', '')}")
        door = item.get("href")
        if mark == "✗" and door:
            lines.append(f"    {'':22} → {door}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print this installation's readiness verdict (read-only)."
    )
    parser.add_argument(
        "--url",
        default=f"http://localhost:{os.environ.get('COGITATE_BACKEND_PORT', DEFAULT_PORT)}",
        help="the backend's root URL (default: http://localhost:$COGITATE_BACKEND_PORT or 8000)",
    )
    parser.add_argument("--json", action="store_true", help="print the raw readiness payload")
    args = parser.parse_args(argv)

    url = args.url.rstrip("/") + "/api/v1/setup/readiness"
    payload = fetch(url)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("\n".join(render(payload)))

    return 0 if payload.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
