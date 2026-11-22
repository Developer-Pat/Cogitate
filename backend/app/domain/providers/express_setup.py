"""Express setup — the packaged configurations, and the one press that adopts one.

**A pick names a MODEL.** A model strong enough to drive the box answers chat, titles, summaries,
workflows and memory alike; the five-capability split is legacy plumbing (the user's ruling,
2026-11-21), so a pick does not carry a capability list. What it carries instead is the honesty:
a `tier` (`strong` = what we would run the box on, `grab bag` = a local model we cannot vouch
for), one `needs` (`key` / `local` / `none`), and EVIDENCE (`verified_on` + `verified_how`) —
a null date is a pick nobody has driven end to end, and every surface must say so.

**The packaged file is the authority** (`express_setup.json`, in this directory). The
`setup_picks` table is its loaded copy: `load_packaged()` upserts it on every start, so a fresh
install has picks without anyone running a command, and the loader never deletes a row it does
not know (a user's own pick survives).

Why a FILE and not a Python dict (the thing it replaces, `setup_offers.MODEL_FOR`): the same
model was spelled three ways in this tree — `deepseek-v4-flash` in code, `~deepseek/
deepseek-v4-flash-latest` in one install's chain, `deepseek-flash` in the provider's own list.
A dict cannot carry which of those was true WHEN. A catalog entry carries its verification date.

Nothing here computes a verdict: the write goes through the general chain path (`replace_chain`)
and the default-provider service, exactly as `setup_offers.apply` does, so express setup holds no
state of its own.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Capability, Provider, SetupPick
from app.domain.providers.capabilities import CandidateSpec, replace_chain
from app.domain.providers.setup_offers import Offer, _provider_row

logger = logging.getLogger(__name__)

PACKAGED_PATH = Path(__file__).with_name("express_setup.json")

TIERS = ("strong", "grab bag")
NEEDS_KINDS = ("key", "local", "none")

# What a pick must carry for the loader to accept it. Kept as data so the pre-commit check and
# the loader can refuse the same row for the same reason.
REQUIRED = ("key", "label", "provider_name", "provider_type", "model_id", "tier", "needs_kind")


# ── The packaged file ───────────────────────────────────────────────────────


def packaged_picks() -> list[dict[str, Any]]:
    """The file's picks, validated. A malformed pack raises — it ships with us, so it is our bug."""
    raw = json.loads(PACKAGED_PATH.read_text())
    picks = raw.get("picks")
    if not isinstance(picks, list):
        raise ValueError(f"{PACKAGED_PATH.name}: 'picks' must be a list")
    seen: set[str] = set()
    for pick in picks:
        problems = validate_pick(pick)
        if problems:
            raise ValueError(f"{PACKAGED_PATH.name}: pick {pick.get('key')!r}: " + "; ".join(problems))
        if pick["key"] in seen:
            raise ValueError(f"{PACKAGED_PATH.name}: duplicate key {pick['key']!r}")
        seen.add(pick["key"])
    return picks


def validate_pick(pick: dict[str, Any]) -> list[str]:
    """Every way one packaged row can be wrong. Empty list = it may be loaded."""
    problems: list[str] = []
    for field in REQUIRED:
        if not pick.get(field):
            problems.append(f"missing {field}")
    if pick.get("tier") and pick["tier"] not in TIERS:
        problems.append(f"tier must be one of {TIERS}")
    kind = pick.get("needs_kind")
    if kind and kind not in NEEDS_KINDS:
        problems.append(f"needs_kind must be one of {NEEDS_KINDS}")
    if kind == "key" and not pick.get("needs_env"):
        problems.append("needs_kind 'key' requires needs_env")
    if kind != "key" and pick.get("needs_env"):
        problems.append("needs_env belongs only to needs_kind 'key'")
    # A cloud address is the registry's business, never the catalog's (one home per fact).
    if kind != "local" and any("://" in str(pick.get(f, "") or "") for f in ("model_id", "label")):
        problems.append("a cloud pick may not carry an address")
    return problems


