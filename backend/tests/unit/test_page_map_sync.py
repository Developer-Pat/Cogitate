"""The page map and the frontend route table must never disagree.

WHY THIS TEST EXISTS
--------------------
`open-page` offers a model a closed set of destinations. If that set drifts from
the app's real pages, the model is offered a page that no longer exists and the
jump 404s — a silent failure with a plausible cause. So the set is generated
(`scripts/core/gen_page_map.py`) and this test fails the moment the committed map
stops matching `frontend/src/config/routes.ts`.

THE POINT IS THE FAILURE, NOT THE PASS. A page added to routes.ts without
regenerating makes this test RED, which is the only signal that would ever be
produced. Same discipline as the capability-taxonomy test that caught the bogus
`system-admin`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# The repo root comes from the Paths locator, never from a __file__ crawl —
# re-deriving it by hand is the phantom-path class the sweep's
# path-arithmetic gate exists to stop.
sys.path.insert(0, "backend")
from app.core.config import Paths  # noqa: E402

REPO_ROOT = Path(str(Paths.root))
GENERATOR = REPO_ROOT / "scripts/core/gen_page_map.py"
PAGE_MAP_JSON = REPO_ROOT / "backend/app/domain/tools/page_map.json"
ROUTES_TS = REPO_ROOT / "frontend/src/config/routes.ts"
NAV_TS = REPO_ROOT / "frontend/src/services/appNavigation.ts"


def test_the_generated_map_is_committed():
    """The artifact the tool reads at import must exist."""
    assert PAGE_MAP_JSON.exists(), (
        "page_map.json is missing — run `python3 scripts/core/gen_page_map.py`"
    )


def test_the_map_is_in_sync_with_the_route_table():
    """THE GATE: regenerate and compare, byte for byte.

    Runs the real generator rather than re-implementing its parse, so this test
    cannot itself drift from the thing it is checking.
    """
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, (
        "The page map is STALE — a route changed without regenerating the tool's enum.\n"
        f"  run: python3 scripts/core/gen_page_map.py\n"
        f"  {proc.stdout.strip()}\n  {proc.stderr.strip()}"
    )


def test_the_generator_fails_loudly_when_it_cannot_parse(monkeypatch, tmp_path):
    """A parser that quietly returns FEWER entries is the worst outcome.

    If routes.ts changes shape, the generator must raise rather than emit a
    shorter map — otherwise the model silently loses destinations.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts/core"))
    import gen_page_map  # type: ignore[import-not-found]

    good = ROUTES_TS.read_text()
    # Rename EVERY `path:` key — the table no longer looks like a route table.
    broken = good.replace("path:", "routePath:")
    assert broken != good and "routePath:" in broken
    monkeypatch.setattr(gen_page_map, "ROUTES_TS", tmp_path / "routes.ts")
    (tmp_path / "routes.ts").write_text(broken)

    with pytest.raises(gen_page_map.ParseError):
        gen_page_map.build_map()


def test_a_partial_parse_is_rejected(monkeypatch, tmp_path):
    """Half the table understood is as dangerous as none of it.

    One object the raw counter sees but the parser misses must make the count
    comparison fire, so the map can never quietly shrink by a page.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts/core"))
    import gen_page_map  # type: ignore[import-not-found]

    good = ROUTES_TS.read_text()
    lines = good.splitlines(keepends=True)
    seen = 0
    for i, ln in enumerate(lines):
        if ln.startswith("    path:"):
            seen += 1
            if seen == 2:
                # the raw counter matches exactly 4 spaces; the object parser
                # does not, so the two disagree by one
                lines[i] = "  " + ln
                break
    monkeypatch.setattr(gen_page_map, "ROUTES_TS", tmp_path / "routes.ts")
    (tmp_path / "routes.ts").write_text("".join(lines))

    with pytest.raises(gen_page_map.ParseError):
        gen_page_map.build_map()


def test_every_page_entry_has_a_key_and_a_label():
    """The model is handed key + label; an empty one is a useless destination."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.domain.tools.page_map import page_entries

    entries = page_entries()
    assert entries, "the page map produced no entries at all"
    for e in entries:
        assert e.key.strip(), f"an entry has no key: {e}"
        assert e.label.strip(), f"an entry has no label: {e}"
        assert e.kind in ("route", "alias", "tab"), f"unknown kind: {e.kind}"


