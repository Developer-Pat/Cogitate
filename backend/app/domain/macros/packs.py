"""THE SHIPPED MACRO PACKS — the banks a fresh install comes up with.

A pack is a folder under `macros/`:

    macros/<key>/meta-topic.json        the topic, and which surface/bank it binds to
    macros/<key>/macro-sets/*.json      up to five sets, each up to five prompts

WHY A DIRECTORY OF FILES AND NOT PYTHON CONSTANTS: the content is a hundred and
twenty-five prompts that people edit in place — a diff per set reads like prose,
a diff inside a dict literal does not. The folder also mirrors `agents/<key>/`,
the shipped-agent package shape, so an install carries its content, not its code.

WHY `surface` AND `role` SIT IN THE MANIFEST AND NOT IN A COLUMN: the frontend
resolves an unset F/A choice from a few facts — which topic is the F default on
this surface, which one feeds the A keys — and the seed already knows the answer
because it is the thing that created the rows. The manifest states the intent;
`system_flags` records the row it landed on. `role: null` means SHIPPED BUT
UNASSIGNED: the topic exists, the user may point the keys at it, and the seed
must never make that choice for them.

THE MARK (the shipped-agents pattern): `system_flags['shipped-macro-pack:<key>']
= <meta topic id>`. Ids, not names — a topic the user renames keeps its binding,
and a topic the user deletes is not resurrected on the next boot.

NEVER OVERWRITES: a set that already exists (user_key + topic + name) is left
exactly as it is. The pack is an installer, not a sync. `seeds.AKEYS_SETS` and
the `a-key-macros` pack describe the same five sets on purpose: on a fresh
install the seed runs first and the pack adopts its rows, so the two cannot
drift into a second A-Key bank.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths, get_settings
from app.infrastructure.database.models import MacroSet, MetaTopic, SystemFlag

logger = logging.getLogger(__name__)

FLAG_PREFIX = "shipped-macro-pack:"
USER_KEY = "default"
SURFACES = ("agent", "exa")
ROLES = ("default", "action")
SLOT_FIELDS = ("f1_macro", "f2_macro", "f3_macro", "f4_macro", "f5_macro")

# Outcomes — one per pack, reported rather than counted away.
CREATED = "created"
ADOPTED = "adopted"
PRESENT = "present"
INVALID = "invalid"


@dataclass(frozen=True)
class PackOutcome:
    """What the seed DID about one pack."""

    key: str
    status: str
    detail: str

    def describe(self) -> str:
        return f"{self.key}: {self.status} — {self.detail}"


@dataclass(frozen=True)
class PackSet:
    topic: str
    name: str
    description: str
    macros: tuple[Optional[str], ...]
    sort_order: int

    @property
    def filled(self) -> int:
        return sum(1 for m in self.macros if m and m.strip())


@dataclass(frozen=True)
class Pack:
    key: str
    name: str
    description: str
    surface: str
    role: Optional[str]
    sets: tuple[PackSet, ...]

    @property
    def prompt_count(self) -> int:
        return sum(s.filled for s in self.sets)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name} is unreadable: {exc}") from exc


def read_set(path: Path) -> PackSet:
    """Read and validate one macro-set file."""
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not an object")

    topic = str(data.get("topic") or "").strip()
    name = str(data.get("name") or "").strip()
    if not topic:
        raise ValueError(f"{path.name} has no topic")
    if not name:
        raise ValueError(f"{path.name} has no name")

    macros = data.get("macros")
    if not isinstance(macros, dict):
        raise ValueError(f"{path.name} has no macros object")

    values: list[Optional[str]] = []
    for index in range(1, 6):
        raw = macros.get(f"f{index}")
        values.append(str(raw).strip() if raw not in (None, "") else None)

    return PackSet(
        topic=topic,
        name=name,
        description=str(data.get("description") or ""),
        macros=tuple(values),
        sort_order=int(data.get("sort_order") or 0),
    )


def read_pack(folder: Path) -> Pack:
    """Read and validate one pack folder. Raises ValueError with the reason.

    Strict about the things that would otherwise install something wrong quietly:
    a folder name that is not the pack key (two names for one pack drift), a
    surface the app does not have, a sixth set (the M/A keys carry five), and two
    sets mapping the same topic (the second would be unreachable).
    """
    data = _read_json(folder / "meta-topic.json")
    if not isinstance(data, dict):
        raise ValueError("meta-topic.json is not an object")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("meta-topic.json has no name")

    surface = str(data.get("surface") or "").strip()
    if surface not in SURFACES:
        raise ValueError(f"surface {surface!r} is not one of {SURFACES}")

    role = data.get("role")
    role = str(role).strip() if role not in (None, "") else None
    if role is not None and role not in ROLES:
        raise ValueError(f"role {role!r} is not one of {ROLES} (or null)")

    files = data.get("macro_sets")
    if not isinstance(files, list) or not files:
        raise ValueError("macro_sets must be a non-empty list")
    if len(files) > 5:
        raise ValueError(f"{len(files)} sets — the M/A keys carry five")

    sets = tuple(read_set(folder / "macro-sets" / str(entry)) for entry in files)
    seen: set[str] = set()
    for item in sets:
        if item.topic in seen:
            raise ValueError(f"two sets map the topic {item.topic!r}")
        seen.add(item.topic)

    return Pack(
        key=folder.name,
        name=name,
        description=str(data.get("description") or ""),
        surface=surface,
        role=role,
        sets=sets,
    )


def pack_root() -> Path:
    return Paths.from_settings(get_settings()).macro_packs_dir


def read_packs(root: Optional[Path] = None) -> list[Pack]:
    """Every pack the installation carries, in folder order.

    A directory without `meta-topic.json` is not a pack and is ignored silently
    (the corpus carries older hand-made folders that predate the manifest). One
    whose manifest names no `surface` predates this contract too — it is an
    EXAMPLE, not something a fresh install should land, so it is skipped in the
    same way. One that FAILS validation is reported, never silently dropped.
    """
    root = root or pack_root()
    if not root.is_dir():
        return []

    packs: list[Pack] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = folder / "meta-topic.json"
        if not manifest.is_file():
            continue
        try:
            if "surface" not in _read_json(manifest):
                continue
        except ValueError as exc:
            logger.warning("macro pack %s ignored — %s", folder.name, exc)
            continue
        packs.append(read_pack(folder))
    return packs


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


def _mappings(pack: Pack) -> str:
    """The M/A slot labels in set order — cosmetic, but the Macros page shows them."""
    prefix = "A" if pack.role == "action" else "M"
    return json.dumps(
        [{"topic": item.topic, "slot_start": f"{prefix}{index + 1}"} for index, item in enumerate(pack.sets)]
    )


async def _topic_named(db: AsyncSession, name: str) -> Optional[MetaTopic]:
    result = await db.execute(
        select(MetaTopic).where(MetaTopic.user_key == USER_KEY, MetaTopic.name == name)
    )
    return result.scalars().first()


async def apply_pack(db: AsyncSession, pack: Pack) -> PackOutcome:
    """Install one pack. Idempotent; never overwrites a set that exists."""
    flag = await db.get(SystemFlag, f"{FLAG_PREFIX}{pack.key}")
    if flag is not None:
        return PackOutcome(pack.key, PRESENT, f"seeded earlier (meta-topic #{flag.value})")

    topic = await _topic_named(db, pack.name)
    status = CREATED
    if topic is None:
        topic = MetaTopic(
            user_key=USER_KEY,
            namespace="agent",
            name=pack.name,
            description=pack.description,
            topic_mappings=_mappings(pack),
            is_active=True,
        )
        db.add(topic)
        await db.flush()
    else:
        # An existing topic keeps its mappings: the user's order is a decision.
        status = ADOPTED

    created = 0
    for item in pack.sets:
        existing = await db.execute(
            select(MacroSet).where(
                MacroSet.user_key == USER_KEY,
                MacroSet.topic == item.topic,
                MacroSet.name == item.name,
            )
        )
        if existing.scalars().first() is not None:
            continue
        db.add(
            MacroSet(
                user_key=USER_KEY,
                namespace="agent",
                topic=item.topic,
                name=item.name,
                description=item.description,
                is_active=True,
                sort_order=item.sort_order,
                **{field: value for field, value in zip(SLOT_FIELDS, item.macros)},
            )
        )
        created += 1

    db.add(SystemFlag(key=f"{FLAG_PREFIX}{pack.key}", value=str(topic.id)))
    await db.commit()

    detail = f"meta-topic #{topic.id}, {created}/{len(pack.sets)} sets new"
    if status == ADOPTED:
        detail += " (existing topic adopted, its mappings kept)"
    logger.info("shipped macro pack %s %s: %s", pack.key, status, detail)
    return PackOutcome(pack.key, status, detail)


async def seed_shipped_macro_packs(db: AsyncSession) -> list[PackOutcome]:
    """Apply every pack the installation carries. One outcome each, never summarised."""
    return await seed_packs_from(db, pack_root())


async def seed_packs_from(db: AsyncSession, root: Path) -> list[PackOutcome]:
    """`seed_shipped_macro_packs` against an explicit directory (the tests' seam)."""
    if not root.is_dir():
        return []

    outcomes: list[PackOutcome] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = folder / "meta-topic.json"
        if not manifest.is_file():
            continue
        try:
            if "surface" not in _read_json(manifest):
                continue
            pack = read_pack(folder)
        except ValueError as exc:
            logger.warning("macro pack %s ignored — %s", folder.name, exc)
            outcomes.append(PackOutcome(folder.name, INVALID, str(exc)))
            continue

        try:
            outcomes.append(await apply_pack(db, pack))
        except Exception as exc:  # one broken pack must not cost the others
            await db.rollback()
            logger.warning("macro pack %s could not be installed — %s", pack.key, exc)
            outcomes.append(PackOutcome(pack.key, INVALID, str(exc)))
    return outcomes


# ---------------------------------------------------------------------------
# The bindings the frontend resolves from
# ---------------------------------------------------------------------------


async def pack_bindings(
    db: AsyncSession, root: Optional[Path] = None
) -> dict[str, dict[str, Optional[int]]]:
    """Which meta-topic feeds each surface's F keys and A keys.

    Read from the marks, then CONFIRMED against the table: a marked topic that has
    since been deleted or deactivated binds nothing, and the frontend falls through
    to the next rule rather than pointing at a row that is not there.
    """
    bindings: dict[str, dict[str, Optional[int]]] = {
        surface: {"f": None, "a": None} for surface in SURFACES
    }
    root = root or pack_root()
    if not root.is_dir():
        return bindings

    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = folder / "meta-topic.json"
        if not manifest.is_file():
            continue
        try:
            if "surface" not in _read_json(manifest):
                continue
            pack = read_pack(folder)
        except ValueError:
            continue
        if pack.role is None:
            continue  # shipped, unassigned — by design it claims no key

        flag = await db.get(SystemFlag, f"{FLAG_PREFIX}{pack.key}")
        if flag is None or not flag.value:
            continue
        try:
            topic_id = int(flag.value)
        except ValueError:
            continue

        topic = await db.get(MetaTopic, topic_id)
        if topic is None or not topic.is_active:
            continue

        slot = "f" if pack.role == "default" else "a"
        bindings[pack.surface][slot] = topic_id

    return bindings