async def load_packaged(db: AsyncSession) -> list[str]:
    """Upsert the packaged picks into `setup_picks`. Idempotent; never deletes.

    Runs at every start, so the table cannot drift from the file it came from. A packaged pick
    that disappears from the file is LEFT IN PLACE but deactivated, because a row a user is
    relying on should not vanish; a row this loader has never seen is never touched.
    """
    log: list[str] = []
    try:
        picks = packaged_picks()
    except Exception as exc:  # a bad pack must not stop the app from starting
        logger.warning("express setup: the packaged file did not validate — %s", exc)
        return [f"packaged file invalid: {exc}"]

    existing = {
        row.key: row
        for row in (await db.execute(select(SetupPick))).scalars().all()
    }
    packaged_keys = set()
    for pick in picks:
        packaged_keys.add(pick["key"])
        verified_on = pick.get("verified_on")
        fields = dict(
            label=pick["label"],
            provider_name=pick["provider_name"],
            provider_type=pick["provider_type"],
            model_id=pick["model_id"],
            tier=pick["tier"],
            needs_kind=pick["needs_kind"],
            needs_env=pick.get("needs_env"),
            needs_url=pick.get("needs_url"),
            why=pick.get("why"),
            verified_on=date.fromisoformat(verified_on) if verified_on else None,
            verified_how=pick.get("verified_how"),
            sort_order=int(pick.get("sort_order") or 0),
            is_active=True,
        )
        row = existing.get(pick["key"])
        if row is None:
            db.add(SetupPick(key=pick["key"], **fields))
            log.append(f"added {pick['key']}")
            continue
        changed = [name for name, value in fields.items() if getattr(row, name) != value]
        for name, value in fields.items():
            setattr(row, name, value)
        if changed:
            log.append(f"updated {pick['key']} ({', '.join(changed)})")

    # A packaged pick that LEFT the file: keep the row, stop offering it.
    for key, row in existing.items():
        if key not in packaged_keys and row.is_active:
            row.is_active = False
            log.append(f"retired {key} (no longer packaged)")

    await db.commit()
    return log


# ── Reading: what applies here ──────────────────────────────────────────────


def _env_snapshot() -> dict[str, bool]:
    """Which env names are SET. Read through the same parser the offer engine uses."""
    from app.domain.providers.setup_offers import _env_values

    return _env_values()


def describe_needs(pick: SetupPick) -> tuple[str, str]:
    """`(state, detail)` where state is `ready` | `needs-key` | `unavailable`.

    Applicability is COMPUTED, never assumed — the same discipline the readiness verdict follows.

    THE DETAIL IS END-USER COPY (2026-11-21, the user's read of the first draft: "looks more like
    developer stuff than end user material"). The env var name, the file it lands in and the
    install it was measured on are facts for the tooltip and the log, not sentences a stranger
    should have to read to install an app.
    """
    if pick.needs_kind == "none":
        return "ready", "Nothing needed."
    if pick.needs_kind == "key":
        env = _env_snapshot()
        name = pick.needs_env or ""
        if env.get(name):
            return "ready", "Its key is already set."
        where = f" — get one from {_pretty_url(pick.needs_url)}" if pick.needs_url else ""
        return "needs-key", f"Add your {pick.provider_name} key to use this model{where}."
    # `local` picks are not shipped yet: a local model is whatever the box happens to run, and it
    # is chosen on the Providers page (the user's call, 2026-11-21).
    return "unavailable", "Local models are chosen on the Providers page once the app is set up."


def _pretty_url(url: Optional[str]) -> str:
    """`https://platform.deepseek.com/api_keys` → `platform.deepseek.com` — a host a person reads."""
    if not url:
        return ""
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]


