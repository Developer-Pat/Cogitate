"""The SHIPPED AGENTS — the news desk's first two reporters.

A shipped agent is a TRACKED PACKAGE at `backend/templates/agents/<key>/`:

    package.json   the identity and the character's configuration — skills, kits,
                   parameters, the face. Never a service, never a fact.
    persona.md     the system prompt (the character's charter).

THE SPLIT (the one every other seed this phase follows — structure ships, values are
offered):

* **structure ships** — the agent row, its workspace folder, its skills (copied from
  the shared library), its kits, its face.
* **the SERVICE is this install's own answer** to "what answers chat here", taken from
  the resolver's ladder (`providers.capabilities.resolve`). No package names a model:
  a stranger's keys and a stranger's hardware decide that, and a model id written into
  a seed is wrong the day after it is written.
* **nothing is guessed** — an install whose chat question nothing can answer yet DEFERS
  the agents, says why, and tries again on the next boot (and the moment the setup step
  accepts a chat model, which is when the value finally exists).
* **the STATE is empty** — no memory, no beats, no reports. The persona carries the
  craft; the assignments are the person's to give. (`workspace.scaffold` writes the empty
  `state.json`, so the update-state/update-sources tools have a well-formed store from
  the first turn.)

WHY NOT `export_service.import_agent`. That path copies an agent that already exists —
its memory included — and renames it `<name>-imported-<hex>`, because an import is a
COPY of somebody's agent. A shipped agent is not a copy; it is a seed, so it takes its
own path: no memory, the stable workspace key the package declares, no suffix.

A DELETED SHIPPED AGENT STAYS DELETED. Each seeded key leaves a `system_flags` marker,
so a person who removed Bob keeps him removed: this is a first-install seed, not a
resurrection loop. The marker is written when the agent is created AND when an agent
that already carries its name or key is adopted (this is how an installation that made
Bob by hand stops the seed from making a second one).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from app.core.config import Paths, get_settings
from app.domain.agents.workspace import scaffold
from app.domain.collections.models import Collection, CollectionItem
from app.domain.tools.models import Tool as ToolModel
from app.infrastructure.database.models import Agent, SystemFlag

logger = logging.getLogger(__name__)

# One marker per package, written once and never removed.
FLAG_PREFIX = "shipped-agent:"

# The four answers this seed can give for one package. `invalid` and `failed` are
# per-package on purpose: a broken package must not cost the person the other one.
CREATED = "created"
PRESENT = "present"
DEFERRED = "deferred"
INVALID = "invalid"
FAILED = "failed"


@dataclass(frozen=True)
class KitSpec:
    """One toolkit a package names — resolved by NAME, filled from tool names."""

    name: str
    description: str = ""
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShippedAgent:
    """One package, read and validated."""

    key: str
    name: str
    description: str
    persona: str
    skills: tuple[str, ...]
    kits: tuple[KitSpec, ...]
    tags: tuple[str, ...]
    parameters: dict[str, Any]
    llm_spec: dict[str, Any]
    execution_mode: str
    face: Optional[str]


@dataclass(frozen=True)
class SeedOutcome:
    """What the seed DID about one package — reported per package, never summarised away."""

    key: str
    status: str
    detail: str

    def describe(self) -> str:
        return f"{self.key}: {self.status} — {self.detail}"


# ---------------------------------------------------------------------------
# Reading the packages
# ---------------------------------------------------------------------------


def _paths() -> Paths:
    return Paths.from_settings(get_settings())


def read_package(folder: Path) -> ShippedAgent:
    """Read and validate one package folder. Raises ValueError with the reason.

    Validation is deliberately strict about the things that would otherwise write
    something wrong quietly: the folder name IS the workspace key (two names for one
    agent drift), and a package with no persona would create a character with no charter.
    """
    manifest = folder / "package.json"
    if not manifest.is_file():
        raise ValueError(f"no package.json in {folder}")

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"package.json is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("package.json is not an object")

    if str(data.get("format_version") or "") != "1.0":
        raise ValueError(f"unsupported format_version {data.get('format_version')!r}")

    key = str(data.get("key") or "").strip()
    name = str(data.get("name") or "").strip()
    if not key or not name:
        raise ValueError("key and name are both required")
    if key != folder.name:
        raise ValueError(f"key {key!r} does not match its folder {folder.name!r}")

    persona_file = folder / str(data.get("persona") or "persona.md")
    if not persona_file.is_file():
        raise ValueError(f"no persona at {persona_file.name}")
    persona = persona_file.read_text(encoding="utf-8").strip()
    if not persona:
        raise ValueError(f"{persona_file.name} is empty")

    skills = data.get("skills") or []
    if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
        raise ValueError("skills must be a list of names")

    kits: list[KitSpec] = []
    for raw in data.get("kits") or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            raise ValueError("each kit needs a name")
        tools = raw.get("tools") or []
        if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
            raise ValueError(f"kit {raw.get('name')!r}: tools must be a list of tool names")
        kits.append(
            KitSpec(
                name=str(raw["name"]).strip(),
                description=str(raw.get("description") or "").strip(),
                tools=tuple(str(t).strip() for t in tools),
            )
        )

    return ShippedAgent(
        key=key,
        name=name,
        description=str(data.get("description") or "").strip(),
        persona=persona,
        skills=tuple(str(s).strip() for s in skills),
        kits=tuple(kits),
        tags=tuple(str(t) for t in (data.get("tags") or [])),
        parameters=dict(data.get("parameters") or {}),
        llm_spec=dict(data.get("llm_spec") or {}),
        execution_mode=str(data.get("execution_mode") or "llm"),
        face=(str(data["face"]).strip() if data.get("face") else None),
    )


# ---------------------------------------------------------------------------
# The pieces an install supplies
# ---------------------------------------------------------------------------


async def _chat_service(db) -> tuple[Optional[tuple[str, str]], str]:
    """The install's own answer to "what answers chat", plus the rung that answered.

    `(None, reason)` means nothing resolves — the caller DEFERS and reports the reason.
    A candidate with no model is skipped rather than written into a row: an agent whose
    model is empty is a hole every consumer has to tolerate.
    """
    # Imported here, not at module load: `providers.capabilities` documents a cycle that
    # closes the moment anything imports it first (it reaches the vector store).
    from app.domain.providers.capabilities import resolve

    resolved = await resolve(db, "chat")
    for candidate in resolved.candidates:
        if candidate.provider and candidate.model:
            return (candidate.provider, candidate.model), resolved.reason
    return None, resolved.reason


def _ensure_face(face: Optional[str]) -> Optional[str]:
    """Copy a curated face into the served store (additive) and return its URL.

    The curated pool is git-tracked (`assets/agent-images/`) and the store that `/static`
    serves is `data/profile_images/`; the copy is missing-files-only, so a person who
    replaced an image keeps theirs.
    """
    if not face:
        return None
    paths = _paths()
    source = paths.agent_images_dir / face
    if not source.is_file():
        logger.warning("shipped agent face %r is not in %s — the agent ships faceless", face, paths.agent_images_dir)
        return None
    store = Path(get_settings().profile_images_dir)
    store.mkdir(parents=True, exist_ok=True)
    target = store / face
    if not target.exists():
        target.write_bytes(source.read_bytes())
    return f"/static/{face}"


def _stored_entity_id(tool_id: str) -> str:
    """The form `tools.id` is actually stored in: 32 hex characters, no dashes.

    `Tool.id` is a UUID column and `CollectionItem.entity_id` is a plain String, so an id
    read back through the UUID-typed attribute can stringify WITH dashes — every join then
    misses. Measured on a fresh install: all 12 kit members dangled this way, the seeded
    agents were offered zero tools, and the model invented a textual `<tool_call>` block.
    """
    return str(tool_id).replace("-", "")


async def _ensure_kit(db, spec: KitSpec) -> tuple[Collection, list[str]]:
    """Find or create a kit BY NAME, fill in the tools it names, return the unresolved ones.

    Two rules here: a kit that already exists is REUSED (its name is the handle, so the
    install does not collect duplicates), and only MISSING members are added — a kit a
    person curated is never reset. A tool name the registry does not carry is reported,
    not invented (a half-built kit is better than a kit naming a tool that does not exist).
    """
    result = await db.execute(
        select(Collection).where(
            Collection.name == spec.name, Collection.entity_type == "tool"
        )
    )
    kit = result.scalars().first()
    if kit is None:
        kit = Collection(
            id=str(uuid.uuid4()),
            user_key="default",
            name=spec.name,
            description=spec.description or None,
            entity_type="tool",
        )
        db.add(kit)
        await db.flush()

    present = {
        _stored_entity_id(v)
        for v in (
            await db.execute(
                select(CollectionItem.entity_id).where(CollectionItem.collection_id == kit.id)
            )
        )
        .scalars()
        .all()
    }
    unresolved: list[str] = []
    for tool_name in spec.tools:
        tool = (
            await db.execute(select(ToolModel).where(ToolModel.name == tool_name))
        ).scalars().first()
        if tool is None:
            unresolved.append(tool_name)
            continue
        stored_id = _stored_entity_id(tool.id)
        if stored_id in present:
            continue
        db.add(
            CollectionItem(
                id=str(uuid.uuid4()),
                collection_id=kit.id,
                entity_id=stored_id,
                entity_type="tool",
                entity_name=tool.name,
            )
        )
        present.add(stored_id)
    return kit, unresolved


# ---------------------------------------------------------------------------
# The seed
# ---------------------------------------------------------------------------


async def _existing_agent(db, package: ShippedAgent) -> Optional[Agent]:
    """An agent that already IS this package — by workspace key or by name.

    Matching on the name as well as the key is what keeps an installation that made Bob
    by hand (his folder is `bob`, but a person may have named the key anything) from
    gaining a second Bob. Soft-deleted rows count: a deleted agent is a decision.
    """
    result = await db.execute(
        select(Agent).where(
            (Agent.workspace_key == package.key) | (Agent.name == package.name)
        )
    )
    found = result.scalars().first()
    return found if isinstance(found, Agent) else None


async def _mark(db, package: ShippedAgent, agent_id: int) -> None:
    """Remember that this key has been seen — so a later deletion is not undone."""
    db.add(SystemFlag(key=f"{FLAG_PREFIX}{package.key}", value=str(agent_id)))


async def _create(db, package: ShippedAgent, service: tuple[str, str]) -> Agent:
    """Create the row, its workspace, its kits and its face."""
    provider, model = service
    agent = Agent(
        name=package.name,
        description=package.description,
        provider=provider,
        model=model,
        system_prompt=package.persona,
        workspace_key=package.key,
        is_active=True,
        skills=list(package.skills),
        tags=list(package.tags),
        parameters=package.parameters or None,
        llm_spec=package.llm_spec or None,
        execution_mode=package.execution_mode,
        profile_image_url=_ensure_face(package.face),
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)

    # The workspace manifests the row: the derived agent.json, the skills copied from
    # the shared library, the empty state.json and persona.md.
    scaffold(agent)

    from app.domain.agent_kits.service import AgentKitService

    kits = AgentKitService(db)
    for spec in package.kits:
        kit, unresolved = await _ensure_kit(db, spec)
        if unresolved:
            logger.warning(
                "shipped agent %s: kit %r names tools this install does not carry — %s",
                package.key,
                spec.name,
                ", ".join(unresolved),
            )
        await kits.attach(agent.id, kit.id)

    await _mark(db, package, agent.id)
    return agent


async def seed_shipped_agents(db) -> list[SeedOutcome]:
    """Seed every package the installation carries. Idempotent; safe to call at boot.

    Returns one outcome per package, so a caller can SAY what happened — the boot log
    and the setup step both print them rather than reporting "seeded" and leaving the
    person to find out which agents exist.
    """
    root = _paths().agent_seed_dir
    if not root.is_dir():
        return []

    outcomes: list[SeedOutcome] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            package = read_package(folder)
        except (ValueError, OSError) as exc:
            logger.warning("shipped agent package %s ignored — %s", folder.name, exc)
            outcomes.append(SeedOutcome(folder.name, INVALID, str(exc)))
            continue

        flag = await db.get(SystemFlag, f"{FLAG_PREFIX}{package.key}")
        if flag is not None:
            outcomes.append(
                SeedOutcome(package.key, PRESENT, f"seeded earlier (agent #{flag.value})")
            )
            continue

        existing = await _existing_agent(db, package)
        if existing is not None:
            await _mark(db, package, existing.id)
            await db.commit()
            outcomes.append(
                SeedOutcome(package.key, PRESENT, f"agent #{existing.id} already exists — adopted")
            )
            continue

        service, reason = await _chat_service(db)
        if service is None:
            outcomes.append(SeedOutcome(package.key, DEFERRED, reason))
            logger.warning(
                "shipped agent %s deferred: nothing answers chat on this install yet (%s). "
                "It is seeded on the next start, or as soon as the setup step takes a chat model.",
                package.name,
                reason,
            )
            continue

        try:
            agent = await _create(db, package, service)
            await db.commit()
        except Exception as exc:  # one broken package must not cost the other
            await db.rollback()
            logger.warning("shipped agent %s could not be created — %s", package.key, exc)
            outcomes.append(SeedOutcome(package.key, FAILED, str(exc)))
            continue

        outcomes.append(
            SeedOutcome(
                package.key,
                CREATED,
                f"agent #{agent.id} — {service[0]}/{service[1]}",
            )
        )
        logger.info(
            "shipped agent %s created: agent #%d (%s/%s), workspace %r",
            package.name,
            agent.id,
            service[0],
            service[1],
            agent.workspace_key,
        )

    return outcomes
