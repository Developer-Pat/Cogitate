"""The activation path — probe, provision, and the decision.

Exa ships included and inactive; activation is the sequence that takes it to
answering (runtime on PATH → home provisioned → model set → keys present →
the user's flag). These tests defend the two things that make that sequence
trustworthy: the probe never guesses, and provisioning never carries a secret
it was not meant to carry.
"""

import pytest

from app.domain.external_agent import activation
from app.domain.external_agent.schemas import ExternalAgentConfig
from app.domain.external_agent.services import get_config, save_config


def _seed_skill(seed_dir):
    """A one-skill seed tree, shaped like skills/exa/<name>/."""
    home = seed_dir / "system-tasks"
    home.mkdir(parents=True)
    (home / "SKILL.md").write_text("---\nname: cogitate-system-tasks\n---\nbody\n", encoding="utf-8")
    (home / "references").mkdir()
    (home / "references" / "api.md").write_text("ref\n", encoding="utf-8")


def test_provision_creates_the_home_and_seeds_skills(tmp_path):
    home = tmp_path / ".hermes"
    seed = tmp_path / "seed"
    _seed_skill(seed)
    log = activation.provision_home(home=home, seed_dir=seed, project_env=tmp_path / "none.env")

    for sub in ("memories", "skills", "sessions", "cron", "hooks"):
        assert (home / sub).is_dir(), sub
    # the entry point AND its supporting file travel
    assert (home / "skills" / "cogitate" / "system-tasks" / "SKILL.md").exists()
    assert (home / "skills" / "cogitate" / "system-tasks" / "references" / "api.md").exists()
    assert any("skills seeded" in line for line in log)


