"""READINESS — the install's ONE verdict, measured where the facts live.

WHY THIS MODULE EXISTS. The Setup page used to draw its checklist in the browser from three
calls — `/providers/managed/keys`, `/providers/default`, and a POST to provider id **1** to
guess whether Ollama was up — with `agentReady` hardcoded True. The Dashboard drew nothing at
all, so a fresh install that could not answer a single message looked healthy on the landing
page (measured on a fresh clone: `{"providers":[],"total":0}`, no default provider, no agents,
and the dashboard silent about all three).

So the facts are measured HERE, in the process that knows, and one endpoint feeds both screens
— and, later, the acceptance check the install docs and the agent skill quote.

THE STATES, and what each licenses a surface to say:

    ok        the fact holds now
    unmet     the user has to act, and the detail says what to do
    blocked   waiting on another item — the user CANNOT act yet, so the copy must not ask
    optional  not needed to answer; never counted in `remaining`

A blocked item is the one most easily got wrong: the old checklist told a stranger to "pick a
capability profile" while zero profiles existed, because the seed was waiting for a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.providers.capabilities import resolve
from app.domain.providers.env_key_store import env_key_store
from app.infrastructure.database.models import Agent, Provider

OK = "ok"
UNMET = "unmet"
BLOCKED = "blocked"
OPTIONAL = "optional"

# Where each item's fix lives, in the app's own vocabulary. The href is what a button on the
# card (or a tile in the checklist) navigates to; nothing here writes anything.
# THE DOOR IS THE TAB, NOT THE PAGE (2026-11-21, measured on a from-zero install). The Provider
# Dashboard opens on CURATED — recommendations, not the chat model — so an item pointing at
# `/provider-dashboard` landed a stranger one tab away from the thing it named. Each href names the
# tab that fixes the item, and both tabs can now do their job from nothing: the Keys tab creates the
# first provider (key and row in one form), the Default tab offers the provider+model picker.
HREF_PROVIDER = "/providers/cloud?tab=keys"
HREF_MODEL = "/providers/cloud?tab=default"
HREF_AGENTS = "/agent-profiles"
HREF_RUNTIME = "/exa"


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    label: str
    state: str
    detail: str
    href: str
    counted: bool = True


@dataclass
class ReadinessReport:
    items: list[ReadinessItem] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        """How many counted items are not `ok` — the number a stranger is told."""
        return sum(1 for i in self.items if i.counted and i.state != OK)

    @property
    def ready(self) -> bool:
        return self.remaining == 0

    def item(self, key: str) -> Optional[ReadinessItem]:
        return next((i for i in self.items if i.key == key), None)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "remaining": self.remaining,
            "items": [
                {
                    "key": i.key,
                    "label": i.label,
                    "state": i.state,
                    "detail": i.detail,
                    "href": i.href,
                    "counted": i.counted,
                }
                for i in self.items
            ],
        }


def _settings_key(provider_type: str) -> str:
    """The `.env`-backed settings attribute for a provider type, when it has one."""
    settings = get_settings()
    return {
        "openrouter": settings.openrouter_api_key,
        "deepseek": settings.deepseek_api_key,
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "ollama_cloud": settings.ollama_cloud_api_key,
    }.get(provider_type, "") or ""


def _is_dialable(row: Provider) -> bool:
    """A key for a keyed provider, or a loopback address for a local one.

    A local server needs no key: refusing it would report a working install as unconfigured.
    """
    if env_key_store.get_key(row.provider_type) or _settings_key(row.provider_type):
        return True
    base = (row.base_url or "").lower()
    return "localhost" in base or "127.0.0.1" in base or "::1" in base


async def _provider_item(db: AsyncSession) -> ReadinessItem:
    rows = (await db.execute(select(Provider))).scalars().all()
    dialable = [r for r in rows if _is_dialable(r)]
    if not rows:
        return ReadinessItem(
            key="provider",
            label="Provider + key",
            state=UNMET,
            detail=(
                "No provider yet. Add one on the Provider Dashboard (deepseek and openrouter "
                "are the two this build offers) and paste its key — or point Cogitate at a "
                "local model server."
            ),
            href=HREF_PROVIDER,
        )
    if not dialable:
        return ReadinessItem(
            key="provider",
            label="Provider + key",
            state=UNMET,
            detail=(
                f"{len(rows)} provider row(s), none with a key. Paste one on the Setup page's "
                "API Keys tab and nothing else needs to change."
            ),
            href=HREF_PROVIDER,
        )
    return ReadinessItem(
        key="provider",
        label="Provider + key",
        state=OK,
        detail=f"{len(dialable)} of {len(rows)} provider(s) can be dialled.",
        href=HREF_PROVIDER,
    )


def _chat_model_string(primary: Any) -> str:
    """The model string for the resolved chat row, built where every other caller builds it.

    A model that already carries its handler (`~deepseek/…`) is printed as it stands; one that does
    not gets the provider's prefix. A string the client cannot build is still the row's own answer.
    """
    from app.domain.providers.litellm_route import litellm_model_string

    try:
        return str(litellm_model_string(primary.provider, primary.model, primary.provider_type))
    except Exception:
        return str(primary.model)


async def _chat_item(db: AsyncSession) -> ReadinessItem:
    resolved = await resolve(db, "chat")
    primary = resolved.primary
    if resolved.resolved and primary is not None and primary.model:
        return ReadinessItem(
            key="chat",
            label="Chat model",
            state=OK,
            # THE ONE HOME FOR THE STRING (2026-11-20): `provider/model` printed a doubled prefix
            # for a row whose model already carries one (`deepseek/~deepseek/…`). The route module
            # builds this string everywhere else, so it builds it here too.
            detail=f"{_chat_model_string(primary)} answers chat; title, summary, "
            "workflow and memory inherit it.",
            href=HREF_MODEL,
        )
    return ReadinessItem(
        key="chat",
        label="Chat model",
        state=UNMET,
        detail=(
            "Nothing answers chat yet. Set a default provider and model on the Provider "
            "Dashboard — every other LLM capability inherits it."
        ),
        href=HREF_MODEL,
    )


async def _agents_item(db: AsyncSession, chat: ReadinessItem) -> ReadinessItem:
    count = (
        await db.execute(select(func.count()).select_from(Agent).where(Agent.is_active.is_(True)))
    ).scalar_one()
    if count:
        return ReadinessItem(
            key="agents",
            label="Agents",
            state=OK,
            detail=f"{count} agent(s) installed.",
            href=HREF_AGENTS,
        )
    if chat.state != OK:
        return ReadinessItem(
            key="agents",
            label="Agents",
            state=BLOCKED,
            detail=(
                "Bob and Lois arrive once a chat model resolves — the seed is waiting, and "
                "runs on the next start (or the moment a model is accepted)."
            ),
            href=HREF_AGENTS,
        )
    return ReadinessItem(
        key="agents",
        label="Agents",
        state=UNMET,
        detail=(
            "A model answers and no agents exist yet. The shipped reporters seed the moment a "
            "chat model is set — set the default model again to seed now, or restart."
        ),
        href=HREF_AGENTS,
    )


async def _runtime_item(db: AsyncSession) -> ReadinessItem:
    """Exa's external runtime — never counted, because Exa is a decision, not a requirement."""
    from app.domain.external_agent.services import get_config, probe_runnable

    try:
        blocked = probe_runnable(await get_config(db))
    except Exception as exc:  # a readiness read must not fail the page
        return ReadinessItem(
            key="runtime",
            label="Exa runtime (optional)",
            state=OPTIONAL,
            detail=f"Could not be probed: {exc}",
            href=HREF_RUNTIME,
            counted=False,
        )
    if blocked is None:
        return ReadinessItem(
            key="runtime",
            label="Exa runtime (optional)",
            state=OK,
            detail="Exa's runtime is on PATH. Activation is still your decision.",
            href=HREF_RUNTIME,
            counted=False,
        )
    return ReadinessItem(
        key="runtime",
        label="Exa runtime (optional)",
        state=OPTIONAL,
        detail=f"Exa needs an external runtime: {blocked}",
        href=HREF_RUNTIME,
        counted=False,
    )


async def measure(db: AsyncSession) -> ReadinessReport:
    """Measure every fact once, in the order a stranger meets them."""
    provider = await _provider_item(db)
    chat = await _chat_item(db)
    agents = await _agents_item(db, chat)
    runtime = await _runtime_item(db)
    return ReadinessReport(items=[provider, chat, agents, runtime])
