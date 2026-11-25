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
async def test_apply_provisions_and_takes_the_decision(tmp_path, test_session, monkeypatch):
    """Provisioning and the decision — not the box it runs on.

    The runtime probe has its own subject (`test_probe_reports_every_missing_step`,
    which uses `sh`), and the ladder's is covered by the probe tests. Left un-stubbed,
    this test asks whether the MACHINE has `hermes` on PATH: true on a developer's box,
    false on every CI runner, where it read as a broken build until someone downloaded
    the runner's artifact.
    """
    monkeypatch.setattr(activation, "probe_runnable", lambda cfg: None)
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


# ─────────────────────────────────────────────────────────────────────────────
# TWO FACTS, NOT ONE: "a model is set" vs "that model can answer" (2026-11-22)
# ─────────────────────────────────────────────────────────────────────────────

def _home_with_model(tmp_path, model="anthropic/claude-opus-4.6", provider="anthropic",
                     base_url=None, env_lines=""):
    home = tmp_path / ".hermes"
    home.mkdir()
    yaml = f"model:\n  default: {model}\n  provider: {provider}\n"
    if base_url:
        yaml += f"  base_url: {base_url}\n"
    (home / "config.yaml").write_text(yaml, encoding="utf-8")
    (home / ".env").write_text(env_lines, encoding="utf-8")
    return home


def test_a_model_without_its_key_is_reported_unusable(tmp_path):
    """A model with no credential is not a satisfied step.

    It used to pass (`ok` was about the SECTION existing, and Exa may deliberately run on another
    model); measured on the 0.1.2 walk, that let a home with a model and no key read every step
    green while the runtime could not make one call.
    """
    home = _home_with_model(tmp_path, env_lines="ANTHROPIC_API_KEY=\n")
    check = activation._check_model(home)
    assert check.ok is False
    assert "usable: no" in check.detail
    assert "ANTHROPIC_API_KEY" in check.detail
    assert "Setup → API Keys" in check.fix


def test_a_model_with_its_key_is_reported_usable(tmp_path):
    home = _home_with_model(tmp_path, env_lines="ANTHROPIC_API_KEY=sk-test\n")
    check = activation._check_model(home)
    assert check.ok is True
    assert "usable: yes" in check.detail


def test_a_local_endpoint_needs_no_key_to_be_usable(tmp_path):
    """A loopback model is usable without any credential — do not report it as blocked."""
    home = _home_with_model(
        tmp_path, model="qwen", provider="llama", base_url="http://127.0.0.1:8080/v1"
    )
    check = activation._check_model(home)
    assert "usable: yes" in check.detail


def test_the_missing_runtime_message_names_the_path_it_searched(monkeypatch):
    """"not on PATH" is true and unactionable; the backend's PATH is not the user's shell."""
    from app.domain.external_agent.services import probe_runnable

    monkeypatch.setenv("PATH", "/nowhere/bin:/second/bin")
    why = probe_runnable(ExternalAgentConfig(command="hermes acp"))
    assert why is not None
    assert "/nowhere/bin" in why and "/second/bin" in why
    assert "cogitate.sh start" in why

# ─────────────────────────────────────────────────────────────────────────────
# THE PRE-TURN GUARD — a turn that cannot answer says so BEFORE it starts
# ─────────────────────────────────────────────────────────────────────────────

def test_the_guard_refuses_a_home_with_no_model(tmp_path):
    """Six silent minutes were the alternative (measured on a fresh install, 2026-11-22)."""
    home = tmp_path / ".hermes"
    home.mkdir()
    why = activation.pre_turn_refusal(
        ExternalAgentConfig(command="python3 acp"), home=home
    )
    assert why is not None
    assert "no model configured" in why


def test_the_guard_refuses_a_model_without_its_key(tmp_path):
    home = _home_with_model(tmp_path, env_lines="ANTHROPIC_API_KEY=\n")
    why = activation.pre_turn_refusal(
        ExternalAgentConfig(command="python3 acp"), home=home
    )
    assert why is not None
    assert "ANTHROPIC_API_KEY" in why
    assert "Setup → API Keys" in why, (
        "the refusal names the door that writes the .env provisioning copies from — the Exa "
        "pages have no Keys tab, and the sentence used to send the reader to one"
    )


def test_the_guard_passes_a_local_model_with_no_key(tmp_path):
    """A loopback model needs no credential, so the guard must not block it."""
    home = _home_with_model(
        tmp_path, model="qwen", provider="llama", base_url="http://127.0.0.1:8080/v1"
    )
    assert activation.pre_turn_refusal(
        ExternalAgentConfig(command="python3 acp"), home=home
    ) is None


def test_the_guard_names_a_missing_runtime_first(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "/nowhere/bin")
    why = activation.pre_turn_refusal(
        ExternalAgentConfig(command="hermes acp"), home=tmp_path
    )
    assert why is not None and "/nowhere/bin" in why


