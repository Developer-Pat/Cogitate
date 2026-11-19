"""The wiki search endpoint — the lookup the ask-Exa verbs ride.

`nav` is pure client-side (the routes live there); `info`, `dev` and
`atlas` need the wiki's search, and the last two are namespace-scoped:
"dev architecture" means a note under dev-notes/, so the scope filter has
to apply BEFORE ranking — otherwise ten global hits can crowd the
namespace out and the verb reports "nothing found" while the note exists.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def test_search_returns_ranked_hits(client):
    r = client.get("/api/v1/wiki/search", params={"q": "atlas"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "atlas"
    assert body["count"] >= 1
    for hit in body["results"]:
        assert set(hit) >= {"path", "title", "score", "snippet"}
        # the path is wiki-relative and extension-less: /wiki/<path> is the URL
        assert not hit["path"].endswith(".md")
        assert not hit["path"].startswith("/")


def test_empty_query_is_not_an_error(client):
    r = client.get("/api/v1/wiki/search", params={"q": "   "})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_prefix_scopes_the_search(client):
    """The dev-notes namespace holds notes the global top-10 can crowd out."""
    loose = client.get("/api/v1/wiki/search", params={"q": "architecture", "prefix": ""}).json()
    scoped = client.get(
        "/api/v1/wiki/search", params={"q": "architecture", "prefix": "dev-notes"}
    ).json()
    assert all(h["path"].startswith("dev-notes/") for h in scoped["results"]), scoped["results"]
    # scoping must not turn a real namespace hit into nothing
    assert scoped["count"] >= 1
    # and the loose search is not already dominated by that namespace
    assert len(loose["results"]) >= len(scoped["results"])


def test_prefix_tolerates_surrounding_slashes(client):
    a = client.get("/api/v1/wiki/search", params={"q": "atlas", "prefix": "/atlas/"}).json()
    b = client.get("/api/v1/wiki/search", params={"q": "atlas", "prefix": "atlas"}).json()
    assert [h["path"] for h in a["results"]] == [h["path"] for h in b["results"]]
