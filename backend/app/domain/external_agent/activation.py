"""The activation path — bringing Exa from "included" to "answering".

Exa ships INCLUDED and INACTIVE (2026-11-18). Activation is ONE sequence, and
this module is its one implementation: the install skill, the CLI
(`scripts/core/activate_exa.py`), the HTTP probe and the docs all read THIS,
because three copies of it would drift.

  1. RUNTIME   the configured command exists on PATH (Hermes, by default)
  2. HOME      <root>/.hermes — the isolated home, its seeded skills, a model
               section, and the provider keys lifted from the project's .env
  3. DECISION  the persisted `enabled` flag — the user's, never a side effect

Probing is what separates advice from a guess: `probe()` only REPORTS, and
`apply()` performs exactly the parts it was asked for. Nothing here writes a
key it was not given, and nothing prints a key at all.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Paths
from app.domain.external_agent.schemas import ExternalAgentConfig
from app.domain.external_agent.services import (
    command_parts,
    get_config,
    probe_runnable,
    save_config,
)

# THE DOCUMENTED HERMES INSTALLER (verified against the hermes-agent reference).
# Activation never runs this on its own: installing a runtime is the user's or
# the installing agent's action, so the probe REPORTS it as the fix.
HERMES_INSTALL_COMMAND = "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"

# What a provider key looks like in a .env — matched on the NAME only. The
# copy set also carries BASE_URL lines (a custom endpoint is part of a
# provider's config), but a base URL is not a key and never counts as one.
#
# NO "SECRET" (2026-11-20, measured). The marker carried LANGFUSE_SECRET_KEY into
# the agent's home — a TRACING credential, which this module's own rule says must
# not cross ("an app secret crossing that boundary is a leak, not a convenience"),
# and the test only asserted the PUBLIC half of the pair. A provider key is an
# API_KEY or a TOKEN; a SECRET is an application credential. Unknown names still
# do not carry a bare `*_KEY`, which is what keeps COGITATE_ENCRYPTION_KEY out.
_CARRIED_ENV_MARKERS = ("API_KEY", "BASE_URL", "TOKEN")
_KEY_MARKERS = ("API_KEY", "TOKEN")


@dataclass
class ActivationCheck:
    """One step of the sequence, as it was found on this machine."""

    name: str
    ok: bool
    detail: str
    fix: str = ""


@dataclass
class ChatOffer:
    """This install's chat answer, OFFERED to Exa — never written without an accept.

    Exa's model lives in its own config.yaml, and the rule that it is not copied from the
    operator's home is about SILENT decisions, not about using the same model. So the app's
    resolved chat model is offered here: `--from-default` (or the Exa page's button) accepts
    it, and nothing writes it otherwise.
    """

    provider: str
    model: str
    base_url: str | None = None

    def to_dict(self) -> dict:
        return {"provider": self.provider, "model": self.model, "base_url": self.base_url}


@dataclass
class ActivationReport:
    checks: list[ActivationCheck] = field(default_factory=list)
    offer: ChatOffer | None = None

    @property
    def ready(self) -> bool:
        """Every step satisfied — Exa can spawn AND answer."""
        return bool(self.checks) and all(c.ok for c in self.checks)

    @property
    def missing(self) -> list[ActivationCheck]:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "checks": [
                {"name": c.name, "ok": c.ok, "detail": c.detail, "fix": c.fix}
                for c in self.checks
            ],
            "offer": self.offer.to_dict() if self.offer is not None else None,
        }


# ── the home ────────────────────────────────────────────────────────────────


def _home(home: Path | None) -> Path:
    return Path(home) if home is not None else Paths.exa_home


def _operator_env_path() -> Path:
    """The operator's OWN Hermes home `.env` — where `hermes setup` puts a provider key.

    A user who configures Hermes the normal way ends with `DEEPSEEK_API_KEY` in `~/.hermes/.env`,
    and activation never read it: the copy source is the PROJECT's `.env`, whose every key NAME
    already exists with an EMPTY value (install writes it from `.env.example`), so the ladder said
    `keys ✗` and the same key had to be entered a second time (measured on a fresh install,
    2026-11-22). This is the path — carrying it across stays a decision.
    """
    return Path.home() / ".hermes" / ".env"


def operator_key_names(home: Path | None = None) -> list[str]:
    """Provider key NAMES the operator's Hermes home carries — names only, never a value.

    Empty when that home IS the isolated home (a project placed directly under `~`), so the offer
    can never point a user at the file it is about to write.
    """
    path = _operator_env_path()
    try:
        if path.parent.resolve() == _home(home).resolve():
            return []
    except OSError:  # an unreadable path is not an offer
        return []
    return _present_key_names(path.parent)


def _env_keys(dst: Path, src: Path) -> list[str]:
    """Copy ONLY the provider-key lines from src into dst; return the NAMES.

    MERGE, never truncate (2026-11-20, measured): activation now runs this on every
    switch, and `dst` is Exa's OWN store — `AUXILIARY_VISION_MODEL` is written there by
    the Model card and a hand-added variable is the user's. So a carried name is
    REPLACED in place, a new one is appended, and every other line survives; the old
    write-everything-else-away behaviour silently emptied the file on activation.

    Never returns or logs a value: the house rule is that .env is parsed in
    Python, never sourced and never printed.
    """
    carried: dict[str, str] = {}
    if src.exists():
        for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            # THE ORIGINAL FILTER, deliberately NOT widened: a `*_KEY` suffix
            # would also carry COGITATE_ENCRYPTION_KEY into the agent's home, and
            # an app secret crossing that boundary is a leak, not a convenience.
            if any(w in key.upper() for w in _CARRIED_ENV_MARKERS):
                carried[key] = line

    existing = dst.read_text(encoding="utf-8").splitlines() if dst.exists() else []
    merged: list[str] = []
    replaced: set[str] = set()
    for raw in existing:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in carried:
                merged.append(carried[key])
                replaced.add(key)
                continue
        merged.append(raw)
    merged.extend(line for key, line in carried.items() if key not in replaced)
    dst.write_text("\n".join(merged).rstrip("\n") + "\n", encoding="utf-8")

    return [key for key, line in carried.items() if line.split("=", 1)[1].strip()]


def provision_home(
    home: Path | None = None,
    seed_dir: Path | None = None,
    project_env: Path | None = None,
    carry_operator_env: bool = False,
) -> list[str]:
    """Create Exa's isolated home. Idempotent; existing files are preserved.

    Returns the log lines rather than printing them, so the CLI can format and
    a test can assert. NO MODEL is ever written here, and none is copied from an
    operator's home: Exa's brain is a decision, taken on the Exa page or with
    `--from-default`/`--model`. A home that arrived with a model keeps it.
    """
    target = _home(home)
    seed = Path(seed_dir) if seed_dir is not None else Paths.skills_dir / "exa"
    env_src = Path(project_env) if project_env is not None else Paths.root / ".env"
    log: list[str] = []

    for sub in ("memories", "skills", "sessions", "cron", "hooks"):
        (target / sub).mkdir(parents=True, exist_ok=True)

    # THE SEED SKILL SET: skills/exa/<name>/SKILL.md (+ any references) is
    # tracked in the repo and lands in the home's cogitate/ category. Copied
    # FILE BY FILE and only when ABSENT — an edited skill is never overwritten.
    if seed.exists():
        dest_cat = target / "skills" / "cogitate"
        dest_cat.mkdir(parents=True, exist_ok=True)
        seeded = 0
        for child in sorted(seed.iterdir()):
            src_skill = child / "SKILL.md"
            if not src_skill.exists():
                continue
            for src_file in sorted(child.rglob("*")):
                if not src_file.is_file() or "__pycache__" in src_file.parts:
                    continue
                dst_file = dest_cat / child.name / src_file.relative_to(child)
                if dst_file.exists():
                    continue
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                seeded += 1
        log.append(f"skills seeded into {dest_cat} ({seeded} file(s) added)")

    # The config: an existing one is kept — and that is the ONLY way a model
    # arrives here. Copying the operator's ~/.hermes was the developer
    # convenience, and on any box where Hermes is installed it handed Exa a
    # brain nobody chose (the offer-is-not-an-inheritance rule, 2026-11-20).
    cfg_dst = target / "config.yaml"
    if cfg_dst.exists():
        log.append("config.yaml present (kept)")
    else:
        log.append("config.yaml not created — Exa's model is a decision (the Exa page offers this install's chat model)")

    # The keys: only the provider-key lines, and only their NAMES are reported.
    names = _env_keys(target / ".env", env_src)
    if names:
        log.append("provider keys written: " + ", ".join(sorted(names)))
    else:
        log.append("no provider keys in .env — add one in Settings, or set them by hand")

    # THE SECOND SOURCE, for a key the user already configured elsewhere: the same narrow filter,
    # the same NAME-only reporting, and only when the caller asked (never a silent inheritance).
    if carry_operator_env:
        carried = _env_keys(target / ".env", _operator_env_path())
        if carried:
            log.append(
                "provider keys carried from the Hermes home: " + ", ".join(sorted(carried))
            )
        else:
            log.append(
                f"nothing to carry from {_operator_env_path()} — no provider key there either"
            )

    return log


# ── the model section (the one writer of it) ────────────────────────────────


def read_model_config(home: Path | None = None) -> dict:
    """Exa's model + reasoning sections from its private config.yaml."""
    try:
        import yaml as _yaml  # type: ignore[import-untyped]

        cfg_path = _home(home) / "config.yaml"
        if not cfg_path.exists():
            return {}
        with open(cfg_path, encoding="utf-8") as f:
            cfg = _yaml.safe_load(f) or {}
        m = cfg.get("model") or {}
        a = cfg.get("agent") or {}
        return {
            "model": m.get("default"),
            "provider": m.get("provider"),
            "base_url": m.get("base_url"),
            "reasoning_effort": a.get("reasoning_effort"),
        }
    except Exception:  # a broken file is a fact to report, not a crash
        return {}


def write_model_config(
    model: str,
    provider: str,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
    clear_base_url: bool = False,
    home: Path | None = None,
) -> None:
    """Write Exa's model (+ reasoning effort) into its private config.yaml."""
    import yaml as _yaml  # type: ignore[import-untyped]

    cfg_path = _home(home) / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = _yaml.safe_load(f) or {}
    cfg.setdefault("model", {})
    cfg["model"]["default"] = model
    cfg["model"]["provider"] = provider
    if base_url:
        cfg["model"]["base_url"] = base_url
    elif clear_base_url:
        # the client's own default applies — never leave a stale address behind
        cfg["model"].pop("base_url", None)
    if reasoning_effort is not None:
        cfg.setdefault("agent", {})
        cfg["agent"]["reasoning_effort"] = reasoning_effort
    with open(cfg_path, "w", encoding="utf-8") as f:
        _yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


# ── the probe ───────────────────────────────────────────────────────────────


def _check_runtime(cfg: ExternalAgentConfig) -> ActivationCheck:
    blocked = probe_runnable(cfg)
    first = (command_parts(cfg.command) or ["hermes"])[0]
    if blocked is None:
        return ActivationCheck(
            "runtime", True, f"'{first}' is on PATH (command: {cfg.command})"
        )
    return ActivationCheck(
        "runtime",
        False,
        blocked,
        fix=f"Install the runtime: {HERMES_INSTALL_COMMAND}",
    )


def _check_home(home: Path) -> ActivationCheck:
    missing = [
        part
        for part, present in (
            ("the home directory", home.is_dir()),
            ("config.yaml", (home / "config.yaml").exists()),
            ("skills/cogitate", (home / "skills" / "cogitate").is_dir()),
        )
        if not present
    ]
    if missing:
        return ActivationCheck(
            "home",
            False,
            f"{home} is missing {', '.join(missing)}",
            fix="Run this command with --apply to provision it.",
        )
    return ActivationCheck("home", True, f"{home} is provisioned")


def _present_key_names(home: Path) -> list[str]:
    """The provider key NAMES the isolated home carries with a non-empty value."""
    env_path = home / ".env"
    names: list[str] = []
    if not env_path.exists():
        return names
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value.strip() and any(w in key.upper() for w in _KEY_MARKERS):
            names.append(key.strip())
    return names


def _is_loopback(url: str) -> bool:
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def _model_usable(home: Path, provider: str, base_url: str | None) -> tuple[bool, str]:
    """Can the configured model actually be CALLED from this home? `(usable, why not)`.

    Two facts, not one: a model being SET says nothing about a credential existing, and this
    ladder reported only the first — a home carrying the operator's `anthropic/claude-opus-4.6`
    (copied config) read `model ✓` beside `keys ✗`, i.e. a runtime that could not make one call
    (measured on a fresh install, 2026-11-22). A LOCAL endpoint needs no key, so it is usable.
    """
    if base_url and _is_loopback(base_url):
        return True, ""
    from app.domain.providers.env_key_store import env_key_store

    name = env_key_store.env_var_for(provider) or env_key_store.env_var_for(provider.lower())
    if name is None:
        return False, f"no provider key name is known for '{provider}'"
    if name in _present_key_names(home):
        return True, ""
    return False, f"{name} is empty or absent in the isolated home"


def _check_model(home: Path, offer: ChatOffer | None = None) -> ActivationCheck:
    """The model step: what is configured, whether it can ANSWER, and the offer.

    `ok` stays about the section existing — Exa may deliberately run on something other than
    this install's model. USABILITY rides the detail, so the ladder reads
    `model ✓ (usable: no — ANTHROPIC_API_KEY is empty ...)` rather than a ✓ that a stranger
    reads as a working model.
    """
    m = read_model_config(home)
    have = (m.get("model"), m.get("provider"))
    if have[0] and have[1]:
        usable, why = _model_usable(home, have[1], m.get("base_url"))
        detail = f"{have[0]} via {have[1]} (usable: {'yes' if usable else 'no — ' + why})"
        if offer is not None and have != (offer.model, offer.provider):
            detail += f"; this install's chat model is {offer.model} via {offer.provider}"
        return ActivationCheck("model", True, detail)
    fix = (
        f"Take this install's chat model — {offer.model} via {offer.provider} (--from-default, "
        "or the Exa page). Nothing is set for you."
        if offer is not None
        else "Set it on the Exa page (or pass --model/--provider with --apply)."
    )
    return ActivationCheck("model", False, "no model section in config.yaml", fix=fix)


def _check_keys(home: Path) -> ActivationCheck:
    names = _present_key_names(home)
    if names:
        return ActivationCheck("keys", True, "present: " + ", ".join(sorted(names)))
    # A key the operator already configured in their OWN Hermes home is one command away, and
    # saying so is the difference between "type it again" and "you already have this" (2026-11-22).
    available = operator_key_names(home)
    fix = "Add the provider key to the project's .env and run with --apply."
    if available:
        fix = (
            f"{_operator_env_path()} already has {', '.join(sorted(available))} — carry it across "
            f"with `scripts/core/activate_exa.py --apply --carry-operator-env`, or paste the key on "
            f"the Exa page's Keys tab. A key entered into Hermes elsewhere does not count on its own."
        )
    return ActivationCheck(
        "keys",
        False,
        "no provider key in the isolated home's .env",
        fix=fix,
    )


def pre_turn_refusal(cfg: ExternalAgentConfig, home: Path | None = None) -> str | None:
    """None when a turn can be ATTEMPTED, else the sentence saying why it cannot.

    Three facts make a turn impossible before it starts, and all three are LOCAL reads (the binary
    on PATH; config.yaml; the isolated home's .env):

    - the runtime is not on PATH;
    - the home has no model section;
    - the configured model's provider has no credential **and is not a loopback endpoint**.

    It exists because the alternative is silence: on a fresh install a turn sat in its streaming
    state for six minutes while the runtime did a first-run install and then had no key to call,
    with the 900-second turn timer as the only thing that would ever have said so (measured
    2026-11-22). A refusal is one frame, names the fix, and costs nothing to compute.

    Deliberately NOT a verdict about whether the provider will answer — a present key can still be
    wrong. This refuses only what cannot possibly work.
    """
    blocked = probe_runnable(cfg)
    if blocked:
        return f"Exa cannot answer: {blocked}"

    resolved_home = _home(home)
    model = read_model_config(resolved_home)
    if not (model.get("model") and model.get("provider")):
        return (
            "Exa has no model configured, so this turn cannot run. Take this install's chat model "
            "on the Exa page (or run `activate_exa.py --from-default --apply`), then send again."
        )
    usable, why = _model_usable(resolved_home, model["provider"], model.get("base_url"))
    if not usable:
        return (
            f"Exa's model {model['model']} via {model['provider']} cannot be called: {why}. "
            "Add the provider key on the Exa page's Keys tab (or run `activate_exa.py --apply`), "
            "then send again."
        )
    return None


def _check_decision(cfg: ExternalAgentConfig) -> ActivationCheck:
    if cfg.enabled:
        return ActivationCheck("decision", True, "Exa is activated")
    return ActivationCheck(
        "decision",
        False,
        "Exa is inactive — it ships that way, and switching it on is the user's decision",
        fix="Run with --apply to activate, or press Activate on the Exa page.",
    )


async def chat_offer(db) -> ChatOffer | None:
    """This install's resolved chat answer, as Exa would need it — or None.

    The resolver is the one place that knows what answers chat here; Exa's config wants the
    litellm model string for that row, which `litellm_model_string` is the one home of.
    """
    from app.domain.providers.capabilities import resolve
    from app.domain.providers.litellm_route import litellm_model_string

    resolved = await resolve(db, "chat")
    primary = resolved.primary
    if primary is None or not primary.provider or not primary.model:
        return None
    try:
        # THE TYPE DECIDES THE HANDLER, not the name (measured 2026-11-20: a row named
        # "Deepseek" with type "deepseek" produced `Deepseek/deepseek-flash`, which no
        # handler answers — litellm's prefixes are lowercase).
        model = litellm_model_string(primary.provider, primary.model, primary.provider_type)
    except Exception:  # a string litellm cannot build is still the row's own answer
        model = primary.model
    # THE PROVIDER FIELD IS A litellm KEY, not the row's display name (measured 2026-11-20:
    # a row named "Deepseek" offered `via Deepseek`, which is not a provider key). The TYPE
    # is what the handler map knows; the name is what a human reads.
    return ChatOffer(
        provider=primary.provider_type or primary.provider,
        model=model,
        base_url=primary.endpoint,
    )


async def probe(db, home: Path | None = None) -> ActivationReport:
    """Report every step of the activation sequence. Writes nothing."""
    cfg = await get_config(db)
    target = _home(home)
    offer = await chat_offer(db)
    return ActivationReport(
        offer=offer,
        checks=[
            _check_runtime(cfg),
            _check_home(target),
            _check_model(target, offer),
            _check_keys(target),
            _check_decision(cfg),
        ],
    )


# ── the act ─────────────────────────────────────────────────────────────────


async def apply(
    db,
    home: Path | None = None,
    seed_dir: Path | None = None,
    project_env: Path | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
    from_default: bool = False,
    carry_operator_env: bool = False,
) -> tuple[ActivationReport, list[str]]:
    """Provision the home, optionally set the brain, and take the decision.

    `from_default` takes THIS INSTALL'S chat model — the accept for the offer. Without it and
    without an explicit --model/--provider, no model is written: inventing one is the silent
    decision this path refuses. When nothing is set, the log NAMES the offer, because a model-less
    Exa answers as plain Hermes and that is the failure this path exists to prevent.

    Returns the post-apply report and the provisioning log. The DECISION is
    taken last, so a half-provisioned home is never left switched on.
    """
    log = provision_home(
        home=home,
        seed_dir=seed_dir,
        project_env=project_env,
        carry_operator_env=carry_operator_env,
    )
    if from_default and not (model and provider):
        offer = await chat_offer(db)
        if offer is None:
            log.append(
                "no chat model resolves on this install yet — nothing to take; set the "
                "default provider and model first (or pass --model/--provider)"
            )
        else:
            model, provider = offer.model, offer.provider
            # A local row's address is part of the answer; a cloud provider keeps the
            # client's own default rather than a copied URL.
            base = offer.base_url or ""
            if "localhost" in base or "127.0.0.1" in base:
                base_url = base_url or base
            log.append(f"model offered by this install and accepted: {model} via {provider}")
    if model and provider:
        write_model_config(
            model,
            provider,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            home=home,
        )
        log.append(f"model set: {model} via {provider}")
    elif read_model_config(home).get("model"):
        # Provisioning never touches an existing brain; say so rather than let the
        # absence of a "model set" line read as "it has none".
        m = read_model_config(home)
        log.append(f"model unchanged: {m.get('model')} via {m.get('provider')}")
    else:
        offer = await chat_offer(db)
        if offer is not None:
            log.append(
                f"no model yet — this install offers {offer.model} via {offer.provider}"
            )
        else:
            log.append("no model yet, and nothing on this install can answer chat to offer")

    cfg = await get_config(db)
    if not cfg.enabled:
        await save_config(db, cfg.model_copy(update={"enabled": True}))
        log.append("activated: Exa will spawn on the next chat")

    return await probe(db, home=home), log
