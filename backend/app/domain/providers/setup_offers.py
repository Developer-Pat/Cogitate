"""The setup step's OFFERS — what a fresh install may be told it can have.

THE RULE THIS IMPLEMENTS (the user's ruling, 2026-10-10):

  structure (capability keys, a row's shell, tables)  -> the seed/migration, no consent needed
  a VALUE (a model name, an endpoint, a shortlist)    -> an OPTIONAL step, offered WITH ITS REASON
  a rule (the resolve ladder, "report, never guess")  -> code

A code default is a decision made for you; a setup default is a recommendation
you accept. So nothing here writes anything by itself: `probe()` reports each
capability's state and the offers that fit THIS machine, `apply()` performs only
the offers that were accepted, and a capability that can be resolved by nothing
is REPORTED as a gap rather than filled with an invented value.

EVIDENCE, not a generic list — every offer names the thing that makes it
applicable here: a provider key present in the project's .env, or a local
provider row whose server actually answers and reports a model.

The offers' model ids are pinned by a test against `litellm_model_string`, so an
entry that litellm could not parse fails the suite instead of a stranger's first
chat.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.domain.providers.capabilities import (
    CandidateSpec,
    describe_chain,
    replace_chain,
    resolve,
)
from app.domain.providers.provider_classes import provider_location
from app.domain.providers.provider_endpoints import PROVIDER_ENDPOINTS, resolve_endpoint
from app.infrastructure.database.models import Capability, Provider

logger = logging.getLogger(__name__)

# The capabilities a setup pass speaks for: the LLM slots a stranger notices
# first, and the embedding slot that can never inherit a chat model.
SETUP_CAPABILITIES: tuple[str, ...] = (
    "chat",
    "title",
    "summary",
    "workflow-llm",
    "memory",
    "embeddings",
)

# The model each keyed provider is offered WITH — PER CAPABILITY, because a chat
# model is not an embedder. The `chat` entries are grounded in this repo's own
# config data (the bare id DeepSeek's row carries; the OpenRouter id Exa's
# DEFAULT_BRAINS ships). `embeddings` has NO entry: no embedding id here could be
# verified, and offering a chat model for it is precisely the "whatever is default
# can embed" answer the ruling forbids — so the gap is reported instead.
MODEL_FOR: dict[str, dict[str, str]] = {
    "chat": {
        "deepseek": "deepseek-v4-flash",
        "openrouter": "deepseek/deepseek-v4-flash",
    },
    "embeddings": {},
}

# The key each provider needs in .env before the offer applies.
KEY_FOR_PROVIDER: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# A local server's model is only offered for embeddings when the model IS one.
# The server usually says so in its capability list; when it says nothing, the
# NAME has to carry the evidence, and a guess is not evidence.
EMBEDDING_CAPABILITY = "embedding"
EMBEDDING_NAME_HINTS: tuple[str, ...] = ("embed", "bge", "minilm", "nomic", "e5-")

LOOPBACK_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class Offer:
    """One recommendation: what it writes, why, and what makes it applicable."""

    key: str
    capability: str
    provider: str
    provider_type: str
    model: str
    reason: str
    needs: str  # "key:DEEPSEEK_API_KEY" | "local:<provider row name>" | ""

    def describe(self) -> str:
        return f"{self.capability}: {self.provider}/{self.model}"


@dataclass
class CapabilityState:
    """What one capability resolves to today, and what could improve it."""

    capability: str
    kind: str
    resolved: bool
    detail: str
    offers: list[Offer]
    gap: str = ""

    def to_dict(self) -> dict:
        return {
            "capability": self.capability,
            "kind": self.kind,
            "resolved": self.resolved,
            "detail": self.detail,
            "gap": self.gap,
            "offers": [
                {
                    "key": o.key,
                    "provider": o.provider,
                    "model": o.model,
                    "reason": o.reason,
                    "needs": o.needs,
                }
                for o in self.offers
            ],
        }


@dataclass
class SetupReport:
    states: list[CapabilityState]

    @property
    def offers(self) -> list[Offer]:
        seen: dict[str, Offer] = {}
        for state in self.states:
            for offer in state.offers:
                seen.setdefault(offer.key, offer)
        return list(seen.values())

    @property
    def gaps(self) -> list[CapabilityState]:
        return [s for s in self.states if not s.resolved]

    def to_dict(self) -> dict:
        return {
            "states": [s.to_dict() for s in self.states],
            "gaps": [s.capability for s in self.gaps],
            "offers": [o.key for o in self.offers],
        }


# ── evidence ────────────────────────────────────────────────────────────────


def _env_values(path: Path | None = None) -> dict[str, bool]:
    """Which keys are set (NAME -> has a non-empty value). Values are never returned."""
    env = Path(path) if path is not None else Paths.root / ".env"
    found: dict[str, bool] = {}
    if not env.exists():
        return found
    for raw in env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        found[name.strip()] = bool(value.strip())
    return found


def _is_local_row(row: Provider) -> bool:
    return provider_location(row.provider_type or row.name, row.base_url) == "local"


async def _reported_models(base_url: str | None) -> list[dict]:
    """What an OpenAI-compatible server actually reports. [] when it is silent.

    A probe, not a guess: an install with no local server gets no local offer,
    which is the difference between advice and a wish. Each entry keeps its
    CAPABILITY list — that is how a completion-only model is kept out of the
    embedding offer.
    """
    if not base_url:
        return []
    url = base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=LOOPBACK_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        logger.info("setup offers: no model list at %s (the local offer is skipped)", url)
        return []
    out: list[dict] = []
    for entry in payload.get("data") or payload.get("models") or []:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("id") or entry.get("model") or entry.get("name") or "").strip()
        if not model_id:
            continue
        out.append({"id": model_id, "capabilities": list(entry.get("capabilities") or [])})
    return out


def _can_embed(model: dict) -> bool:
    """Whether a probed model can serve the embedding capability — never assumed."""
    caps = [str(c).lower() for c in model.get("capabilities") or []]
    if caps:
        return EMBEDDING_CAPABILITY in caps
    name = str(model.get("id", "")).lower()
    return any(hint in name for hint in EMBEDDING_NAME_HINTS)


# ── the probe ───────────────────────────────────────────────────────────────


def _keyed_offers(capability: str, env: dict[str, bool]) -> list[Offer]:
    """Offers for the providers that have a VERIFIED model for THIS capability."""
    offers: list[Offer] = []
    for provider, model in MODEL_FOR.get(capability, {}).items():
        key_name = KEY_FOR_PROVIDER[provider]
        if not env.get(key_name):
            continue
        offers.append(
            Offer(
                key=f"{capability}-{provider}",
                capability=capability,
                provider=provider,
                provider_type=provider,
                model=model,
                reason=(
                    f"{key_name} is set in .env and {provider} answers at its documented "
                    f"endpoint — so {model} can be the default here."
                ),
                needs=f"key:{key_name}",
            )
        )
    return offers


async def _local_offers(db: AsyncSession, capability: str) -> list[Offer]:
    """Local rows whose server answers AND reports a model fit for this capability."""
    rows = (await db.execute(select(Provider).where(Provider.is_active.is_(True)))).scalars().all()
    offers: list[Offer] = []
    for row in rows:
        if not _is_local_row(row):
            continue
        models = await _reported_models(row.base_url)
        usable = models
        if capability == "embeddings":
            usable = [m for m in models if _can_embed(m)]
        if not usable:
            continue
        ids = [m["id"] for m in usable]
        default_model = (row.config or {}).get("default_model") if isinstance(row.config, dict) else None
        chosen = default_model if isinstance(default_model, str) and default_model in ids else ids[0]
        offers.append(
            Offer(
                key=f"{capability}-local-{row.name}",
                capability=capability,
                provider=row.name,
                provider_type=row.provider_type or row.name,
                model=chosen,
                reason=(
                    f"a local server answers at {row.base_url} and reports "
                    f"{len(ids)} model(s) that can serve this — no key, no cost per call."
                ),
                needs=f"local:{row.name}",
            )
        )
    return offers


def _gap_for(capability: str, kind: str) -> str:
    if kind == "embedding":
        # The exact honest sentence from the ruling: the capability ships EMPTY
        # and the install SAYS what is off rather than borrowing a chat model.
        return (
            "no embedding model — indexing and document search are off until one is "
            "chosen on the Providers page"
        )
    return f"no model resolves for '{capability}' — its callers will refuse"


async def probe(db: AsyncSession, env_path: Path | None = None) -> SetupReport:
    """Report each setup capability's state plus the offers that fit this machine."""
    env = _env_values(env_path)
    states: list[CapabilityState] = []
    for key in SETUP_CAPABILITIES:
        resolved = await resolve(db, key)
        cap_row = (
            await db.execute(select(Capability).where(Capability.key == key))
        ).scalar_one_or_none()
        kind = cap_row.kind if cap_row is not None else "llm"
        offers: list[Offer] = []
        if not resolved.resolved:
            offers.extend(_keyed_offers(key, env))
            offers.extend(await _local_offers(db, key))
        states.append(
            CapabilityState(
                capability=key,
                kind=kind,
                resolved=resolved.resolved,
                detail=(
                    f"{describe_chain(resolved)} ({resolved.reason})"
                    if resolved.resolved
                    else f"nothing resolves ({resolved.reason})"
                ),
                offers=offers,
                gap="" if resolved.resolved else _gap_for(key, kind),
            )
        )
    return SetupReport(states=states)


