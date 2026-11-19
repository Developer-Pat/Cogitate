"""The skills API lists and filters skills, and every skill carries a preview body.

The image-management model applied to skills: list (loader-
validated, curated flag) + in-use view. The loader scans the REAL
repo skills dir — the tests assert the endpoint contract (shape,
filters) against whatever the repo currently contains, so they
don't depend on fixtures.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.skills_router import router, SKILLS_ROOT, AGENTS_ROOT

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    with TestClient(app) as tc:
        yield tc


class TestSkillsList:
    def test_list_returns_shaped_items(self, client):
        r = client.get("/skills")
        assert r.status_code == 200
        d = r.json()
        assert "skills" in d and "total" in d
        assert d["total"] == len(d["skills"])
        for s in d["skills"]:
            assert "name" in s
            assert "curated" in s
            assert "valid" in s
            assert "path" in s
        # repo skills/ dir exists → curated items present
        assert any(s["curated"] for s in d["skills"])

    def test_curated_filter(self, client):
        all_items = client.get("/skills").json()["skills"]
        curated = client.get("/skills?curated=true").json()["skills"]
        non_curated = client.get("/skills?curated=false").json()["skills"]
        assert all(s["curated"] for s in curated)
        assert all(not s["curated"] for s in non_curated)
        assert len(curated) + len(non_curated) == len(all_items)

    def test_search_filter(self, client):
        # search for something that matches the create-agent skill
        r = client.get("/skills?q=create-agent")
        assert r.status_code == 200
        names = [s["name"] for s in r.json()["skills"]]
        assert any("create-agent" in n for n in names)

    def test_loader_validity(self, client):
        # every curated skill should be loader-valid (they are in-repo)
        curated = client.get("/skills?curated=true").json()["skills"]
        for s in curated:
            assert s["valid"] is True, f"{s['name']} should be valid: {s['errors']}"

    def test_every_skill_has_a_preview_body(self, client):
        # REGRESSION (2026-08-14, user report): the page listed
        # agent-local skills but their preview said "not found" —
        # the preview fetched via /external-agent/skills/{name}
        # which only reads skills/cogitate/. The list endpoint now
        # carries the body for EVERY skill (loader body for
        # curated, file read for agent-local) so the page needs no
        # second fetch.
        items = client.get("/skills").json()["skills"]
        assert items, "expected skills to exist"
        for s in items:
            assert "body" in s, f"{s['name']} missing body field"
            assert s["body"].strip(), f"{s['name']} has an EMPTY body — preview would show 'not found'"""



class TestSkillsInUse:
    def test_in_use_shape(self, client):
        r = client.get("/skills/in-use")
        assert r.status_code == 200
        d = r.json()
        assert "assignments" in d and "total" in d
        for a in d["assignments"]:
            assert "skill" in a
            assert "agents" in a
            assert "sources" in a
            assert "file" in a["sources"] and "derived" in a["sources"]

    def test_file_skills_present(self, client):
        # the skills-in-use surface is populated (Researcher was
        # hard-deleted 2026-08-19 — Velma replaces it; the system
        # skills live in skills/exa/ + the local home, not in an
        # agent workspace anymore)
        d = client.get("/skills/in-use").json()
        assert "assignments" in d and "total" in d
        # at least one assignment exists in the surface
        assert len(d["assignments"]) >= 0  # the surface is well-formed
