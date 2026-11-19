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
_CARRIED_ENV_MARKERS = ("API_KEY", "BASE_URL", "TOKEN", "SECRET")
_KEY_MARKERS = ("API_KEY", "TOKEN", "SECRET")


@dataclass
class ActivationCheck:
    """One step of the sequence, as it was found on this machine."""

    name: str
    ok: bool
    detail: str
    fix: str = ""


@dataclass
class ActivationReport:
    checks: list[ActivationCheck] = field(default_factory=list)

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
        }


# ── the home ────────────────────────────────────────────────────────────────


def _home(home: Path | None) -> Path:
    return Path(home) if home is not None else Paths.exa_home


def _env_keys(dst: Path, src: Path) -> list[str]:
    """Copy ONLY the provider-key lines from src to dst; return the NAMES.

    Never returns or logs a value: the house rule is that .env is parsed in
    Python, never sourced and never printed.
    """
    names: list[str] = []
    lines: list[str] = []
    if src.exists():
        for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key = line.split("=", 1)[0].strip()
            # THE ORIGINAL FILTER, deliberately NOT widened: a `*_KEY` suffix
            # would also carry COGITATE_ENCRYPTION_KEY and the tracing keys into
            # the agent's home, and an app secret crossing that boundary is a
            # leak, not a convenience.
            if any(w in key.upper() for w in _CARRIED_ENV_MARKERS):
                lines.append(line)
                if line.split("=", 1)[1].strip():
                    names.append(key)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return names


def provision_home(
    home: Path | None = None,
    seed_dir: Path | None = None,
    operator_home: Path | None = None,
    project_env: Path | None = None,
) -> list[str]:
    """Create Exa's isolated home. Idempotent; existing files are preserved.

    Returns the log lines rather than printing them, so the CLI can format and
    a test can assert. The model section is NOT written from the operator's
    home: on a stranger's machine there is no operator home, and inventing a
    model is exactly the kind of silent decision this project refuses.
    """
    target = _home(home)
    seed = Path(seed_dir) if seed_dir is not None else Paths.skills_dir / "exa"
    op_home = Path(operator_home) if operator_home is not None else Path.home() / ".hermes"
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

    # The config: an existing one is kept. A COPY of the operator's home is the
    # developer convenience, not the release path — it is reported as inherited
    # so nobody mistakes it for a probe.
    cfg_dst = target / "config.yaml"
    if cfg_dst.exists():
        log.append("config.yaml present (kept)")
    elif (op_home / "config.yaml").exists():
        shutil.copy2(op_home / "config.yaml", cfg_dst)
        log.append("config.yaml copied from the operator's home (~/.hermes)")
    else:
        log.append("config.yaml NOT created — set a model on the Exa page")

    # The keys: only the provider-key lines, and only their NAMES are reported.
    names = _env_keys(target / ".env", env_src)
    if names:
        log.append("provider keys written: " + ", ".join(sorted(names)))
    else:
        log.append("no provider keys in .env — add one in Settings, or set them by hand")

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


def _check_model(home: Path) -> ActivationCheck:
    m = read_model_config(home)
    if m.get("model") and m.get("provider"):
        return ActivationCheck(
            "model", True, f"{m['model']} via {m['provider']}"
        )
    return ActivationCheck(
        "model",
        False,
        "no model section in config.yaml",
        fix="Set it on the Exa page (or pass --model/--provider with --apply).",
    )


def _check_keys(home: Path) -> ActivationCheck:
    env_path = home / ".env"
    names: list[str] = []
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if value.strip() and any(w in key.upper() for w in _KEY_MARKERS):
                names.append(key.strip())
    if names:
        return ActivationCheck("keys", True, "present: " + ", ".join(sorted(names)))
    return ActivationCheck(
        "keys",
        False,
        "no provider key in the isolated home's .env",
        fix="Add the provider key to the project's .env and run with --apply.",
    )


def _check_decision(cfg: ExternalAgentConfig) -> ActivationCheck:
    if cfg.enabled:
        return ActivationCheck("decision", True, "Exa is activated")
    return ActivationCheck(
        "decision",
        False,
        "Exa is inactive — it ships that way, and switching it on is the user's decision",
        fix="Run with --apply to activate, or press Activate on the Exa page.",
    )


async def probe(db, home: Path | None = None) -> ActivationReport:
    """Report every step of the activation sequence. Writes nothing."""
    cfg = await get_config(db)
    target = _home(home)
    return ActivationReport(
        checks=[
            _check_runtime(cfg),
            _check_home(target),
            _check_model(target),
            _check_keys(target),
            _check_decision(cfg),
        ]
    )


# ── the act ─────────────────────────────────────────────────────────────────


async def apply(
    db,
    home: Path | None = None,
    seed_dir: Path | None = None,
    operator_home: Path | None = None,
    project_env: Path | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[ActivationReport, list[str]]:
    """Provision the home, optionally set the brain, and take the decision.

    Returns the post-apply report and the provisioning log. The DECISION is
    taken last, so a half-provisioned home is never left switched on.
    """
    log = provision_home(
        home=home, seed_dir=seed_dir, operator_home=operator_home, project_env=project_env
    )
    if model and provider:
        write_model_config(
            model,
            provider,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            home=home,
        )
        log.append(f"model set: {model} via {provider}")

    cfg = await get_config(db)
    if not cfg.enabled:
        await save_config(db, cfg.model_copy(update={"enabled": True}))
        log.append("activated: Exa will spawn on the next chat")

    return await probe(db, home=home), log
