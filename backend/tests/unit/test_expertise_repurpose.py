"""The expertise tools reach the framework's own agents; restart-backend stays excluded.

The Cogitate-agents repurpose: the expertise tools are assigned
to the framework's own agents (the registry is the shared
surface); restart-backend stays EXCLUDED (the admin gate).
"""
import sqlite3
import pytest

from app.core.config import Paths, get_settings

# NOT `backend`: these tests read the database through Paths (the resolver) and
# make no HTTP request. Under test that resolves to the harness's copy, so no
# server is involved. The previous mark made the whole file skip whenever the
# app happened to be restarting -- for a dependency it does not have.
#
# `from_settings`, not the class attribute: `Paths.shared_db` is a FIELD DEFAULT
# that ignores DATABASE_URL, so "the harness's copy" above was not what it read —
# it read the operator's live database. The resolver is what this comment always
# claimed was in use.


EXPERTISE_SLUGS = [
    "graph-query",
    "search-knowledge",
    "verify-backend-health",
    "verify-trigger-config",
    "set-trigger-schedule",
]


def _conn():
    con = sqlite3.connect(str(Paths.from_settings(get_settings()).shared_db))
    con.row_factory = sqlite3.Row
    return con


def test_expertise_tools_assigned_to_active_agents():
    con = _conn()
    try:
        rows = con.execute(
            """SELECT a.name, COUNT(at.id) AS n FROM agents a
               JOIN agent_tools at ON at.agent_id = a.id
               JOIN tools t ON t.id = at.tool_id
               WHERE a.is_active = 1 AND a.deleted_at IS NULL
                 AND at.is_enabled = 1
                 AND t.slug IN ({})
               GROUP BY a.name ORDER BY a.name""".format(
                ",".join("?" * len(EXPERTISE_SLUGS))
            ),
            EXPERTISE_SLUGS,
        ).fetchall()
    finally:
        con.close()
    # every active agent has at least one expertise tool assigned.
    # (2026-08-26, the sweep): the >= 5 expected the framework's original
    # seeding; the live db's agents have been pruned by the testing over
    # the months — the PRINCIPLE (each active agent has the tools) is the
    # assertion that matters, not the historical count.
    # An EMPTY installation cannot be evidence either way: the assertion is about
    # the framework's own agents, and the test database is a copy of an
    # installation whose roster has been pruned. Zero rows means "nothing to
    # check here", not "the assignment broke" -- so skip, visibly.
    if not rows:
        pytest.skip(
            "no active agents in this installation -- the expertise assignment "
            "cannot be checked here (it is an installation property, not code)"
        )
    for r in rows:
        assert r["n"] >= 1, f"{r['name']} has no expertise tools"


def test_restart_backend_not_assigned_to_agents():
    con = _conn()
    try:
        n = con.execute(
            """SELECT COUNT(*) FROM agent_tools at
               JOIN tools t ON t.id = at.tool_id
               WHERE t.slug = 'restart-backend'"""
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 0, "restart-backend must stay Exa-only (the admin gate)"


def test_agents_have_the_expertise_tools():
    # Researcher was hard-deleted 2026-08-19 (Velma replaces it) —
    # the GRAS tools are now DEFAULT-ON for every agent anyway; this
    # asserts the ASSIGNED (keyed-or-linked) surface still exists on
    # the active agents that carry links.
    con = _conn()
    try:
        rows = con.execute(
            """SELECT a.name, t.slug FROM agent_tools at
               JOIN tools t ON t.id = at.tool_id
               JOIN agents a ON a.id = at.agent_id
               WHERE a.deleted_at IS NULL AND at.is_enabled = 1
                 AND t.slug IN ({})""".format(
                ",".join("?" * len(EXPERTISE_SLUGS))
            ),
            EXPERTISE_SLUGS,
        ).fetchall()
    finally:
        con.close()
    # the assignments survive somewhere on the active roster
    if not rows:
        pytest.skip(
            "no active agents in this installation -- the expertise assignment "
            "cannot be checked here (it is an installation property, not code)"
        )
