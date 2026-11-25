"""
Application configuration using Pydantic Settings.

Loads configuration from environment variables with sensible defaults
for local development.
"""

from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# BASE_DIR Configuration
# =============================================================================
# 
# CRITICAL: BASE_DIR must always resolve to PROJECT ROOT, regardless of
# working directory. This is essential because cogitate.sh changes to
# backend/ directory before starting uvicorn (for proper signal handling
# and logging).
#
# config.py location: backend/app/core/config.py
# Directory levels to traverse:
#   Level 0: config.py (this file)
#   Level 1: core/      (.parents[0])
#   Level 2: app/       (.parents[1])
#   Level 3: backend/   (.parents[2])
#   Level 4: cogitate/  (.parents[3]) ← PROJECT ROOT ✅
#
# Note: .parents is 0-indexed, so .parents[3] = 4th parent = project root
# =============================================================================

BASE_DIR = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Paths:
    """The locator service for the app's canonical paths.

    ONE place resolves where the important things live; modules
    import Paths instead of recomputing path arithmetic per-file
    (the bug class fixed 2026-08-17: workflow_router + template_
    router opened a phantom <install-root>.db via
    parent×5; the provisioning router wrote to production via a
    hardcoded path). The industrial fork flips these to Postgres
    without touching the call sites.

    Attributes:
        root: the project root (BASE_DIR — canonical).
        shared_db: the shared cogitate.db path — derived from
            settings.database_url (honors DATABASE_URL overrides
            in tests; the provisioning fix's pattern).
        data_dir: the runtime data dir (root/data).
        monitor_dir: the product/report delivery dir (data/monitor).
        agents_dir: the agent workspaces dir (root/agents).
        logs_dir: the backend logs dir (root/backend/logs).
        tests_dir: the backend test tree (backend/tests) — the groups.
        selftest_dir: the page's own exercise (backend/selftest) — outside
            tests/ on purpose, so no group and no sweep collects it.
        test_runs_dir: the test runs (data/test-runs) — one folder per
            run: report.md, report.xml, events.jsonl.
        test_reports_dir: where a run SAVED by hand goes (data/test-reports) —
            the default destination for the page's Save, and nothing else: no
            repository, no retention, and the page never writes here on its own.
        sweep_dir: the system sweep's own reports + baseline
            (data/sweep) — system space, not a person's runs.
        trash_dir: the recoverable-delete staging area (root/trash).
        exa_home: the external agent's private Hermes home
            (root/.hermes) — HERMES_HOME for the Exa subprocess.
        rag_index_path: the RAG doc index (data/system_docs_vector.db).
        code_vector_path: the code vector index (data/system_code_vector.db).
        rag_status_file: the RAG ingest status file (data/rag_ingest_status.json).
    """

    root: Path = BASE_DIR
    shared_db: Path = BASE_DIR / "cogitate.db"
    data_dir: Path = BASE_DIR / "data"
    monitor_dir: Path = BASE_DIR / "data" / "monitor"
    agents_dir: Path = BASE_DIR / "agents"
    # THE SHIPPED AGENTS' SOURCE (Phase D, item 3): the tracked packages a fresh
    # install seeds from — `backend/templates/agents/<key>/{package.json,persona.md}`.
    # Deliberately NOT under `agents/`: that directory holds per-install WORKSPACES
    # (gitignored), and a seed source only exists in a clone if it is in the repo.
    agent_seed_dir: Path = BASE_DIR / "backend" / "templates" / "agents"
    # THE SHIPPED MACRO PACKS (`macros/<pack>/{meta-topic.json, macro-sets/*.json}`).
    # Tracked, so a clone carries them; a fresh install seeds the ones whose
    # manifest names a surface. Deliberately NOT `data/macro-saves/` — that is
    # gitignored and holds the user's own exports, which the Save/Load page lists.
    macro_packs_dir: Path = BASE_DIR / "macros"
    agent_images_dir: Path = BASE_DIR / "assets" / "agent-images"
    notification_sounds_dir: Path = BASE_DIR / "data" / "notification-sounds"
    curated_sounds_dir: Path = BASE_DIR / "assets" / "notification-sounds"
    piper_dir: Path = BASE_DIR / "backend" / "data" / "piper"
    wiki_dir: Path = BASE_DIR / "wiki"
    # THE USER-TESTING PAGE. The test tree and the RUNS dir —
    # resolved HERE, like every other canonical path, so the
    # testing router does no path arithmetic of its own (the bug class the
    # docstring above names).
    tests_dir: Path = BASE_DIR / "backend" / "tests"
    selftest_dir: Path = BASE_DIR / "backend" / "selftest"
    #   THE PAGE'S OWN EXERCISE. Deliberately OUTSIDE tests/: `testpaths`
    #   is ["tests"] and every runner group selects tests/, so a fixture
    #   whose job is to produce failures would otherwise turn every full
    #   run and every sweep red — and a suite that is always red tells a
    #   person nothing. The page runs it by name, from its own tab.
    test_runs_dir: Path = BASE_DIR / "data" / "test-runs"
    #   ONE FOLDER PER RUN: report.md (the developer's hard copy),
    #   report.xml (JUnit — what the page parses) and events.jsonl (the
    #   live record). Under data/ because a run is a runtime artifact of a
    #   feature, not a developer's scratch file: local/ is untracked and
    #   does not exist in an installation.
    test_reports_dir: Path = BASE_DIR / "data" / "test-reports"
    #   WHERE A SAVED RUN GOES — the default destination for the page's
    #   Save, which COPIES a run's folder here so a person keeps it. It is
    #   a destination, not a repository: nothing is written here unless a
    #   person presses Save, and nothing reads it back or prunes it.
    sweep_dir: Path = BASE_DIR / "data" / "sweep"
    #   THE SYSTEM SWEEP'S OWN OUTPUT (its reports and its baseline).
    #   Separate from the runs because the boundary is real: the sweep
    #   machine's health record is not a person's test run.
    trash_dir: Path = BASE_DIR / "trash"
    #   THE RECOVERABLE-DELETE STAGING AREA. A deleted thing MOVES here
    #   rather than vanishing, so "delete" is one action away from undo.
    #   It holds ONE SHELF PER DOMAIN (agents, test-runs, reports, dbs,
    #   misc) — see trash_dir_for below — and a run a person deletes
    #   goes to trash/test-runs/<name>. Gitignored, and created on
    #   demand: an installation starts without it.
    macro_templates_dir: Path = BASE_DIR / "backend" / "templates" / "macros"
    backups_dir: Path = BASE_DIR / "backend" / "data" / "backups"
    skills_dir: Path = BASE_DIR / "skills"
    logs_dir: Path = BASE_DIR / "backend" / "logs"
    access_log: Path = BASE_DIR / "backend" / "logs" / "access.log"
    #   (2026-08-20): the access-evidence journal — the
    #   verify-http-evidence tool's VERIFIED source (uvicorn's
    #   access log is stdout-bound; this file is the robust one)
    exa_workspace: Path = BASE_DIR / ".exa-workspace"
    #   (2026-08-20): Exa's DESK — the workspace where the system
    #   agent puts reports, receives workflow products (inbox/),
    #   and stages files. The home/workspace split: .hermes/ is
    #   the identity (Hermes state), this is the work area (the
    #   OpenClaw WORKSPACE_DIR pattern). Gitignored, per-install.
    exa_home: Path = BASE_DIR / ".hermes"  # the external agent's
    #   private Hermes home (Phase 1 2026-08-18): HERMES_HOME for
    #   the Exa subprocess — per-install, shippable, isolated from
    #   the operator's ~/.hermes.
    rag_index_path: Path = BASE_DIR / "data" / "system_docs_vector.db"
    code_vector_path: Path = BASE_DIR / "data" / "system_code_vector.db"
    rag_status_file: Path = BASE_DIR / "data" / "rag_ingest_status.json"

    # ── the trash's shelves ────────────────────────────────────────────────
    @classmethod
    def trash_dir_for(cls, domain: str) -> Path:
        """The trash shelf for ONE domain — `trash/<domain>/`.

        THE ROOT IS THE LOCATOR'S; THE DOMAIN NAME IS THE REGISTRY'S. The trash
        holds one shelf per domain, and that vocabulary belongs to the domain
        registry (`app.domain.trash.registry`) — so this method deliberately
        carries NO second copy of the list, and a shelf is asked for by the
        name the registry registered.

        What it DOES enforce is the SHAPE of a key: one clean path segment, no
        separators, no parent references, no dot-leading name. A misspelling
        therefore fails at the registry (`get_domain` refuses an unknown key)
        and a malformed one fails HERE, rather than quietly creating
        `trash/agnts/` and burying a shelf inside a typo.

        A CLASSMETHOD, so it reads the SAME attribute every other reader of the
        trash reads (`cls.trash_dir`) — a shelf resolves through the locator
        instead of being composed by hand at the call site, and a test that
        points the trash elsewhere does so in one place.
        """
        key = (domain or "").strip()
        if not key or key != Path(key).name or key.startswith("."):
            raise ValueError(
                f"a trash domain must be a single clean path segment, got {domain!r}"
            )
        return cls.trash_dir / key

    @classmethod
    def from_settings(cls, settings: "Settings") -> "Paths":
        """Build the locator honoring settings.database_url — the
        single source of truth for the shared DB (tests override
        DATABASE_URL; the industrial fork points it at Postgres).

        The sqlite URL conventions (the 2026-08-29 fix — the
        file:-URI readers silently failed on the double-slash):
          sqlite+aiosqlite:///relative.db   -> path "/relative.db"
                                                -> relative.db
          sqlite+aiosqlite:////abs/path.db  -> path "//abs/path.db"
                                                -> /abs/path.db
        """
        from dataclasses import fields as _dataclass_fields
        from urllib.parse import urlparse

        parsed = urlparse(settings.database_url)
        raw = parsed.path
        if not raw:
            return cls(shared_db=Path(BASE_DIR / "cogitate.db"))
        if raw.startswith("//"):
            raw = raw[1:]  # the absolute form: drop ONE leading slash
        else:
            raw = raw.lstrip("/")  # the relative form: drop the leading slash
        shared = Path(raw)

        # THE ROOT FOLLOWS THE DATABASE. The shared DB sits at the root of an
        # installation, so its parent IS that root — and every other path here
        # hangs off it.
        #
        # Historically only `shared_db` was honoured. The consequence was
        # silent: pointing DATABASE_URL at a temporary file redirected the
        # database and NOTHING ELSE, so agent workspaces, per-agent memory
        # databases, pipeline traces and logs still landed in the production
        # tree. The docstring above promises the opposite, and this is that
        # promise kept.
        base = Path(BASE_DIR)
        root = shared.parent
        if not str(root) or root.resolve() == base.resolve():
            # Production, or a URL with no usable directory: the declarations
            # below already point at the right place. Nothing moves.
            return cls(shared_db=shared)

        # Re-root EVERY field declared relative to BASE_DIR — derived from the
        # declarations rather than a second hand-written list, so the two cannot
        # drift apart. A new field is handled the day it is added.
        moved: dict = {"shared_db": shared}
        for f in _dataclass_fields(cls):
            if f.name == "shared_db" or not isinstance(f.default, Path):
                continue
            try:
                rest = f.default.relative_to(base)
            except ValueError:
                continue  # not declared under BASE_DIR — leave it alone
            moved[f.name] = root if str(rest) == "." else root / rest
        return cls(**moved)

    @classmethod
    def rooted_at(cls, shared_db: "Path | str") -> "Paths":
        """The installation whose shared database sits at `shared_db`.

        `from_settings` answers this for a running application, from
        DATABASE_URL. This answers it for a caller that HAS a database and no
        settings object — a test standing up its own sandbox, a script aimed at a
        copy — and it derives the WHOLE installation the same way, because the
        one-field form is a trap: `Paths(shared_db=...)` leaves every other field
        at its BASE_DIR declaration, so the database moves and the tree does not.
        That is how tests came to write a LangGraph checkpointer into the
        repository root and a verification store into the operator's `data/`.
        """
        path = Path(shared_db)
        # The URL conventions from `from_settings`: three slashes for a relative
        # path, four for an absolute one (which is what an absolute Path gives).
        return cls.from_settings(Settings(database_url=f"sqlite+aiosqlite:///{path}"))


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # THE PROJECT'S `.env`, BY PATH — not `".env"`.
        #
        # A bare `".env"` resolves against the PROCESS CWD, and `cogitate.sh` cds to
        # `backend/` before uvicorn, so the file it named (`backend/.env`) is one this
        # repository does not have. Configuration arrived anyway, from a side effect:
        # litellm calls `load_dotenv()` at import, which walks up from the cwd and finds
        # the root `.env`, putting every key in `os.environ` — where pydantic reads it
        # first. Invisible, order-dependent, and silent when it stops: every field has a
        # default, so a lost `.env` boots a keyless app instead of failing.
        #
        # Anchored to BASE_DIR, the store is the one `EnvKeyStore` writes and the one the
        # README tells a stranger to create, whatever directory the process starts in.
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Cogitate"
    app_version: str = "0.1.4"
    debug: bool = True
    environment: str = "development"  # development, staging, production

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # THE INPUT CEILING — one knob, not a per-model system (2026-11-21).
    #
    # `token_budget.DEFAULT_INPUT_BUDGET` is the policy number the prompt assembly may fill; the
    # MODEL's own window can only LOWER it. Sizing per model was ruled out as "a per model config
    # and a moving target at that", so the ceiling is a human's single number instead: an install
    # running a small local model sets `INPUT_TOKEN_BUDGET=16384` in `.env` and nothing else
    # changes. 100000 is the default because every model the express shortlist ships answers a
    # 1M-token window, and 16K was dropping history that had room to stay.
    input_token_budget: int = 100_000

    @field_validator("input_token_budget", mode="before")
    @classmethod
    def _empty_budget_is_the_default(cls, value: object) -> object:
        """`INPUT_TOKEN_BUDGET=` in `.env` means "unset", not "a number that failed to parse".

        Measured 2026-11-22 on a release install: a fresh `.env` is copied from `.env.example`, and that
        file carries the key with NO value (the generator had classed it as a secret). pydantic then tried
        `int("")` at import time and the whole backend failed to load — the install stopped at its own
        verification step, on the default it ships. An empty numeric setting is "leave it alone" for every
        person who will ever edit this file by hand, so it is normalised here rather than there.
        """
        if value is None:
            return 100_000
        if isinstance(value, str) and not value.strip():
            return 100_000
        return value

    # THE STARTUP SYSTEM-SWEEP (2026-09-12) — OPT-IN, OFF BY DEFAULT.
    # The sweep itself is deterministic: no LLM, no agent call (the
    # system-audit graph's nodes are plain functions and the Exa
    # distributor only writes a markdown file into the workspace inbox).
    # But it is scheduled at BOOT, and under `--reload` a boot follows
    # every file save — so each edit produced a "System Sweep complete"
    # toast plus a second toast when the inbox processor cleared the
    # queue it had just filled. During development that is a stream of
    # notifications about a system nobody is changing.
    #
    # Run it on demand instead — the sweep was always user-runnable:
    #     POST /api/v1/workflows/execute  {"workflow_id": "system-audit"}
    # or from the Workflows page (WorkflowRunner handles system-audit).
    # Set STARTUP_SWEEP_ENABLED=true to restore the boot-time sweep.
    startup_sweep_enabled: bool = False

    # EXA'S BACKGROUND PROCESSING (2026-09-12) — the workspace DRAIN,
    # OPT-IN, OFF BY DEFAULT.
    # The recurring loop that clears .exa-workspace/inbox/ (moving each
    # report to system-reports/ and toasting only when a report carries a
    # **warning**). This is the consumer end of the flow documented in
    # local/dev/testing_policy.md: a run produces a report → the report is
    # filed into Exa's inbox → Exa's queue-clearing reads and triages it.
    #
    # Off by default because while testing, an inbox that is continuously
    # emptied and announced is noise, and nothing is waiting on it.
    # NOTE THE COUPLING: with this off, anything that FILES into the inbox
    # accumulates instead of being drained. The startup sweep honours that
    # (see main.py — it will not schedule if this is off), and the
    # on-demand log sweep (POST /api/v1/system/sweep/log) still files by
    # hand, by user choice.
    exa_background_processing_enabled: bool = False

    # ============================================================================
    # Database Configuration
    # ============================================================================
    # 
    # CRITICAL: Use absolute paths based on BASE_DIR, NOT relative paths.
    # Relative paths (e.g., "./cogitate.db") resolve from the working directory,
    # which changes when cogitate.sh does 'cd "$BACKEND_DIR"'.
    #
    # Canonical locations:
    #   - Main DB: project_root/cogitate.db
    #   - Docs DB: project_root/data/cogitate_docs_en.db
    # ============================================================================
    
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/cogitate.db"
    documents_database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/cogitate_docs_en.db"
    db_echo: bool = False

    # CORS. The dev-server origins we expect. The launcher EXPORTS
    # COGITATE_FRONTEND_PORT, and `_with_configured_frontend_port` below adds
    # that origin to whatever is listed here — so running on another port does
    # not silently break the browser with a CORS rejection that looks like a
    # network fault. (The list already carried 5174, so a second port was
    # anticipated; this makes it follow the configured one.)
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_origins")
    @classmethod
    def _with_configured_frontend_port(cls, v: list[str]) -> list[str]:
        """Always allow the port the launcher actually started the dev server on.

        An env-set origin is added, never substituted: the defaults stay, so a
        browser on the house port keeps working even when COGITATE_FRONTEND_PORT
        points somewhere else.
        """
        import os

        port = os.environ.get("COGITATE_FRONTEND_PORT")
        if not port:
            return v
        for host in ("localhost", "127.0.0.1"):
            origin = f"http://{host}:{port}"
            if origin not in v:
                v = [*v, origin]
        return v
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # LiteLLM Configuration
    litellm_master_key: str = ""
    # THE RETIRED MODEL LITERALS (the capability arc's phase 4, C2). These two knobs
    # used to default to `"ollama"` and `"llama3.2"` — a provider AND a model named in
    # code, pointing at a service that is not running — and were read as the system
    # manager's model and by the POST checks' evidence. Both are empty now: NO model
    # name is written in code, and "which service answers this?" is a capability's
    # answer (`capabilities.<KEY>`), or the row that actually serves the model.
    default_llm_provider: str = ""
    default_llm_model: str = ""

    # Ollama (default provider) — the address is deliberately NOT a setting. It is a provider ROW's
    # `base_url`, resolved by `provider_endpoints.resolve_endpoint` (the service-literals arc: an
    # address the app dials is a DECISION, so the row carries it; a field here would be the second home
    # this arc removes). See `wiki/issues/resolved/embedded-service-literals/local-embedding-server.md` — RULED, option C, staged.
    # (Retired 2026-10-10 from `ollama_base_url: str = "http://localhost:11434"`.)

    # OpenAI (optional)
    openai_api_key: str = ""

    # Anthropic (optional)
    anthropic_api_key: str = ""

    # OpenRouter (optional)
    openrouter_api_key: str = ""

    # Deepseek (optional)
    deepseek_api_key: str = ""

    # Groq (optional - OpenAI-compatible)
    groq_api_key: str = ""

    # Ollama Cloud (hosted OpenAI-compatible API at https://ollama.com/v1)
    ollama_cloud_api_key: str = ""

    # Tavily (optional - web search tool)
    tavily_api_key: str = ""

    # Langfuse observability (optional — where workflow/chat traces are sent)
    # Field names match the .env vars LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY /
    # LANGFUSE_BASE_URL / LANGFUSE_TRACING_ENVIRONMENT / LANGFUSE_TRACING_ENABLED
    # (case-insensitive lookup). They are declared here so the adapter can ask the app's own
    # configuration object rather than the environment — and because the environment cannot be
    # trusted to be empty: litellm calls `load_dotenv()` at import time, so the whole `.env` is
    # copied into `os.environ` in any process that touches the providers layer. The adapter asks
    # this object FIRST and the environment second, so a declaration wins over that copy.
    #
    # `langfuse_base_url` is the SDK's CURRENT name for the destination; `langfuse_host`
    # is DEPRECATED and kept as the fallback so an .env written against the old name
    # still works. Passing the wrong one is not cosmetic: the SDK falls back to
    # cloud.langfuse.com, so a regional installation (us./eu.) silently ships every
    # trace to the wrong host.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = ""
    langfuse_host: str = ""
    langfuse_environment: str = ""
    langfuse_tracing_enabled: bool | None = None

    # API Key Encryption (Phase 4)
    # Field name matches the .env var COGITATE_ENCRYPTION_KEY (case-insensitive
    # lookup) — was `encryption_key`, which never populated from .env
    # (pydantic looked for ENCRYPTION_KEY). Fixed 2026-08-03.
    cogitate_encryption_key: str = ""  # 32-byte key for Fernet encryption

    # Model Sync (Phase 4)
    default_sync_interval_hours: int = 168  # 7 days

    # ============================================================================
    # File Upload
    # ============================================================================
    
    max_upload_size: int = 5 * 1024 * 1024  # 5MB
    max_sound_upload_size: int = 2 * 1024 * 1024  # 2MB (notification sounds are tiny)
    
    # CRITICAL: Use absolute path based on BASE_DIR
    allowed_image_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    ]
    allowed_sound_types: list[str] = ["audio/wav", "audio/x-wav", "audio/wave"]
    profile_images_dir: str = str(BASE_DIR / "data" / "profile_images")

    # ============================================================================
    # Logging
    # ============================================================================
    
    # The application's log level, and the ONE place it is set: both handlers in
    # logging_config.py now follow it rather than carrying their own hardcoded
    # values. It defaulted to DEBUG, which is a flood in normal use — one run
    # wrote 144 MB to the console capture alone. DEBUG stays available by setting
    # LOG_LEVEL in the environment when it is actually wanted.
    log_level: str = "INFO"
    # CRITICAL: Use absolute path based on BASE_DIR
    log_file: str = str(BASE_DIR / "backend" / "logs" / "app.log")
    # The local llama.cpp GGUF, if one is served. Empty = the provider's own
    # default. This was a literal absolute path in the provider catalog, which
    # named one developer's home directory and worked nowhere else.
    llama_model_path: str = ""

    # Cache (in-memory for MVP)
    cache_ttl_seconds: int = 300  # 5 minutes


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Using lru_cache ensures we only load settings once,
    then reuse the same instance throughout the app lifecycle.

    Returns:
        Settings: Application settings instance
    """
    return Settings()
