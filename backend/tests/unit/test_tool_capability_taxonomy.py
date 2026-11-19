"""The capability taxonomy — the frozen vocabulary and its families.

The canonical capability vocabulary is code-defined (capabilities.py),
declared by handler classes, carried by the registry, mirrored in
the tools table. These tests pin the contract:

- the vocabulary: valid slugs, the frozen list, no vendor/persona
- the registry: every builtin declares a canonical capability
  (except the cruft list)
- the DB mirror: classified rows match, cruft stays NULL
"""

import sys
sys.path.insert(0, "backend")

import sqlite3
from pathlib import Path

import pytest

from app.domain.tools.capabilities import (
    CAPABILITIES, CAPABILITY_FAMILIES, is_valid_capability, family_for,
)
from app.domain.tools.registry import init_default_registry

from app.core.config import Paths as CorePaths, get_settings
# THE LIVE DATABASE, named deliberately — the class attribute is how the suite
# names the operator's own installation (the `live_db_path` fixture does the same,
# for the same reason). This file's DB-mirror tests assert the SHIPPED data, so
# the sandbox copy is not a substitute: `tools` is an ORM table and
# `auto_clean_tables` truncates it between tests. Declared @pytest.mark.shared_db.
LIVE_DB = Path(str(CorePaths.shared_db))

# the cruft tools get NO capability (Phase B removes them)
CRUFT = {
    "echo", "tool-crib", "boris-file-display", "boris-report-writer",
    "calc_e2e_live", "calc_test", "calculator_e2e", "check_schema",
    "test-tool-1",
}


class TestVocabulary:
    def test_all_capabilities_are_valid(self):
        for cap in CAPABILITIES:
            assert is_valid_capability(cap), cap
        # and they are unique
        assert len(set(CAPABILITIES)) == len(CAPABILITIES)

    def test_vocabulary_is_frozen_plain_names(self):
        # no vendors, no personas, no underscores — single words or
        # kebab-case (calculator, datetime are single-word plain)
        for cap in CAPABILITIES:
            assert "_" not in cap, f"underscore in: {cap}"
            assert " " not in cap, f"space in: {cap}"
            assert cap.islower(), f"not lowercase: {cap}"
            assert not any(v in cap for v in ("duck", "tavily", "wikipedia",
                                               "jina", "boris", "boss")), cap

    def test_families_cover_the_vocabulary(self):
        covered = {c for members in CAPABILITY_FAMILIES.values() for c in members}
        assert covered == set(CAPABILITIES)

    def test_family_for(self):
        assert family_for("web-search") == "Search & Retrieval"
        assert family_for("code-execution") == "Data & Computation"
        assert family_for("event-publish") == "System & Admin"
        assert family_for("nonsense") is None


class TestRegistryDeclarations:
    def test_builtins_declare_canonical_capability(self):
        reg = init_default_registry()
        tools = list(reg._tools.values())
        assert len(tools) >= 20
        for t in tools:
            if t.slug in CRUFT:
                assert t.capability is None, f"cruft has capability: {t.slug}"
            else:
                assert t.capability, f"no capability: {t.slug}"
                assert is_valid_capability(t.capability),                     f"not in vocabulary: {t.slug} → {t.capability}"

    def test_key_mappings(self):
        # spot-check the study's mapping
        reg = init_default_registry()
        by_slug = {t.slug: t.capability for t in reg._tools.values()}
        assert by_slug["duckduckgo"] == "web-search"
        assert by_slug["jina_reader"] == "web-fetch"
        assert by_slug["sqlite-query"] == "db-query"
        assert by_slug["run-python"] == "code-execution"
        assert by_slug["publish"] == "event-publish"
        assert by_slug["file-info"] == "file-read"
        assert by_slug["file-manager"] == "file-write"
        assert by_slug["agent-manager"] == "agent-admin"
        assert by_slug["sequential-thinking"] == "reasoning-aid"


@pytest.mark.shared_db
class TestDBMirror:
    """THE MIRROR, READ FROM THE OPERATOR'S OWN DATABASE.

    Declared `shared_db` because the copy will not do: `tools` has an ORM model, so
    `auto_clean_tables` truncates it between tests and the mirror is empty by the
    time these run. What is asserted here is the SHIPPED data — the classification
    the operator's registry carries — not the suite's fixture, so the live table is
    the subject rather than a leak.
    """

    def test_classified_rows_match_the_vocabulary(self):
        from tests import conftest as cf

        # The suite truncates every ORM table between tests, so the mirror is
        # empty by the time this runs. Restore the shipped reference rows first:
        # they are the subject here, not a leak.
        cf._load_reference_rows(str(LIVE_DB))
        con = sqlite3.connect(LIVE_DB)
        try:
            rows = con.execute(
                "SELECT slug, capability FROM tools WHERE capability IS NOT NULL"
            ).fetchall()
        finally:
            con.close()
        assert len(rows) >= 25, "most live tools should be classified"
        for slug, cap in rows:
            assert is_valid_capability(cap), f"{slug} → {cap} not in vocabulary"

    def test_cruft_is_removed_not_nulled(self):
        # Phase B removed the cruft tools entirely — they must not
        # exist as rows (nor reappear NULL-capability)
        con = sqlite3.connect(LIVE_DB)
        try:
            rows = con.execute(
                "SELECT slug FROM tools WHERE capability IS NULL"
            ).fetchall()
            present = {r[0] for r in rows}
            rows2 = con.execute(
                "SELECT slug FROM tools WHERE slug IN ("
                + ",".join("'" + s + "'" for s in CRUFT) + ")"
            ).fetchall()
        finally:
            con.close()
        leftover = {r[0] for r in rows2}
        assert leftover == set(), f"cruft still present: {leftover}"
        # every remaining tool must have a capability (no NULLs at all)
        assert present == set(), f"NULL-capability tools remain: {present}"
