#!/usr/bin/env python3
"""Activate Exa — the one command behind the install skill and the docs.

Exa ships INCLUDED and INACTIVE. Activating it is the user's decision, and the
sequence behind that decision is: the runtime on PATH, the isolated home
provisioned, a model set, provider keys present, and the persisted flag.

This CLI is a thin front door over `app.domain.external_agent.activation` —
the same code the HTTP probe uses — so the two can never disagree about what
"ready" means.

Usage:
    uv run python scripts/core/activate_exa.py                 # report only
    uv run python scripts/core/activate_exa.py --apply         # provision + activate
    uv run python scripts/core/activate_exa.py --apply \
        --model deepseek/deepseek-v4-flash --provider deepseek

    --json      machine-readable (for an agent driving the install)
    --home DIR  inspect a home other than <project>/.hermes (testing)

Exit codes: 0 = ready, 1 = not ready (the report says what is missing).

The report never prints a key — only the NAMES of the ones it found.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

MARK = {True: "✓", False: "✗"}


def _print_report(report, log: list[str]) -> None:
    if log:
        print("What this run did:")
        for line in log:
            print(f"  · {line}")
        print()
    print("The activation sequence:")
    for check in report.checks:
        print(f"  {MARK[check.ok]} {check.name:<9} {check.detail}")
        if not check.ok and check.fix:
            print(f"             → {check.fix}")
    print()
    print("READY — Exa can answer." if report.ready else "NOT READY — see the fixes above.")


async def _run(args) -> int:
    from app.infrastructure.database import get_db_session
    from app.domain.external_agent import activation

    home = Path(args.home).expanduser() if args.home else None
    log: list[str] = []
    report = None

    async for db in get_db_session():
        if args.apply:
            report, log = await activation.apply(
                db,
                home=home,
                model=args.model,
                provider=args.provider,
                base_url=args.base_url,
                reasoning_effort=args.reasoning,
            )
        else:
            report = await activation.probe(db, home=home)
        break

    if report is None:
        print("could not open a database session", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"ready": report.ready, "checks": report.to_dict()["checks"], "log": log}, indent=2))
    else:
        _print_report(report, log)
    return 0 if report.ready else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="Report (or perform) the sequence that takes Exa from included to answering."
    )
    p.add_argument("--apply", action="store_true", help="provision the home, set the model, activate")
    p.add_argument("--model", help="the model id to write into Exa's config (with --apply)")
    p.add_argument("--provider", help="the provider NAME for --model")
    p.add_argument("--base-url", dest="base_url", help="optional endpoint override for --model")
    p.add_argument(
        "--reasoning",
        choices=["none", "low", "medium", "high", "max"],
        help="optional reasoning effort for --model",
    )
    p.add_argument("--home", help="inspect/provision this home instead of <project>/.hermes")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

    if bool(args.model) != bool(args.provider):
        print("--model and --provider go together.", file=sys.stderr)
        return 2
    if (args.model or args.reasoning or args.base_url) and not args.apply:
        print("--model/--provider/--base-url/--reasoning need --apply.", file=sys.stderr)
        return 2

    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
