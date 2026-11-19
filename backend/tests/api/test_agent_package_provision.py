"""The agent-package provision action tests.

The flow: read the package -> the wizard answers (location
defaults to the spec) -> create the agent with the OWNED copies
(kit/skills/llm_spec) + package_id provenance + a model (the
explicit override wins, else the matcher) -> REPORT the outcome.
The HONEST 400 when the matcher finds nothing.
"""

import uuid

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Agent, Provider, CuratedModel


async def _get_or_create_provider(db, name: str) -> Provider:
    """The provider row for `name`, REUSED when the copied database already has it.

    The test database starts as a copy of a real one (`conftest`), so `openrouter`
    and `ollama` are usually already present — inserting them again raised a UNIQUE
    violation at fixture setup, which is how this file's tests errored instead of
    running. Reuse-or-create makes the fixture independent of what the copy holds.
    """
    existing = (
        await db.execute(select(Provider).where(Provider.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    provider = Provider(name=name, provider_type=name)
    db.add(provider)
    await db.flush()
    return provider


@pytest.fixture
async def provision_env(test_session):
    """Providers + models so the matcher has candidates.

    The providers are REUSED when they already exist: the test database starts as a
    copy of a real one (conftest), where `openrouter` and `ollama` are already rows —
    inserting them again raised a UNIQUE violation at fixture setup, which is how
    this file's tests ERRORED instead of running.
    """
    orp = await _get_or_create_provider(test_session, "openrouter")
    # `ollama` stays present: the window tests below hang their own local row off it.
    await _get_or_create_provider(test_session, "ollama")
    # THE LOCAL ROW LIVES ON `llama`, NOT `ollama` — deliberately. The provider that
    # serves a model has to be READ from the row that owns it, so a fixture whose only
    # local provider is itself named `ollama` cannot tell the lookup apart from the
    # retired location->name guess (`"openrouter" if location == "cloud" else
    # "ollama"`). Live data's local server is `llama`; this fixture matches that.
    llama = await _get_or_create_provider(test_session, "llama")
    test_session.add_all([
        CuratedModel(model_id="qwen/qwen3.8-max", model_name="Qwen3.8 Max", provider_id=orp.id, is_free=True, thinking="high", location="cloud", context_length=1048576),
        CuratedModel(model_id="llama3.2:latest", model_name="Llama 3.2", provider_id=llama.id, is_free=True, thinking="none", location="local", context_length=128000),
    ])
    await test_session.commit()
    return test_session


def pkg_body(thinking="none", location="local") -> dict:
    return {
        "name": f"provision-pkg-{uuid.uuid4().hex[:6]}",
        "description": "A provision test package.",
        "kit_id": None,
        "skills": ["greeting"],
        "llm_spec": {"kind": "chat", "thinking": thinking, "location": location, "min_context": None},
    }


@pytest.mark.anyio
async def test_provision_picks_a_model_from_the_matcher(client, provision_env):
    """No explicit model -> the matcher picks (the package's local
    spec finds llama3.2)."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"prov-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["package_id"] == pkg["id"]
    assert d["model"] == "llama3.2:latest"   # the matcher's pick (free local)
    assert d["location"] == "local"
    assert d["skills"] == ["greeting"]
    assert d["agent_id"] > 0

    # the agent's OWNED copies + provenance (the GET)
    gr = await client.get(f"/api/v1/agents/{d['agent_id']}")
    a = gr.json()
    assert a["package_id"] == pkg["id"]
    assert a["skills"] == ["greeting"]
    assert a["llm_spec"]["location"] == "local"
    # THE PROVIDER COMES FROM THE ROW THAT SERVES THE MODEL, not from the spec's
    # location. The fixture's local row is owned by `llama`, so the retired guess
    # (`"ollama"` for `location == "local"`) fails this line — that is what makes it
    # a discriminating assertion rather than a coincidence of naming.
    assert a["provider"] == "llama"


@pytest.mark.anyio
async def test_provision_override_takes_the_provider_from_the_serving_row(
    client, provision_env
):
    """B2a: an explicit model has no candidate list, so the row that SERVES it names
    the provider — the override path stops writing the location guess."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"prov-{uuid.uuid4().hex[:6]}", "model": "llama3.2:latest"},
    )
    assert r.status_code == 200, r.text
    a = (await client.get(f"/api/v1/agents/{r.json()['agent_id']}")).json()
    assert a["model"] == "llama3.2:latest"
    assert a["provider"] == "llama"           # the row's owner — not "ollama"


@pytest.mark.anyio
async def test_provision_override_refuses_a_model_no_row_serves(
    client, provision_env
):
    """A model no active curated row serves has NO provider: the adopter refuses
    (400) instead of pairing the model with a guessed provider."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    name = f"ghost-prov-{uuid.uuid4().hex[:6]}"
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": name, "model": "ghost/model-nobody-serves"},
    )
    assert r.status_code == 400
    assert "No provider in the registry serves" in r.json()["detail"]

    # nothing was created — the refusal lands BEFORE the agent row
    created = (
        await provision_env.execute(select(Agent).where(Agent.name == name))
    ).scalars().all()
    assert created == []


@pytest.mark.anyio
async def test_provision_explicit_model_wins(client, provision_env):
    """The explicit model override beats the matcher."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body())).json()
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"prov-{uuid.uuid4().hex[:6]}", "model": "qwen/qwen3.8-max"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "qwen/qwen3.8-max"


@pytest.mark.anyio
async def test_provision_wizard_location_override(client, provision_env):
    """The wizard's location answer overrides the package's default.

    The pick is asserted as A CLOUD ROW rather than as one named model. The test database is a copy
    of a real installation, so the matcher's cloud candidate list is whatever that installation
    holds — twelve rows since the cloud-providers arc — and `candidates[0]` is therefore not the
    fixture's `qwen/qwen3.8-max`. Asserting the name made this test fail for a reason that has
    nothing to do with the wizard's answer. What it is about is the LOCATION answer, so it asserts
    that, plus the consistency this arc's phase 4 introduced: the agent's provider is the owner of
    the row that serves the chosen model.
    """
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body(location="local"))).json()
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"prov-{uuid.uuid4().hex[:6]}", "location": "cloud"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["location"] == "cloud"

    served = {
        model_id: provider
        for model_id, provider in (
            await provision_env.execute(
                select(CuratedModel.model_id, Provider.name)
                .join(Provider, CuratedModel.provider_id == Provider.id)
                .where(
                    CuratedModel.location == "cloud",
                    CuratedModel.is_active.is_(True),
                )
            )
        ).all()
    }
    assert d["model"] in served, f"{d['model']} is not a cloud row the matcher could have picked"
    a = (await client.get(f"/api/v1/agents/{d['agent_id']}")).json()
    assert a["provider"] == served[d["model"]]     # the row's owner, not a location guess