def test_provision_carries_provider_keys_and_nothing_else(tmp_path):
    """A key name is not a provider key. The app's own credentials must never
    cross into the agent's home — the encryption key, nor a tracing SECRET."""
    home = tmp_path / ".hermes"
    env = tmp_path / "project.env"
    env.write_text(
        "# comment\nDEEPSEEK_API_KEY=sk-test\nEMPTY_KEY=\nCOGITATE_ENCRYPTION_KEY=app-secret\n"
        "LANGFUSE_PUBLIC_KEY=lf-public\nLANGFUSE_SECRET_KEY=lf-secret\n"
        "OPENROUTER_BASE_URL=https://example.invalid\n",
        encoding="utf-8",
    )
    log = activation.provision_home(
        home=home, seed_dir=tmp_path / "none", project_env=env
    )
    written = (home / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-test" in written
    assert "OPENROUTER_BASE_URL=" in written
    assert "COGITATE_ENCRYPTION_KEY" not in written
    assert "LANGFUSE_PUBLIC_KEY" not in written
    # THE MEASURED LEAK (2026-11-20): a SECRET-named tracing credential crossed,
    # because "SECRET" was in the carry markers. Both halves of the pair stay out.
    assert "LANGFUSE_SECRET_KEY" not in written
    # and the log names keys, never values
    assert any("DEEPSEEK_API_KEY" in line for line in log)
    assert all("sk-test" not in line for line in log)
    assert all("lf-secret" not in line for line in log)


def test_provisioning_merges_the_env_and_keeps_exas_own_lines(tmp_path):
    """Activation runs provisioning on every switch, and this file is Exa's own.

    THE MEASURED BUG (2026-11-20): provisioning wrote ONLY the carried lines, so a
    live activation emptied `AUXILIARY_VISION_MODEL` (written by the Model card) and
    any variable a user added. Carried names are replaced in place; everything else
    survives, and an older value for the same name is refreshed rather than doubled.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text(
        "# Exa's own store\n"
        "AUXILIARY_VISION_MODEL=deepseek-vision\n"
        "DEEPSEEK_API_KEY=stale\n"
        "MY_OWN_VAR=keep-me\n",
        encoding="utf-8",
    )
    env = tmp_path / "project.env"
    env.write_text("DEEPSEEK_API_KEY=sk-fresh\nOPENROUTER_API_KEY=or-fresh\n", encoding="utf-8")

    log = activation.provision_home(home=home, seed_dir=None, project_env=env)
    written = (home / ".env").read_text(encoding="utf-8")

    assert "AUXILIARY_VISION_MODEL=deepseek-vision" in written, "Exa's own line must survive"
    assert "MY_OWN_VAR=keep-me" in written
    assert "DEEPSEEK_API_KEY=sk-fresh" in written and "stale" not in written
    assert "OPENROUTER_API_KEY=or-fresh" in written, "a new key is appended"
    assert written.count("DEEPSEEK_API_KEY") == 1
    assert "# Exa's own store" in written
    assert any("DEEPSEEK_API_KEY" in line for line in log)


def test_provisioning_never_invents_a_model(tmp_path):
    """A fresh home has NO model — not its own, and not the operator's.

    Copying `~/.hermes/config.yaml` was the developer convenience; with
    provision-on-activate it fired on every fresh home on any box with Hermes
    installed, handing Exa a brain nobody chose. The model is a decision, so the
    log says so and the config is not written.
    """
    home = tmp_path / ".hermes"
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "config.yaml").write_text("model:\n  default: operator\n", encoding="utf-8")

    log = activation.provision_home(home=home, seed_dir=None, project_env=tmp_path / "none.env")

    assert not (home / "config.yaml").exists(), "a model must never be inherited"
    assert any("Exa's model is a decision" in line for line in log)


def test_provision_keeps_an_existing_config(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("model:\n  default: keep-me\n", encoding="utf-8")

    log = activation.provision_home(home=home, seed_dir=None, project_env=tmp_path / "none.env")
    assert "keep-me" in (home / "config.yaml").read_text(encoding="utf-8")
    assert any("kept" in line for line in log)


def test_model_section_round_trip(tmp_path):
    home = tmp_path / ".hermes"
    activation.write_model_config("deepseek/x", "deepseek", base_url=None, reasoning_effort="low", home=home)
    got = activation.read_model_config(home)
    assert got["model"] == "deepseek/x"
    assert got["provider"] == "deepseek"
    assert got["reasoning_effort"] == "low"

    activation.write_model_config("deepseek/x", "deepseek", base_url="https://a.invalid", home=home)
    assert activation.read_model_config(home)["base_url"] == "https://a.invalid"
    # a cleared address is a decision too — never leave the stale one behind
    activation.write_model_config("deepseek/x", "deepseek", clear_base_url=True, home=home)
    assert activation.read_model_config(home)["base_url"] is None


@pytest.mark.asyncio
async def test_probe_reports_every_missing_step(tmp_path, test_session):
    """A fresh box: the runtime may be there, but nothing else is. The probe
    says WHICH parts are missing, and writes nothing."""
    await save_config(test_session, ExternalAgentConfig(command="sh", enabled=False))
    report = await activation.probe(test_session, home=tmp_path / "empty")

    by_name = {c.name: c for c in report.checks}
    assert by_name["runtime"].ok is True
    assert by_name["home"].ok is False
    assert by_name["model"].ok is False
    assert by_name["keys"].ok is False
    assert by_name["decision"].ok is False
    assert report.ready is False
    assert not (tmp_path / "empty").exists(), "the probe must not create anything"


@pytest.mark.asyncio
async def test_apply_provisions_and_takes_the_decision(tmp_path, test_session):
    seed = tmp_path / "seed"
    _seed_skill(seed)
    env = tmp_path / "project.env"
    env.write_text("DEEPSEEK_API_KEY=sk-test\n", encoding="utf-8")
    home = tmp_path / ".hermes"

    report, log = await activation.apply(
        test_session,
        home=home,
        seed_dir=seed,
        project_env=env,
        model="deepseek/x",
        provider="deepseek",
    )

    assert (await get_config(test_session)).enabled is True
    assert report.ready is True, [c for c in report.missing]
    assert any("model set" in line for line in log)
    assert any("activated" in line for line in log)


@pytest.mark.asyncio
async def test_apply_never_takes_the_model_it_was_not_given(tmp_path, test_session, monkeypatch):
    """The offer is an OFFER. Activation provisions, flips and NAMES this install's
    chat model — the model itself is written only on `--from-default` (the accept)
    or with an explicit --model/--provider."""
    from app.domain.external_agent.activation import ChatOffer
    from app.domain.external_agent.services import get_config

    async def fake_offer(_db):
        return ChatOffer(provider="deepseek", model="deepseek-flash", base_url=None)

    monkeypatch.setattr(activation, "chat_offer", fake_offer)
    home = tmp_path / ".hermes"

    report, log = await activation.apply(
        test_session, home=home, seed_dir=tmp_path / "none", project_env=tmp_path / "none.env"
    )

    assert activation.read_model_config(home).get("model") is None, "no model may be invented"
    assert any("offers deepseek-flash" in line for line in log)
    assert report.offer is not None and report.offer.model == "deepseek-flash"
    assert (await get_config(test_session)).enabled is True


@pytest.mark.asyncio
async def test_probe_calls_out_a_missing_runtime(test_session):
    """The one fix a script cannot perform for you: installing the runtime."""
    await save_config(test_session, ExternalAgentConfig(command="definitely-not-installed acp"))
    report = await activation.probe(test_session, home=None)
    runtime = next(c for c in report.checks if c.name == "runtime")
    assert runtime.ok is False
    assert "definitely-not-installed" in runtime.detail
    assert activation.HERMES_INSTALL_COMMAND in runtime.fix