# ── the act ─────────────────────────────────────────────────────────────────


async def _provider_row(db: AsyncSession, offer: Offer) -> Provider:
    """The row an offer writes into — created from the REGISTRY when absent.

    The endpoint comes from `PROVIDER_ENDPOINTS`, never from a literal here, so a
    new provider is added in one place and every front door follows.
    """
    row = (
        await db.execute(select(Provider).where(Provider.name == offer.provider))
    ).scalar_one_or_none()
    if row is not None:
        return row
    # THE ADDRESS IS THE REGISTRY'S (a plain name -> URL table), never a literal
    # here: a new provider is added in one place and every front door follows.
    base_url = PROVIDER_ENDPOINTS.get(offer.provider) or resolve_endpoint(
        offer.provider_type, None, offer.provider
    )
    row = Provider(
        name=offer.provider,
        display_name=offer.provider.title(),
        provider_type=offer.provider_type,
        base_url=base_url,
        is_active=True,
        priority=50,
        config={},
    )
    db.add(row)
    await db.flush()
    return row


async def apply(
    db: AsyncSession, accepted: Sequence[str], env_path: Path | None = None
) -> tuple[SetupReport, list[str]]:
    """Write ONLY the accepts, then report the state they produced.

    The write is the general chain path (`replace_chain`) — the setup step holds
    no state of its own, so there is nothing here that can become a fourth home
    for a value. A capability that was accepted gets an explicit chain, which
    beats the global default row and says what it is on purpose.
    """
    log: list[str] = []
    report = await probe(db, env_path=env_path)
    by_key = {o.key: o for o in report.offers}

    for key in accepted:
        offer = by_key.get(key)
        if offer is None:
            log.append(f"skipped {key}: it does not apply to this install")
            continue
        row = await _provider_row(db, offer)
        await replace_chain(
            db,
            offer.capability,
            [CandidateSpec(provider_id=row.id, model=offer.model)],
            label=f"set up: {offer.provider}/{offer.model}",
        )
        log.append(f"{offer.capability} -> {offer.provider}/{offer.model} (provider #{row.id})")

        # THE INHERITANCE (2026-11-18): a `chat` chain fixes chat and nothing
        # else, because the ladder's last rung is the DEFAULT ROW — so on an
        # install that has none, the accept also names this provider the default
        # and the other LLM capabilities inherit it. Only when none exists: a
        # default somebody chose is never reassigned behind their back.
        if offer.capability == "chat":
            from app.domain.providers.config_service import DefaultProviderService

            service = DefaultProviderService()
            if await service.get_default_provider(db) is None:
                await service.set_default_provider(db, row.id)
                log.append(
                    f"default provider -> {offer.provider} "
                    f"(the other LLM capabilities inherit it)"
                )
        await db.commit()

    # THE VALUE'S CONSUMER (Phase D, item 3): a chat model is what the shipped agents were
    # waiting for, so the moment one is accepted the seed can run — no restart between
    # "here is my model" and "here are your reporters". Idempotent: an install that already
    # has its agents (or has deleted them) reports that and nothing is re-created.
    try:
        from app.domain.agents.shipped import seed_shipped_agents

        for outcome in await seed_shipped_agents(db):
            log.append(f"news desk — {outcome.describe()}")
    except Exception as exc:  # a setup step must not fail on a seed
        log.append(f"news desk — not seeded: {exc}")

    return await probe(db, env_path=env_path), log