@pytest.mark.anyio
async def test_provision_honest_400_when_no_candidates(client, provision_env):
    """A high/local spec matches NOTHING -> the honest 400 (no fake
    model pick)."""
    pkg = (await client.post("/api/v1/agent-packages", json=pkg_body(thinking="high", location="local"))).json()
    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"prov-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 400
    assert "No model" in r.json()["detail"]


@pytest.mark.anyio
async def test_provisioning_onto_a_too_small_driver_WARNS_and_still_creates(
    client, provision_env, caplog
):
    """D9: a window too small for the agent's need is ALLOWED — and reported.

    The package declares a prompt floor (4096) and an output budget (8192), so it
    needs 12288 tokens; the chosen driver holds 8192. The agent is created anyway
    (the runtime clamps the budget to fit) and the response carries the sentence.
    """
    import logging

    from app.infrastructure.database.models import CuratedModel

    oll = (await provision_env.execute(
        select(Provider).where(Provider.name == "ollama")
    )).scalar_one()
    provision_env.add(CuratedModel(
        model_id="tiny:latest", model_name="Tiny", provider_id=oll.id,
        is_free=True, thinking="none", location="local", context_length=8192,
    ))
    await provision_env.commit()

    pkg = (await client.post("/api/v1/agent-packages", json={
        "name": f"tiny-pkg-{uuid.uuid4().hex[:6]}",
        "description": "A long-form asker on a small driver.",
        "kit_id": None,
        "skills": ["greeting"],
        "llm_spec": {
            "kind": "chat", "thinking": "none", "location": "local",
            "min_context": 4096, "max_output": 8192,
        },
    })).json()

    with caplog.at_level(logging.WARNING, logger="app.api.v1.agent_packages.router"):
        r = await client.post(
            f"/api/v1/agent-packages/{pkg['id']}/provision",
            json={"name": f"tiny-prov-{uuid.uuid4().hex[:6]}", "model": "tiny:latest"},
        )

    assert r.status_code == 200, r.text
    d = r.json()
    assert d["model"] == "tiny:latest"
    assert d["agent_id"] > 0                     # created: a small window is not a refusal
    assert d["window_note"] is not None
    assert "8192" in d["window_note"] and "12288" in d["window_note"]
    assert "window_clamp" in d["window_note"]    # what the runtime will do about it
    assert "WINDOW FIT" in caplog.text


@pytest.mark.anyio
async def test_a_driver_that_fits_has_nothing_to_say(client, provision_env):
    """No note when there is nothing wrong — the field is not decoration."""
    pkg = (await client.post("/api/v1/agent-packages", json={
        "name": f"fit-pkg-{uuid.uuid4().hex[:6]}",
        "description": "Fits comfortably.",
        "kit_id": None,
        "skills": ["greeting"],
        "llm_spec": {
            "kind": "chat", "thinking": "none", "location": "local",
            "min_context": 4096, "max_output": 8192,
        },
    })).json()

    r = await client.post(
        f"/api/v1/agent-packages/{pkg['id']}/provision",
        json={"name": f"fit-prov-{uuid.uuid4().hex[:6]}", "model": "llama3.2:latest"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["window_note"] is None       # 128000 holds 12288


@pytest.mark.anyio
async def test_provision_unknown_package_404(client):
    r = await client.post(
        "/api/v1/agent-packages/does-not-exist/provision",
        json={"name": "nope"},
    )
    assert r.status_code == 404