def test_the_enum_has_no_duplicates():
    """Two entries sharing a key would make the model's choice ambiguous."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.domain.tools.page_map import page_keys

    keys = page_keys()
    assert len(keys) == len(set(keys)), (
        "duplicate page keys: "
        + ", ".join(sorted({k for k in keys if keys.count(k) > 1}))
    )


def test_resolve_page_is_loud_not_guessing():
    """An unknown page returns candidates and NO target — never a plausible guess."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.domain.tools.page_map import resolve_page

    entry, candidates = resolve_page("/settings")
    assert entry is not None and entry.key == "/settings"

    # an alias resolves to its query-string destination
    entry, _ = resolve_page("/settings?tab=appearance")
    assert entry is not None and entry.kind == "alias"

    # a tab app resolves by name
    entry, _ = resolve_page("messages")
    assert entry is not None and entry.kind == "tab"

    # nonsense does NOT resolve, and says what it does know
    entry, candidates = resolve_page("/definitely-not-a-page")
    assert entry is None, "an unknown page must not resolve to anything"
    assert isinstance(candidates, list)


def test_a_synonym_resolves_to_the_surface_that_declares_it():
    """The nav table's `match` words reach the backend resolver too.

    They are the names the APP answers to (`nav logging`), so a model echoing the
    user's phrasing now lands where the user would. Before this, those words rode
    in the generated mirror with no reader at all: `nav logging` worked in the
    command box while `open-page("logging")` was a loud miss.
    """
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.domain.tools.page_map import resolve_page

    entry, candidates = resolve_page("logging")  # an alias: /logs
    assert entry is not None, f"a declared synonym must resolve (candidates: {candidates})"
    assert entry.key == "/logs"

    entry, _ = resolve_page("themes")  # an alias: the Settings appearance tab
    assert entry is not None and entry.key == "/settings?tab=appearance"

    entry, _ = resolve_page("session list")  # a tab app's other name
    assert entry is not None and entry.key == "sessions"

    # The matching is EXACT: a typo is not a synonym and still gets the loud miss.
    entry, _ = resolve_page("loggingg")
    assert entry is None, "a near-miss must not be accepted as a synonym"


def test_every_synonym_in_the_generated_map_resolves():
    """The completeness lock — no `match` word in the mirror is dead.

    This is the defect that started it (generated, carried, read by nobody). Every
    word an alias or tab declares must land somewhere, and on the key of the block
    that declares it, or the map tells two stories again.
    """
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.domain.tools.page_map import resolve_page

    # Two declared words are ALSO the exact label of another entry — `message
    # center` is the `/messages` route's title and `agent chat` is
    # `/agent-interaction`'s. An exact label legitimately outranks a nickname, so
    # these two resolve there, and the assertion below checks the REASON rather
    # than excusing them by name alone.
    outranked_by_label = {"message center", "agent chat"}

    data = json.loads(PAGE_MAP_JSON.read_text())
    checked = 0
    for table, key_name in (("aliases", "to"), ("tabs", "app")):
        for block in data[table]:
            for word in block.get("match") or []:
                entry, _ = resolve_page(word)
                assert entry is not None, (
                    f"{word!r} (declared by {block[key_name]!r}) resolves to nothing"
                )
                if word in outranked_by_label:
                    assert entry.label.lower() == word, (
                        f"{word!r} is expected to be outranked only by an exact label"
                    )
                else:
                    assert entry.key == block[key_name], (
                        f"{word!r} resolves to {entry.key!r}, "
                        f"not {block[key_name]!r}"
                    )
                checked += 1

    # A floor, so a broken `match` scrape cannot make this test vacuous — the same
    # guard the generator carries against emitting an empty map.
    assert checked >= 30, f"only {checked} synonyms found — the match scrape likely broke"


def test_the_map_counts_match_the_sources():
    """A sanity floor: the app has many pages, so a tiny map means a broken parse."""
    data = json.loads(PAGE_MAP_JSON.read_text())
    assert data["counts"]["routes"] >= 30, (
        f"only {data['counts']['routes']} routes — the parser likely broke"
    )
    assert data["counts"]["aliases"] >= 1, "the declared alias table went missing"
    assert data["counts"]["tabs"] >= 1, "the tab-app vocabulary went missing"
    assert ROUTES_TS.exists() and NAV_TS.exists()
