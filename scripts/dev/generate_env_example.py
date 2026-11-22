"""Generate `.env.example` from the settings the app actually reads.

The example file and the configuration surface are two descriptions of one
thing, and they had drifted apart: the file named keys nothing reads, spelled
one key the app never reads, and missed every key the app reads outside
`Settings`. So the file is BUILT — from `Settings` (backend/app/core/config.py)
plus a registry of the env reads that bypass it.

    python3 scripts/dev/generate_env_example.py            # write .env.example
    python3 scripts/dev/generate_env_example.py --check     # gate: exit 1 if stale
    python3 scripts/dev/generate_env_example.py --stdout    # print, write nothing

A field's env name is its own name upper-cased (`max_upload_size` →
`MAX_UPLOAD_SIZE`). Three rules decide what is written for it:

- a default DERIVED from the project root at startup is commented out — a
  machine path must never ship, and an empty value would break the setting;
- a SECRET gets an empty assignment, so `.env` stays the only store;
- everything else is written with its default, because every field has one and
  the app therefore runs with no `.env` at all.

Keys read with `os.getenv` OUTSIDE `Settings` cannot be found by walking the
model, so they live in `REGISTERED`, each with the file that reads it. A new
one has to be added there or it will not appear in the file — that registry is
the one hand-maintained thing here, and it is 9 lines.

`--check` gates the file in the pre-commit hook and in
`scripts/testing/verify_flat_tree.sh`: a hand edit to `.env.example` fails, and
so does a new `Settings` field that nobody regenerated for.
"""

import argparse
import json
import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / ".env.example"

#: Presentation only: which heading a declared field is listed under. A field
#: that no group names still gets written, under `Other settings` — the gate
#: cannot be defeated by forgetting to add it here.
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    (
        "App identity and server",
        ("app_name", "app_version", "debug", "environment", "host", "port"),
    ),
    (
        "Startup work",
        ("startup_sweep_enabled", "exa_background_processing_enabled"),
    ),
    ("Databases", ("database_url", "documents_database_url", "db_echo")),
    (
        "CORS",
        (
            "cors_origins",
            "cors_allow_credentials",
            "cors_allow_methods",
            "cors_allow_headers",
        ),
    ),
    (
        "Provider API keys",
        (
            "openai_api_key",
            "anthropic_api_key",
            "openrouter_api_key",
            "deepseek_api_key",
            "groq_api_key",
            "ollama_cloud_api_key",
            "tavily_api_key",
            "litellm_master_key",
        ),
    ),
    ("Default provider and model", ("default_llm_provider", "default_llm_model")),
    (
        "Tracing",
        (
            "langfuse_public_key",
            "langfuse_secret_key",
            "langfuse_base_url",
            "langfuse_host",
            "langfuse_environment",
            "langfuse_tracing_enabled",
        ),
    ),
    ("Encryption", ("cogitate_encryption_key",)),
    (
        "Sync, uploads and files",
        (
            "default_sync_interval_hours",
            "max_upload_size",
            "max_sound_upload_size",
            "allowed_image_types",
            "allowed_sound_types",
            "profile_images_dir",
        ),
    ),
    ("Logging and cache", ("log_level", "log_file", "cache_ttl_seconds")),
    ("Local models", ("llama_model_path",)),
]

#: Keys the app (or the frontend) reads WITHOUT going through `Settings`, with
#: the reader that makes them real. Walking the model cannot see these, so this
#: is the list that keeps the file honest about them.
REGISTERED: list[tuple[str, str, str]] = [
    (
        "VITE_API_URL",
        "frontend/src/services/apiClient.ts (build-time, via import.meta.env)",
        "the backend origin the browser talks to; unset means same origin",
    ),
    (
        "COGITATE_BACKEND_URL",
        "backend/app/domain/tools/registry.py",
        "the backend's own origin, used by tools that call back into the API",
    ),
    (
        "COGITATE_DECLARATIVE_TOOL_TOKEN",
        "backend/app/domain/tools/declarative.py",
        "the token a declarative tool presents when it calls back",
    ),
    (
        "INBOX_PROCESSOR_INTERVAL_SECONDS",
        "backend/app/main.py (cogitate.sh passes 20 for development)",
        "the drain's period; the code default is 900",
    ),
    (
        "SYSTEM_SWEEP_DELAY_SECONDS",
        "backend/app/main.py (cogitate.sh passes 15 for development)",
        "the boot sweep's delay; the code default is 60",
    ),
    (
        "WORKFLOW_DB_URL",
        "backend/app/workflows/checkpointing/config.py",
        "the checkpoint store's database",
    ),
    (
        "TITLE_LLM_ENABLED",
        "backend/app/domain/title/services.py",
        "whether session titles are generated at all",
    ),
    (
        "TITLE_LLM_MAX_TOKENS",
        "backend/app/domain/title/services.py",
        "the title call's token ceiling; the code default is 128",
    ),
    (
        "TITLE_LLM_TEMPERATURE",
        "backend/app/domain/title/services.py",
        "the title call's temperature; the code default is 0.3",
    ),
]

SECRET_HINTS = ("_KEY", "_TOKEN", "_SECRET", "PASSWORD")

