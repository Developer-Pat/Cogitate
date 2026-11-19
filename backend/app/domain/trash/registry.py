"""THE TRASH DOMAIN REGISTRY — the ONE map of shelves.

The vocabulary of the trash lives HERE, and only here: a domain is registered
with a key (which is also its directory name), and everything else — the
locator's `trash_dir_for`, the service, the page's tabs, Exa's endpoints — asks
this map. That is what makes a sixth shelf a FILE PLUS A REGISTRATION rather
than a page edit, and it is why `Paths` carries no copy.

THE KEY IS VALIDATED TWICE, ON PURPOSE, and neither check is decorative:

- HERE, at registration: a key must be one clean path segment, and two domains
  cannot share one. A duplicated key would silently make one shelf inherit the
  other's entries.
- AT THE LOCATOR (`Paths.trash_dir_for`): the same shape rule, so a shelf
  cannot be CREATED by asking for it with a malformed name.

A misspelled key is therefore refused by `get_domain` before any directory is
touched, which is what stops a typo from planting `trash/agnts/` — a shelf
nothing renders and nothing claims.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.trash.adapters.agents import AgentsTrash
from app.domain.trash.adapters.dbs import DbsTrash
from app.domain.trash.adapters.misc import MiscTrash
from app.domain.trash.adapters.reports import ReportsTrash
from app.domain.trash.adapters.runs import RunsTrash
from app.domain.trash.interface import TrashDomain

_DOMAINS: dict[str, TrashDomain] = {}


def _valid_key(key: str) -> bool:
    """One clean path segment — the locator's own rule, applied where the
    vocabulary lives."""
    return bool(key) and key == Path(key).name and not key.startswith(".")


def register_domain(domain: TrashDomain) -> TrashDomain:
    """Add one shelf to the map. Raises ValueError on a malformed or doubled
    key — a bad shelf is refused at the door rather than discovered later."""
    if not _valid_key(domain.key):
        raise ValueError(
            f"a trash domain key must be a single clean path segment, "
            f"got {domain.key!r}"
        )
    if domain.key in _DOMAINS:
        raise ValueError(
            f"the trash already has a shelf named {domain.key!r} "
            f"({type(_DOMAINS[domain.key]).__name__})"
        )
    _DOMAINS[domain.key] = domain
    return domain


def get_domain(key: str) -> TrashDomain:
    """The shelf registered under `key`, or ValueError naming the ones that
    exist — so a misspelling reads as a misspelling, not as an empty shelf."""
    domain = _DOMAINS.get(key)
    if domain is None:
        known = ", ".join(sorted(_DOMAINS)) or "none"
        raise ValueError(f"unknown trash domain {key!r} — known shelves: {known}")
    return domain


def list_domains() -> list[TrashDomain]:
    """Every shelf, in registration order (the order the tabs render in)."""
    return list(_DOMAINS.values())


#: REGISTRATION ORDER IS TAB ORDER — the agents shelf first, because the agent
#: lifecycle is what most often puts something here.
for _domain in (AgentsTrash(), RunsTrash(), ReportsTrash(), DbsTrash(), MiscTrash()):
    register_domain(_domain)
