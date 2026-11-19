"""The agent clone — a copy is a scoped INSTANCE of the same character.

THE RULING (2026-10-12, the user): *"I want a copy's identity to read: a scoped
instance of the same character."* Two rules follow, and this module writes them
down once, in one place:

- **what describes the CHARACTER travels** — provider and model, the prompt, the
  skills, the tool surface, the cognitive profile, the tags, the operational
  settings, and the FACE (an instance of Bob looks like Bob);
- **what describes the RUN is fresh** — the workspace key (minted by the seam,
  unique against the rows), the folder and its state (scaffolded from the copy's
  OWN row, never copied from the source's), and the name, which carries an
  instance marker (`Bob-2`, not `Bob (Copy)` — a copy marker reads as a fork).

Every field `AgentCreate` declares is claimed by exactly one group below.
`unclassified_fields()` is the census that proves it, and its test fails when a
new schema field arrives unclaimed — which is how this defect formed: the route
hand-built a payload with 8 of 24 fields and the other 16 went nowhere in
silence (`wiki/issues/resolved/embedded-service-literals/duplicated-agent-partial-clone.md`).
"""
from __future__ import annotations

from typing import Any, Iterable

from app.domain.agents.schemas import AgentCreate

# THE CHARACTER — cloned from the source row.
CLONE_FIELDS: frozenset[str] = frozenset({
    "description", "provider", "model", "system_prompt", "is_active",
    "parameters", "template_id", "preferred_providers", "fallback_enabled",
    "allow_delegation", "execution_mode", "behavior_config",
    "cognitive_profile_id", "skills", "profile_image_url", "tags",
    "kit_id", "llm_spec", "package_id",
})

# THE INSTANCE — never carried in.
#   name          → the instance marker (the pool resolves agents BY NAME, and an
#                   exact-name duplicate is rejected outright)
#   workspace_key → minted by the seam, unique against the rows
#   is_builtin    → a copy is an instance, not a protected system agent
FRESH_FIELDS: frozenset[str] = frozenset({"name", "is_builtin", "workspace_key"})

# OUTPUT-only readouts — server-derived from cognitive_profile_id, and filtered
# out by the create path before the row is built. Claimed here so the census is
# exact rather than approximate.
DERIVED_FIELDS: frozenset[str] = frozenset({
    "cognitive_profile_name", "cognitive_profile_depth",
})


def next_instance_name(parent_name: str, existing_names: Iterable[str]) -> str:
    """The instance marker: ``<parent>-<n>``, the lowest free n from 2.

    ``Bob-2``, not ``Bob (Copy)``. The name can never be the parent's own — an
    exact-name duplicate is rejected by the name ban — and a copy marker reads
    as a fork, which the ruling rejects.
    """
    taken = {str(n).strip().lower() for n in existing_names}
    n = 2
    while f"{parent_name}-{n}".strip().lower() in taken:
        n += 1
    return f"{parent_name}-{n}"


def _accepts_none(field: str) -> bool:
    """True when `None` is a legal value for this create field.

    A row can hold NULL where the schema will not take None (`is_active` and
    `allow_delegation` are non-optional bools), so the caller omits those and the
    schema's own default stands, rather than sending a None that fails validation.
    """
    info = AgentCreate.model_fields.get(field)
    if info is None:
        return True
    if info.is_required():
        return False
    return info.default is None


def clone_character(source: Any, existing_names: Iterable[str]) -> AgentCreate:
    """The character's configuration as a create payload, with identity fresh.

    The workspace key is deliberately absent: the seam mints it. A NULL on the
    source row is treated as *absent*, not as an override.
    """
    data: dict[str, Any] = {
        field: getattr(source, field, None)
        for field in CLONE_FIELDS
        if getattr(source, field, None) is not None or _accepts_none(field)
    }
    data["name"] = next_instance_name(source.name, existing_names)
    data["is_builtin"] = False
    return AgentCreate(**data)


def unclassified_fields() -> set[str]:
    """The census: `AgentCreate` fields that no group claims. Empty is the invariant."""
    return set(AgentCreate.model_fields) - (CLONE_FIELDS | FRESH_FIELDS | DERIVED_FIELDS)