HEADER = """\
# =============================================================================
# Cogitate environment configuration — GENERATED, DO NOT EDIT
# =============================================================================
#
# The app runs with no .env at all: every key below has a default, and the
# defaults are declared in backend/app/core/config.py. Values here exist so a
# fresh install can be tuned without reading the source.
#
# To configure: cp .env.example .env, then set only what you need. `.env` is
# gitignored — it is the only place a secret belongs.
#
# Regenerate with `python3 scripts/dev/generate_env_example.py`; `--check` runs
# in the pre-commit hook and the flat-tree gates, so a hand edit fails.
"""


def _settings():
    """Import the app's Settings model (the backend package is not installed)."""
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from app.core.config import Settings  # noqa: PLC0415

    return Settings


def _literal(field) -> str | None:
    """The default as an env value, or None when it must not be written."""
    default = field.default
    if default is None:
        return None
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, (list, dict)):
        return json.dumps(default)
    return str(default)


def _is_derived(value: str) -> bool:
    """True when the default is a path resolved from the project root at startup."""
    return str(PROJECT_ROOT) in value or value.startswith("/")


def _entry(name: str, field, note: str = "") -> list[str]:
    """The comment lines and the assignment for one declared field."""
    env_name = name.upper()
    type_name = str(field.annotation).replace("<class '", "").replace("'>", "")
    lines: list[str] = []
    suffix = f" — {note}" if note else ""
    literal = _literal(field)
    if field.is_required():
        lines.append(f"# {type_name} · REQUIRED{suffix}")
        lines.append(f"{env_name}=")
    elif literal is None:
        lines.append(f"# {type_name} · unset: resolved in code{suffix}")
        lines.append(f"# {env_name}=")
    elif _is_derived(literal):
        lines.append(f"# {type_name} · derived from the project root{suffix}")
        lines.append(f"# {env_name}=")
    elif isinstance(field.default, str) and (
        env_name.endswith(SECRET_HINTS) or any(h in env_name for h in SECRET_HINTS)
    ):
        # A NON-STRING FIELD CANNOT BE A SECRET (2026-11-22). The name heuristic matched `_TOKEN` in
        # `INPUT_TOKEN_BUDGET` — a number — and shipped it as an empty placeholder, which made a fresh
        # `.env` fail to parse at import. Secrets are strings; anything else keeps its default.
        lines.append(f"# {type_name} · secret: `.env` only, never committed{suffix}")
        lines.append(f"{env_name}=")
    else:
        shown = literal if literal else "(empty)"
        lines.append(f"# {type_name} · default: {shown}{suffix}")
        lines.append(f"{env_name}={literal}")
    return lines


def render() -> str:
    """The file's whole text — deterministic, with no clock in it."""
    settings_cls = _settings()
    fields = settings_cls.model_fields
    notes = {
        "default_llm_provider": "read by nothing; a capability or a provider row answers instead",
        "default_llm_model": "read by nothing; the model belongs to the capability or the row",
        "langfuse_environment": "the environment tag traces carry; unset means development",
    }

    drafted: list[str] = [HEADER]
    grouped: set[str] = set()

    def section(heading: str, names: tuple[str, ...]) -> None:
        body: list[str] = []
        for name in names:
            field = fields.get(name)
            if field is None:
                raise SystemExit(
                    f"generate_env_example: GROUPS names `{name}`, which Settings does not declare"
                )
            body.extend(_entry(name, field, notes.get(name, "")))
            body.append("")
            grouped.add(name)
        if body:
            drafted.append(f"# {'-' * 75}\n# {heading}\n# {'-' * 75}\n")
            drafted.append("\n".join(body))

    for heading, names in GROUPS:
        section(heading, names)

    leftovers = tuple(n for n in fields if n not in grouped)
    if leftovers:
        section("Other settings", leftovers)

    stray = [
        "# ---------------------------------------------------------------------------",
        "# Read outside Settings — no model declares these, so they are listed by hand",
        "# ---------------------------------------------------------------------------",
        "",
    ]
    for name, reader, note in REGISTERED:
        stray.append(f"# {note}")
        stray.append(f"# reader: {reader}")
        stray.append(f"# {name}=")
        stray.append("")

    drafted.append("\n".join(stray))
    text = "\n".join(drafted)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.rstrip("\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the file is stale")
    parser.add_argument("--stdout", action="store_true", help="print, write nothing")
    args = parser.parse_args()

    rendered = render()

    if args.stdout:
        print(rendered, end="")
        return 0

    current = OUTPUT.read_text() if OUTPUT.exists() else ""
    if args.check:
        if current == rendered:
            print("CURRENT: .env.example matches the settings the app reads")
            return 0
        import difflib

        diff = list(
            difflib.unified_diff(
                current.splitlines(),
                rendered.splitlines(),
                fromfile=".env.example (on disk)",
                tofile=".env.example (from Settings)",
                lineterm="",
                n=2,
            )
        )
        print("STALE: .env.example does not match the app's settings surface")
        print("\n".join(diff[:60]))
        print("\nRegenerate: python3 scripts/dev/generate_env_example.py")
        return 1

    OUTPUT.write_text(rendered)
    keys = len(re.findall(r"^[A-Z][A-Z0-9_]*=", rendered, re.M))
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)} — {keys} settable keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
