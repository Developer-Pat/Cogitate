"""The app's page map — generated, never hand-kept.

`open-page` offers a model a closed set of destinations. That set has to BE the
app's real pages, or the model gets offered a page that no longer exists and the
jump 404s. So the list is generated from `frontend/src/config/routes.ts` (the
single source of truth the frontend's own map derives from) by
`scripts/core/gen_page_map.py`, and a test asserts the two never disagree.

Three kinds of destination, because the app has three:

  route   a path from routes.ts                `/settings`
  alias   a surface that is NOT a route        `/settings?tab=appearance`
          (the Settings tabs are useState, so they cannot be derived)
  tab     an app that opens as its own tab     `exa` / `messages` / ...

THE FRONTEND IS STILL THE NAVIGATOR. This module only produces a VERIFIED
PATH. Which tab a destination opens in is the frontend's convention
(`appNavigation.openTarget`), not something the backend decides.

THE APP'S OWN OTHER NAMES FOR A SURFACE RESOLVE TOO. The nav table records, per
alias/tab, the words the app answers to (`match: ["logging"]` for `/logs`). Those
used to be carried in the generated mirror and read by nobody, so `nav logging`
worked while a model naming the same surface in prose got a loud miss. They are
now the resolver's synonym step — one vocabulary for the human who types the
word and the model that echoes it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_MAP_PATH = Path(__file__).resolve().parent / "page_map.json"


@dataclass(frozen=True)
class PageEntry:
    """One destination the app can open."""

    kind: str  # 'route' | 'alias' | 'tab'
    key: str  # what the model passes as `page`
    label: str  # the human name to show the user
    description: str = ""
    matches: Tuple[str, ...] = ()  # the app's OTHER names for it (`nav logging`)

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "kind": self.kind,
            "key": self.key,
            "label": self.label,
            "description": self.description,
        }
        if self.matches:
            # Worth telling a model that MISSED: the surface it was reaching for
            # may have been one of these words.
            out["also_called"] = list(self.matches)
        return out


class PageMapMissing(RuntimeError):
    """The generated map is absent — the generator was never run."""


@lru_cache(maxsize=1)
def _raw() -> Dict[str, Any]:
    if not _MAP_PATH.exists():
        raise PageMapMissing(
            f"{_MAP_PATH.name} is missing — run "
            f"`python3 scripts/core/gen_page_map.py` to generate it"
        )
    loaded: Dict[str, Any] = json.loads(_MAP_PATH.read_text())
    return loaded


def page_entries() -> List[PageEntry]:
    """Every openable destination, routes first then aliases then tabs."""
    raw = _raw()
    out: List[PageEntry] = []
    for p in raw.get("pages", []):
        out.append(
            PageEntry(kind="route", key=p["path"], label=p.get("title") or p["path"],
                      description=p.get("description", ""))
        )
    for a in raw.get("aliases", []):
        out.append(
            PageEntry(kind="alias", key=a["to"], label=a.get("label") or a["to"],
                      matches=tuple(a.get("match") or ()))
        )
    for t in raw.get("tabs", []):
        out.append(
            PageEntry(kind="tab", key=t["app"], label=t.get("label") or t["app"],
                      matches=tuple(t.get("match") or ()))
        )
    return out


def _unique_keys(entries: List[PageEntry]) -> List[PageEntry]:
    """Drop later entries that repeat an earlier destination, order preserved.

    An alias points AT a route (its key IS the route's path), so it would
    otherwise appear twice: once as the destination and once as the synonym
    that reaches it. Both surfaces below are a CLOSED SET — the enum the model
    must choose from, and the map it is taught — and a set does not contain a
    thing twice. The alias still RESOLVES (resolve_page walks the full entry
    list); it just does not get a second slot in the list of destinations.
    """
    seen: set[str] = set()
    out: List[PageEntry] = []
    for e in entries:
        if e.key in seen:
            continue
        seen.add(e.key)
        out.append(e)
    return out


def page_keys() -> List[str]:
    """The closed set offered to the model — the tool's enum."""
    return [e.key for e in _unique_keys(page_entries())]


def page_prompt() -> str:
    """The map as text: what the app teaches the model about where things are."""
    lines = [f"- {e.key} — {e.label}" for e in _unique_keys(page_entries())]
    return "\n".join(lines)


def resolve_page(raw: str) -> Tuple[Optional[PageEntry], List[PageEntry]]:
    """Resolve a requested page to a real destination, LOUDLY.

    Returns ``(entry, candidates)``. The entry is None when nothing matched, and
    the candidates are the nearest labels so the caller can say "did you mean".
    **Never guesses**: opening a wrong-but-plausible page is worse than saying
    "I do not know that one".
    """
    wanted = (raw or "").strip().lower()
    if not wanted:
        return None, []

    entries = page_entries()

    # 1. an exact key — the common case, since the enum hands out the keys
    for e in entries:
        if e.key.lower() == wanted:
            return e, []

    # 2. an exact label (a user or model naming the surface instead of the path)
    for e in entries:
        if e.label.lower() == wanted:
            return e, []

    # 3. a path-ish match: tolerate a missing/stray trailing slash
    trimmed = wanted.rstrip("/") or "/"
    for e in entries:
        if e.key.lower().rstrip("/") == trimmed:
            return e, []

    # 4. a SYNONYM — the app's own other name for the surface, as the nav table
    # spells it (`logging` for /logs, `themes` for the Settings appearance tab).
    # The user-typed channel has always spoken these; this is the same vocabulary
    # reaching a model that names the surface in prose instead of using the key it
    # was handed. EXACT only: a near-miss must still fall through to the loud miss.
    for e in entries:
        if any(m.strip().lower() == wanted for m in e.matches):
            return e, []

    # 5. nothing exact — offer the nearest labels rather than a guess
    words = [w for w in wanted.replace("/", " ").replace("-", " ").split() if len(w) > 2]
    scored = []
    for e in entries:
        blob = f"{e.key} {e.label}".lower()
        score = sum(1 for w in words if w in blob)
        if e.label.lower() in wanted or wanted in e.label.lower():
            score += 3
        if score:
            scored.append((score, e))
    scored.sort(key=lambda s: -s[0])
    return None, [e for _, e in scored[:5]]