# ─────────────────────────────────────────────────────────────────────────────
# THE KEY THE USER ALREADY HAS — offered, never silently inherited (2026-11-22)
# ─────────────────────────────────────────────────────────────────────────────

def _fake_operator_home(monkeypatch, tmp_path, lines="DEEPSEEK_API_KEY=sk-operator\n"):
    op = tmp_path / "operator"
    op.mkdir()
    (op / ".env").write_text(lines, encoding="utf-8")
    monkeypatch.setattr(activation, "_operator_env_path", lambda: op / ".env")
    return op


def test_the_operator_home_is_reported_by_name_only(monkeypatch, tmp_path):
    _fake_operator_home(monkeypatch, tmp_path)
    home = tmp_path / "isolated" / ".hermes"
    assert activation.operator_key_names(home) == ["DEEPSEEK_API_KEY"]


def test_a_carried_key_is_not_offered_when_the_homes_are_the_same(monkeypatch, tmp_path):
    """A project placed directly under ~ must not be offered its own file."""
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text("DEEPSEEK_API_KEY=sk\n", encoding="utf-8")
    monkeypatch.setattr(activation, "_operator_env_path", lambda: home / ".env")
    assert activation.operator_key_names(home) == []


def test_carrying_is_a_flag_never_a_default(monkeypatch, tmp_path):
    _fake_operator_home(monkeypatch, tmp_path)
    home = tmp_path / ".hermes"

    activation.provision_home(home=home, seed_dir=tmp_path / "none", project_env=tmp_path / "none.env")
    assert "DEEPSEEK_API_KEY" not in (home / ".env").read_text(encoding="utf-8")

    log = activation.provision_home(
        home=home, seed_dir=tmp_path / "none", project_env=tmp_path / "none.env",
        carry_operator_env=True,
    )
    assert "DEEPSEEK_API_KEY=sk-operator" in (home / ".env").read_text(encoding="utf-8")
    # NAMES are logged; the value never is
    assert any("carried from the Hermes home: DEEPSEEK_API_KEY" in line for line in log)
    assert not any("sk-operator" in line for line in log)


def test_the_keys_step_says_where_the_key_already_is(monkeypatch, tmp_path):
    _fake_operator_home(monkeypatch, tmp_path)
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text("", encoding="utf-8")

    check = activation._check_keys(home)
    assert check.ok is False
    assert "DEEPSEEK_API_KEY" in check.fix
    assert "--carry-operator-env" in check.fix


def test_a_budget_is_not_a_provider_key(tmp_path):
    """MEASURED on the 0.1.2 walk: `INPUT_TOKEN_BUDGET=100000` counted as a provider key.

    The ladder printed `keys ✓ present: INPUT_TOKEN_BUDGET` on a home whose model had no
    credential — and, with the model step passing on its section alone, ended
    "READY — Exa can answer" over a runtime that could not make one call.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text("INPUT_TOKEN_BUDGET=100000\n", encoding="utf-8")

    assert activation._present_key_names(home) == []
    check = activation._check_keys(home)
    assert check.ok is False
    assert "--apply" in check.fix, "the fix names the door that copies a key this install already has"


def test_a_numeric_token_setting_is_not_a_credential():
    """A number is a setting; `_TOKEN` in the name does not make it a secret.

    The same trap shipped a numeric setting as an empty SECRET through the env-example
    generator (`SECRET_HINTS` contains `_TOKEN`) and stopped a fresh backend at import.
    """
    assert activation._is_credential("INPUT_TOKEN_BUDGET", "100000") is False
    assert activation._is_credential("SOME_TOKEN", "60") is False
    assert activation._is_credential("SOME_TOKEN", "abc123") is True
    assert activation._is_credential("DEEPSEEK_API_KEY", "sk-1") is True
    assert activation._is_credential("COGITATE_ENCRYPTION_KEY", "app-secret") is False


def test_provisioning_does_not_carry_the_input_budget(tmp_path):
    """The copy filter and the presence check are one rule now — neither carries a number."""
    home = tmp_path / ".hermes"
    env = tmp_path / "project.env"
    env.write_text("INPUT_TOKEN_BUDGET=100000\nDEEPSEEK_API_KEY=sk-test\n", encoding="utf-8")

    log = activation.provision_home(home=home, seed_dir=tmp_path / "none", project_env=env)
    written = (home / ".env").read_text(encoding="utf-8")

    assert "INPUT_TOKEN_BUDGET" not in written
    assert "DEEPSEEK_API_KEY=sk-test" in written
    assert not any("INPUT_TOKEN_BUDGET" in line for line in log)


def test_a_model_nobody_can_call_is_not_a_satisfied_step(tmp_path):
    """The verdict itself: two green rows over no credential made `ready` True."""
    home = _home_with_model(tmp_path, env_lines="INPUT_TOKEN_BUDGET=100000\n")
    report = activation.ActivationReport(
        checks=[activation._check_model(home), activation._check_keys(home)]
    )

    assert [c.ok for c in report.checks] == [False, False]
    assert report.ready is False, "a model nobody can call is not a satisfied sequence"