async def list_picks(db: AsyncSession) -> list[dict[str, Any]]:
    """Every active pick, in packaged order, with what it needs and whether that is satisfied."""
    rows = (
        (await db.execute(select(SetupPick).where(SetupPick.is_active.is_(True)))).scalars().all()
    )
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: (r.sort_order, r.key)):
        state, detail = describe_needs(row)
        out.append(
            {
                "key": row.key,
                "label": row.label,
                "provider_name": row.provider_name,
                "provider_type": row.provider_type,
                "model_id": row.model_id,
                "tier": row.tier,
                "why": row.why,
                "needs_kind": row.needs_kind,
                "needs_env": row.needs_env,
                "needs_url": row.needs_url,
                "state": state,
                "detail": detail,
                "verified_on": row.verified_on.isoformat() if row.verified_on else None,
                "verified_how": row.verified_how,
            }
        )
    return out


# ── The one press ───────────────────────────────────────────────────────────


async def active_pick_or_none(db: AsyncSession, key: str) -> Optional[SetupPick]:
    """The pick behind `key`, or None. Public so a router can answer 404 before writing anything."""
    row = (
        await db.execute(select(SetupPick).where(SetupPick.key == key))
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        return None
    return row


async def _active_pick(db: AsyncSession, key: str) -> SetupPick:
    row = await active_pick_or_none(db, key)
    if row is None:
        raise ValueError(f"no setup pick called {key!r} on this install")
    return row


async def apply_pick(db: AsyncSession, key: str) -> list[str]:
    """Adopt one pick: the provider row, every llm capability, the default, the agents.

    THE CHAINS ARE REWRITTEN, not left to inheritance (the user's ruling, fork 2a): an install
    that already has explicit `title`/`summary`/`workflow-llm`/`memory` chains would otherwise
    keep answering from its old model while chat moved — the exact defect this arc exists to
    avoid. One model, stated once per capability, is the end state.
    """
    pick = await _active_pick(db, key)
    state, detail = describe_needs(pick)
    if state != "ready":
        raise ValueError(detail)

    offer = Offer(
        key=pick.key,
        capability="chat",
        provider=pick.provider_name,
        provider_type=pick.provider_type,
        model=pick.model_id,
        reason=pick.why or "",
        needs=f"key:{pick.needs_env}" if pick.needs_env else "",
    )
    row = await _provider_row(db, offer)
    log = [f"provider: {row.name} (row #{row.id})"]

    # The model rides the row: the resolver's last rung reads `config.default_model`, and a row
    # without one resolves to a provider that cannot be dialled.
    config = dict(row.config) if isinstance(row.config, dict) else {}
    if config.get("default_model") != pick.model_id:
        config["default_model"] = pick.model_id
        row.config = config

    capabilities = (
        await db.execute(
            select(Capability).where(Capability.kind == "llm", Capability.enabled.is_(True))
        )
    ).scalars().all()
    for capability in sorted(capabilities, key=lambda c: c.key):
        await replace_chain(
            db,
            capability.key,
            [CandidateSpec(provider_id=row.id, model=pick.model_id)],
            label=f"express setup: {pick.label}",
        )
        log.append(f"{capability.key} -> {row.name}/{pick.model_id}")

    # THE DEFAULT, unconditionally: an express pick IS the user choosing, so unlike the offer
    # engine (which never reassigns a default somebody set) this one moves it.
    from app.domain.providers.config_service import DefaultProviderService

    await DefaultProviderService().set_default_provider(db, row.id)
    log.append(f"default provider -> {row.name}")

    await db.commit()

    # The value's consumer: a chat model is what the shipped agents waited for.
    try:
        from app.domain.agents.shipped import seed_shipped_agents

        for outcome in await seed_shipped_agents(db):
            log.append(f"news desk — {outcome.describe()}")
    except Exception as exc:  # a setup step must not fail on a seed
        log.append(f"news desk — not seeded: {exc}")

    return log
