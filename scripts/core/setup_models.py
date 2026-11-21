#!/usr/bin/env python3
"""The setup step — offer the VALUES a fresh install does not decide for you.

Structure ships with the install (capability rows, provider shells, tables).
A VALUE — which model answers here — is a recommendation you accept or skip,
and this is that conversation. The app never fills one in for you, and a
capability nothing can resolve is reported as a gap instead of guessed at.

Usage:
    uv run python scripts/core/setup_models.py              # ask about each offer
    uv run python scripts/core/setup_models.py --check      # report only, write nothing
    uv run python scripts/core/setup_models.py --accept-defaults   # take every offer (agent-driven)
    uv run python scripts/core/setup_models.py --scratch    # leave it bare, say what is off
    uv run python scripts/core/setup_models.py --json       # the report, machine-readable

Every offer carries the EVIDENCE that makes it apply here — a key in .env, or a
local server that answers and reports a model — and one line saying why. Nothing
is written without an explicit accept (`--accept-defaults` IS that accept, made
once for a scripted install).

Exit codes: 0 = every capability resolves (or nothing was offerable), 1 = gaps remain.
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


def _print_states(report) -> None:
    print("Capabilities (structure ships; values are offered):")
    for state in report.states:
        print(f"  {MARK[state.resolved]} {state.capability:<14} {state.detail}")
        if state.gap:
            print(f"                 → {state.gap}")
    print()


def _ask(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


async def _run(args) -> int:
    from app.infrastructure.database import get_db_session
    from app.domain.providers import express_setup, setup_offers

    # THE EXPRESS PICK (2026-11-21): one packaged model, adopted in one command. Handled before
    # the per-capability offers because it IS the short path an agent-driven install should take —
    # `--accept-defaults` stays for the older per-capability flow.
    if args.list_picks or args.pick:
        async for db in get_db_session():
            if args.list_picks:
                for pick in await express_setup.list_picks(db):
                    mark = MARK[pick["state"] == "ready"]
                    print(f"  {mark} [{pick['key']}] {pick['label']}  ({pick['tier']})")
                    print(f"      {pick['provider_name']}/{pick['model_id']} — {pick['detail']}")
                return 0
            try:
                log = await express_setup.apply_pick(db, args.pick)
            except ValueError as exc:
                print(f"cannot apply {args.pick!r}: {exc}", file=sys.stderr)
                return 2
            print("Written:")
            for line in log:
                print(f"  · {line}")
            return 0
        print("could not open a database session", file=sys.stderr)
        return 2

    accepted: list[str] = []
    log: list[str] = []
    report = None

    async for db in get_db_session():
        report = await setup_offers.probe(db)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
            return 0 if not report.gaps else 1

        _print_states(report)
        offers = report.offers
        if not offers:
            print("No offer applies to this machine — nothing to ask about.")
        else:
            print("Offers that fit this machine:")
            for offer in offers:
                print(f"  [{offer.key}] {offer.capability} → {offer.provider}/{offer.model}")
                print(f"      {offer.reason}")
                if args.accept_defaults:
                    accepted.append(offer.key)
                    print("      accepted (--accept-defaults)")
                elif args.check or args.scratch:
                    print("      not taken" + (" (--check)" if args.check else " (--scratch)"))
                elif _ask("      apply it? [y/N] "):
                    accepted.append(offer.key)
            print()

        if accepted:
            report, log = await setup_offers.apply(db, accepted)
            print("Written:")
            for line in log:
                print(f"  · {line}")
            print()
            _print_states(report)
        break

    if report is None:
        print("could not open a database session", file=sys.stderr)
        return 2

    if report.gaps:
        print(f"GAPS: {len(report.gaps)} — " + ", ".join(g.capability for g in report.gaps))
        print("Set them on the Providers page when you want them; nothing here guesses.")
        return 1
    print("Every capability resolves.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Offer the model values a fresh install leaves unset (accept or skip each)."
    )
    p.add_argument("--check", action="store_true", help="report only — write nothing")
    p.add_argument(
        "--accept-defaults",
        action="store_true",
        help="take every applicable offer without asking (for an agent-driven install)",
    )
    p.add_argument(
        "--scratch",
        action="store_true",
        help="leave the install bare and report what is off",
    )
    p.add_argument("--json", action="store_true", help="machine-readable report")
    # The express door: one packaged model, one command.
    p.add_argument("--list-picks", action="store_true", help="list the packaged express picks")
    p.add_argument("--pick", metavar="KEY", help="adopt one packaged pick (provider + model + chains)")
    args = p.parse_args()
    if sum(bool(x) for x in (args.check, args.accept_defaults, args.scratch)) > 0 and (args.list_picks or args.pick):
        print("--list-picks/--pick do not combine with --check/--accept-defaults/--scratch.", file=sys.stderr)
        return 2
    if args.list_picks and args.pick:
        print("--list-picks reports; --pick writes. Choose one.", file=sys.stderr)
        return 2
    if sum(bool(x) for x in (args.check, args.accept_defaults, args.scratch)) > 1:
        print("--check, --accept-defaults and --scratch are alternatives.", file=sys.stderr)
        return 2
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
