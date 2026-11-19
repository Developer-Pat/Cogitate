"""Canonical tool capability vocabulary (Phase A).

The curated set of capability slugs that ARM (Agent Resource
Manager) will select on — the tool rewrite's frozen vocabulary.
Study: local/tooling-study/12 (the first draft) + 10.

Naming rule: plain, verb-first or noun-verb, kebab-case. No
vendor names (never 'duckduckgo' as identity), no persona names,
no invented codes.

The contract: a capability slug NEVER changes once set (the
vocabulary is frozen here, pre-ARM). Tools DECLARE their
capability; ARM selects by it. Provider choice is a config detail
of the capability, not identity.
"""

from __future__ import annotations

from typing import List, Optional


# ── The vocabulary (frozen at Phase A) ────────────────────────────────

# Search & Retrieval
WEB_SEARCH = "web-search"       # search the web, real-time
WEB_FETCH = "web-fetch"         # fetch a URL → clean text
WIKI_LOOKUP = "wiki-lookup"     # encyclopedia lookup
DOC_LOOKUP = "doc-lookup"       # find/read project docs

# File & Text
FILE_READ = "file-read"         # inspect files, metadata
FILE_WRITE = "file-write"       # create/edit/delete files

# Data & Computation
DB_QUERY = "db-query"           # read-only SQLite
DATETIME = "datetime"           # date/time ops
CODE_EXECUTION = "code-execution"  # the sandboxed python runner

# System & Admin (the keyed tier lives here)
SYSTEM_DIAG = "system-diag"     # health, logs, diagnostics
AGENT_ADMIN = "agent-admin"     # manage agents
WORKFLOW_ADMIN = "workflow-admin"  # manage workflows
PROVIDER_ADMIN = "provider-admin"  # manage providers
MACRO_ADMIN = "macro-admin"     # manage macros/meta-topics
DOC_ADMIN = "doc-admin"         # manage docs
REASONING_AID = "reasoning-aid"  # step-by-step thinking
EVENT_PUBLISH = "event-publish"  # the messaging bus

# Surface (2026-09-15 — ADDED, see the note below)
# Move the user's VIEW to a destination in the app. Resolved against the
# generated page map (domain/tools/page_map.py), never guessed.
#
# WHY ADDED RATHER THAN BORROWED: the vocabulary had no fit. The nearest
# was doc-lookup ("find/read project docs"), and an app PAGE is not a doc —
# labelling it that way would have made ARM select navigation for
# documentation work. This is an ADDITION of a slug, not a change to an
# existing one, which the contract above permits.
UI_NAVIGATE = "ui-navigate"

# The complete vocabulary (the canonical list — order matters for
# display; the set is what ARM validates against)
CAPABILITIES: List[str] = [
    WEB_SEARCH, WEB_FETCH, WIKI_LOOKUP, DOC_LOOKUP,
    FILE_READ, FILE_WRITE,
    DB_QUERY, DATETIME, CODE_EXECUTION,
    SYSTEM_DIAG, AGENT_ADMIN, WORKFLOW_ADMIN, PROVIDER_ADMIN,
    MACRO_ADMIN, DOC_ADMIN, REASONING_AID, EVENT_PUBLISH,
    UI_NAVIGATE,
]

# ── Access tiers (Phase C — the GRAS + keyed model) ───────────────
#
# The tier is declared ON THE CAPABILITY (the vocabulary owns it) —
# every tool inherits its tier from its capability. The rule:
#
#   gras  = read-only, enabled is enough (no grant needed)
#   keyed = side-effectful / admin, needs an explicit grant
#
# The capability implies the tier (study 12's pattern): file-read
# is gras, file-write is keyed; web-search is gras, agent-admin is
# keyed. The admin family is the keyed tier by definition.

GRAS = "gras"
KEYED = "keyed"

# capability → tier (the canonical declaration)
CAPABILITY_TIERS = {
    # Search & Retrieval — all read
    WEB_SEARCH: GRAS, WEB_FETCH: GRAS, WIKI_LOOKUP: GRAS, DOC_LOOKUP: GRAS,
    # File & Text — read vs write split
    FILE_READ: GRAS,
    # FILE_WRITE is GRAS, not KEYED (2026-09-10, the News Team arc).
    # Writing is confined to the agent's OWN workspace: every file tool
    # carries needs_workspace, so the execution service injects the
    # agent's folder as base_path — the sandbox IS the scope. Requiring a
    # grant made a fresh agent able to read everything and write nothing,
    # silently: Lois saw file-manager in her tool list, called it, and was
    # refused ("keyed tier: file-write"), then reported the wall in chat.
    # An explicit agent_tools row with is_enabled=0 still excludes it for
    # one agent (the gras off-switch), and the granted path is unchanged —
    # this only stops a fresh agent being born unable to write its beat.
    FILE_WRITE: GRAS,
    # Data & Computation — query vs write split
    DB_QUERY: GRAS, DATETIME: GRAS, CODE_EXECUTION: GRAS,
    # System & Admin — the keyed tier
    SYSTEM_DIAG: GRAS, AGENT_ADMIN: KEYED, WORKFLOW_ADMIN: KEYED,
    PROVIDER_ADMIN: KEYED, MACRO_ADMIN: KEYED, DOC_ADMIN: KEYED,
    REASONING_AID: GRAS, EVENT_PUBLISH: GRAS,
    # Navigation is GRAS on purpose: it changes what the user is LOOKING AT,
    # not any stored data. Making it KEYED would put an admin grant in front
    # of the flagship "take me there" feature, which is not a security
    # boundary worth having.
    UI_NAVIGATE: GRAS,
}

# the keyed set (for quick membership checks)
KEYED_CAPABILITIES = frozenset(
    cap for cap, tier in CAPABILITY_TIERS.items() if tier == KEYED
)


def tier_for(capability: Optional[str]) -> str:
    """The access tier for a capability (defaults to GRAS for
    unknown/None — read-only is the safe default)."""
    return CAPABILITY_TIERS.get(capability or "", GRAS)


def is_keyed(capability: Optional[str]) -> bool:
    """True if the capability requires a grant to execute."""
    return tier_for(capability) == KEYED


# Family grouping (for display/taxonomy, like tool_categories)
CAPABILITY_FAMILIES = {
    "Search & Retrieval": [WEB_SEARCH, WEB_FETCH, WIKI_LOOKUP, DOC_LOOKUP,
                           UI_NAVIGATE],
    "File & Text": [FILE_READ, FILE_WRITE],
    "Data & Computation": [DB_QUERY, DATETIME, CODE_EXECUTION],
    "System & Admin": [SYSTEM_DIAG, AGENT_ADMIN, WORKFLOW_ADMIN,
                       PROVIDER_ADMIN, MACRO_ADMIN, DOC_ADMIN,
                       REASONING_AID, EVENT_PUBLISH],
}


def is_valid_capability(capability: Optional[str]) -> bool:
    """True if the capability is a member of the frozen vocabulary."""
    return capability in CAPABILITIES


def family_for(capability: str) -> Optional[str]:
    """The family a capability belongs to (for display)."""
    for family, members in CAPABILITY_FAMILIES.items():
        if capability in members:
            return family
    return None
