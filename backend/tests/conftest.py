"""
Pytest configuration and fixtures.

Provides reusable fixtures for testing including:
- Test database
- Test client
- Database override for isolation
- Auto‑cleanup between tests to prevent ordering interference
- Litellm log-noise suppression at shutdown
"""

import atexit
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import warnings
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── THE TEST ROOT (the isolation fix) ───────────────────────────────────────
# Everything the application resolves from settings is redirected into ONE
# temporary directory, and it is set BEFORE the app is imported. That ordering
# is the whole point: the database engine is built at import time from
# settings.database_url, so setting it afterwards would leave AsyncSessionLocal
# bound to the production database.
#
# `Paths.from_settings` derives the installation root from the shared database's
# location, so aiming DATABASE_URL here moves the agents root, the data
# directory (pipeline traces), the logs and the Exa workspace with it. The wrong
# path becomes impossible rather than being cleaned up afterwards.
# A PARENT-WALK TO SOURCE is legitimate (to DATA is the defect): this locates the
# project's own wiki/ so a faithful copy can be placed in the installation.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

TEST_ROOT = tempfile.mkdtemp(prefix="cogitate-test-")

# THE TRASH FOLLOWS THE INSTALLATION TOO. `Paths.trash_dir` is a CLASS-level
# default (BASE_DIR/trash), while every other path is read through
# `Paths.from_settings` — so the redirect above moved the agents root and the
# data dir but left the trash pointing at the real one. A test that deletes an
# agent would drop its workspace into the operator's own trash, which is exactly
# the class of leak this arc exists to remove. Pointing the single class
# attribute at the installation fixes it for every reader, including the
# locator's `trash_dir_for`.
from app.core.config import Paths as _Paths  # noqa: E402

_Paths.trash_dir = Path(TEST_ROOT) / "trash"

# The installation must be FAITHFUL, not merely isolated. `Paths.wiki_dir`
# resolves inside TEST_ROOT, so without this the wiki endpoints 404 for a reason
# that has nothing to do with the code (test_delete_wiki_regression). The database
# is copied for the same reason. Copy, not symlink: a test must not be able to
# write into the real wiki/.
_source_wiki = os.path.join(_PROJECT_ROOT, "wiki")
if os.path.isdir(_source_wiki):
    shutil.copytree(_source_wiki, os.path.join(TEST_ROOT, "wiki"), dirs_exist_ok=True)

# The SAME faithfulness for the skill library. `Paths.skills_dir` resolves inside
# TEST_ROOT too, so a test that loads a project skill found nothing — the banked
# `test_skill_aware_cb::test_load_global_skill` failed for a reason that had
# nothing to do with the loader: `skills/web-research.skill.md` exists in the
# repo, and the installation simply did not carry it. 320 KB beside a 4.4 MB wiki.
_source_skills = os.path.join(_PROJECT_ROOT, "skills")
if os.path.isdir(_source_skills):
    shutil.copytree(_source_skills, os.path.join(TEST_ROOT, "skills"), dirs_exist_ok=True)
_TEST_DB_PATH = os.path.join(TEST_ROOT, "cogitate.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"

# THE SHARED-DB CLASS ATTRIBUTE FOLLOWS THE INSTALLATION TOO — the same fix as
# the trash above, and the one that was missing. `DATABASE_URL` moves everything
# resolved through `Paths.from_settings`, but `Paths.shared_db` is also read as a
# CLASS attribute (`live_db_path`, and several tests that open it with raw
# sqlite3). Those readers were opening the operator's PRODUCTION database — and
# on a clean clone, where it does not exist, they raised FileNotFoundError
# instead of testing anything.
_Paths.shared_db = Path(_TEST_DB_PATH)

# THE TEST KEY. A clean clone has no `.env`, and `EncryptionService` refuses to
# construct without `COGITATE_ENCRYPTION_KEY` — 30 tests died on exactly that in a
# flattened tree. A fixed, obviously-fake Fernet key is set ONLY when the machine
# has none, so a developer's own key still wins. (A clean INSTALL has no key
# either; that is a product question — first-run generation — not a test one.)
os.environ.setdefault(
    "COGITATE_ENCRYPTION_KEY", "dGVzdC1rZXktbm90LWEtc2VjcmV0LTMyLWJ5dGVzISE="
)
os.environ["DOCUMENTS_DATABASE_URL"] = (
    f"sqlite+aiosqlite:///{os.path.join(TEST_ROOT, 'documents.db')}"
)

# THE IMAGE STORE. `profile_images_dir` is a STRING setting, not a `Paths` field, so
# `from_settings` does NOT move it with the installation — a test that writes an agent's
# face would write into the operator's store instead of the test's. Env is the only way
# in (no prefix, `case_sensitive=False`), so it is set here, before the settings load.
os.environ["PROFILE_IMAGES_DIR"] = os.path.join(TEST_ROOT, "data", "profile_images")

from app.core.config import BASE_DIR

from app.main import app
from app.core.database import Base, get_db_session
from app.core.dependencies import get_documents_db, get_db
from app.infrastructure.database.models import Provider


# ---------------------------------------------------------------------------
# Suppress litellm "I/O operation on closed file" noise at pytest shutdown.
# The underlying httpx client's transport is garbage-collected before the
# stream/logging infrastructure is torn down, producing a benign traceback
# in litellm/llms/custom_httpx/http_handler.py.
# ---------------------------------------------------------------------------
def _silence_litellm_io_noise() -> None:
    """Quieten the litellm http-handler logger to ERROR only."""
    for name in (
        "litellm.llms.custom_httpx.http_handler",
        "litellm.llms.custom_httpx",
        "litellm",
    ):
        logger = logging.getLogger(name)
        logger.setLevel(logging.ERROR)
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())


_silence_litellm_io_noise()

# Import all models to ensure they are registered with Base.metadata
# This is required for create_all() to work correctly


# Import collections models

# Use temporary file-based SQLite for more reliable testing
# In-memory SQLite has connection sharing issues with multiple session factories

# The database lives inside TEST_ROOT, beside the agent workspaces, data
# directory and logs it belongs to — so one removal clears the lot.
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"


class TestInstallationLeakWarning(UserWarning):
    """The temporary test installation survived its teardown.

    Raised (never swallowed) when `_cleanup_test_db()` could not remove
    TEST_ROOT. It is a warning and not an error on purpose: a run whose tests
    all passed did not fail because the sandbox would not go — but the LEAK is
    a fact about the run, and a fact nothing prints is a fact nobody fixes.
    """


# The roots already named by a leak warning in this process — see the guard in
# `_cleanup_test_db`.
_leaks_reported: set[str] = set()


def _cleanup_test_db() -> None:
    """Remove the whole temporary installation — and SAY SO when it will not go.

    `ignore_errors=True` alone was the silence. A removal that fails — a writer
    still holding a file, a directory that will not yield, an open WAL — left
    the sandbox behind and reported nothing, so 57 roots and 248 MB had
    accumulated in /tmp before anyone counted them.

    The removal stays best-effort; what changes is that it is READ BACK. The
    first refusal names the path it stopped at, the survivors are listed, and
    the whole thing goes out as a warning — a visible event in the run's own
    output. A warning is the channel that also survives `-n auto`: pytest
    relays a worker's warning into the controller's summary, which is where
    report.md picks it up.

    Called twice by design (the engine fixture's teardown, then interpreter
    exit); a root already reported is not reported again.
    """
    held: str | None = None
    try:
        # No ignore_errors here: the FIRST refusal is what names the holder.
        shutil.rmtree(TEST_ROOT)
    except FileNotFoundError:
        return  # already gone — the ordinary, healthy case
    except Exception as exc:
        held = getattr(exc, "filename", None) or str(exc)
        # Finish what can be done, so what is listed below is the real
        # survivors rather than everything after the first refusal.
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    if not os.path.exists(TEST_ROOT):
        return

    # Once per root per process. The teardown names it and the exit retry would
    # name it a second time, from `<sys>:0` — where the warnings registry cannot
    # dedupe it, so the guard has to.
    if TEST_ROOT in _leaks_reported:
        return
    _leaks_reported.add(TEST_ROOT)

    leftovers = sorted(
        os.path.relpath(os.path.join(dirpath, name), TEST_ROOT)
        for dirpath, _dirs, names in os.walk(TEST_ROOT)
        for name in names
    )
    if leftovers:
        detail = f"{len(leftovers)} file(s) left: {', '.join(leftovers[:10])}"
        if len(leftovers) > 10:
            detail += ", ..."
    else:
        # Nothing reachable inside — name the entries themselves rather than
        # report a leak that names nothing.
        try:
            entries = sorted(os.listdir(TEST_ROOT))
        except OSError as exc:
            entries = [f"<unreadable: {exc}>"]
        detail = f"nothing reachable inside; entries: {', '.join(entries[:10])}"

    warnings.warn(
        f"the test installation {TEST_ROOT} survived its teardown"
        + (f" — the removal stopped at {held}" if held else "")
        + f". {detail}\n"
        "      Something was still holding it (a writer, an engine, a subprocess).\n"
        "      The next run gets its own root and this one stays — a leak, not a\n"
        "      one-off. Reproduce with the same file/engine opened at teardown.",
        TestInstallationLeakWarning,
        stacklevel=2,
    )


# THE SECOND LEAK PATH, and the commoner one. `_cleanup_test_db` used to be
# called ONLY from the engine fixture's teardown — so a process that imported
# this conftest and never instantiated that fixture (a `--collect-only`, the
# xdist CONTROLLER, any worker whose tests needed no database) created a root
# at import and no code path ever removed it. Measured: one `--collect-only`
# run of tests/unit left a 4.9 MB root behind, every time — which, not the
# failed removal, is how 57 roots accumulated. Registering the cleanup with
# the interpreter closes it for every process that ever imported this file;
# the fixture teardown still fires first on the ordinary path, and the second
# call finds nothing to do.
atexit.register(_cleanup_test_db)


@pytest_asyncio.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio backend for async tests."""
    return "asyncio"


def _seed_test_db_from_a_real_one() -> None:
    """Start the test database as a COPY of a real, migrated database.

    WHY A COPY, and not `create_all` or `upgrade head`:

    - The ORM metadata is NOT the whole schema. Sixteen tables exist only in
      migrations (`tools`, `workflow_templates`, `workflow_kinds`,
      `agent_tools`, `prompt_templates`, ...) plus the rows they SEED, which
      tests assert on — "the nine canonical workflow kinds" is a migration's
      output, not any model's.
    - The migration chain cannot build a database from nothing. Its early steps
      ALTER tables that only `create_all` creates ("no such table: agents"),
      and running it after `create_all` re-adds columns those tables already
      have ("duplicate column name: parameters"). It is a forward-only history
      from a schema created at some past moment, not a from-empty script.
    - Without the copy, code reading those tables falls through to the
      PRODUCTION database **without failing** — a suite that passes while
      silently reading live data, and keeps passing after the schema it depends
      on has changed.

    The copy is faithful AND isolated: the suite reads and writes the copy, and
    production is never opened for writing. `sqlite3`'s backup API is used
    rather than a file copy because the source runs in WAL mode.
    """
    import sqlite3 as _sqlite3

    src = Path(BASE_DIR) / "cogitate.db"
    if not src.exists():
        return  # a fresh checkout with no database yet: `create_all` still runs

    # THE SANDBOX IS COPIED FROM THE LIVE DATABASE, BY DESIGN — so this one
    # connection to it is not a breach of the contract the guard enforces, it is
    # the step the isolation depends on. `_PROVISIONING` (see the guard's raw
    # sqlite3 wrapper) closes the recording window for exactly this read and no
    # other: every later raw open of the live database is still reported.
    global _PROVISIONING
    _PROVISIONING = True
    try:
        src_con = _sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        dst_con = _sqlite3.connect(_TEST_DB_PATH)
        try:
            with dst_con:
                src_con.backup(dst_con)
        finally:
            dst_con.close()
            src_con.close()
    finally:
        _PROVISIONING = False


_FIXTURES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "cogitate_fixtures.json")

#: Parents before children — the reference rows are inserted in this order.
_FIXTURE_ORDER = (
    "workflow_kinds",
    "tool_categories",
    "tools",
    "workflow_templates",
    "workflow_compositions",
    "agents",
    "agent_tools",
    "workflow_triggers",
    "macro_sets",
    "collections",
    "collection_items",
    "curated_models",
)


def _load_reference_rows(target: str | None = None) -> None:
    """Put the reference rows into a database that has none.

    The sandbox has two possible origins, and both keep working:

    - **copied from a real database** (this machine) — the rows are already
      there, and every table is skipped;
    - **built by `create_all`** (a clean clone, no `cogitate.db`) — the tables
      exist and are empty, and the rows come from
      `tests/fixtures/cogitate_fixtures.json`, which is what the suite asserts
      on: the kinds catalog, the 36 workflow templates, the demo compositions,
      the tool registry, the kits and the curated models.

    Missing-rows-only, so a copied sandbox is never rewritten. Regenerate the
    file with `scripts/testing/export_test_fixtures.py`.
    """
    import json
    import sqlite3 as _sqlite3

    if not os.path.exists(_FIXTURES_PATH):
        return  # a tree that predates the fixtures: the copy path still works
    with open(_FIXTURES_PATH, encoding="utf-8") as handle:
        payload = json.load(handle)
    tables = payload.get("tables", {})

    connection = _sqlite3.connect(target or _TEST_DB_PATH)
    try:
        for table in _FIXTURE_ORDER:
            rows = tables.get(table) or []
            if not rows:
                continue
            exists = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            if not exists:
                continue
            if connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]:
                continue
            columns = sorted(rows[0].keys())
            placeholders = ", ".join(f":{name}" for name in columns)
            column_list = ", ".join(f'"{name}"' for name in columns)
            connection.executemany(
                f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})', rows
            )
        connection.commit()
    finally:
        connection.close()


def reload_reference_rows() -> None:
    """Put the fixture's reference rows back into the test database.

    `auto_clean_tables` truncates every ORM table after each test, and only the
    three in `_SEEDED_TABLES` are exempt. Everything else the fixtures carry —
    the tool registry, the kits, the curated models, the collections — is gone
    after the first test a worker runs. A test that NAMES one of those rows
    (a registry id, a curated model id) therefore sees an empty table, and its
    verdict moves with xdist's distribution: green as the first test in a
    worker, red in every one that has already run something.

    THE FIX IS THE FIXTURE, NOT A PRIVATE COPY. Call this from a module-level
    autouse fixture in any module whose tests name fixture content (see
    `tests/workflows/test_multi_agent_tools.py`); nothing recreates those rows
    otherwise. Missing-rows-only, like the loader it wraps: a table that still
    has rows is left alone, so a copied database is never rewritten.
    """
    _load_reference_rows()


def _provision_test_db() -> None:
    """Guarantee the sandbox EXISTS before any test touches it.

    Plenty of tests open `sqlite3.connect(Paths.shared_db)` directly, and some
    fixtures copy the database — neither goes through `test_engine`, so the file
    has to be there at import time. Two origins, same as the loader: a copy of a
    real database when this machine has one, else `create_all` from the models
    plus the reference fixtures (a clean clone).
    """
    from sqlalchemy import create_engine

    _seed_test_db_from_a_real_one()
    if os.path.exists(_TEST_DB_PATH):
        return
    engine = create_engine(f"sqlite:///{_TEST_DB_PATH}")
    Base.metadata.create_all(engine)
    engine.dispose()
    _load_reference_rows()


async def get_or_create_provider(session, *, name: str, **fields) -> "Provider":
    """The provider row named `name` — the COPIED database usually carries one already.

    THE COPY IS THE POINT. `_seed_test_db_from_a_real_one` starts the sandbox as a copy of the
    operator's installation, so a fixture that INSERTs a provider called `ollama`, `openrouter`
    or `ollama_cloud` meets that installation's own row as
    `UNIQUE constraint failed: providers.name`. A fixture's insert arrives as an ERROR at SETUP
    (the test body never runs); a test that inserts its own row fails inside the test. Either
    way it fires for the FIRST test function a worker runs, because `auto_clean_tables`
    truncates after that first function and every later test inserts cleanly — so which file
    that is depends on xdist's distribution, the same code is green in one run and red in the
    next, and a run's SUMMARY LINE (`2 passed, 1 error`) hides it. Read a run's ERROR lines, not
    only its FAILED list.

    REUSE-OR-CREATE, and the fields the caller names are RESTATED on the row it finds: the
    caller controls every value it declares, and the row keeps its id — so the curated entries,
    capability bindings, sync schedules and cache rows hanging off it stay attached. The row is
    FLUSHED before it is returned, so `row.id` is usable at once.

    THE SAME RULE ONE LEVEL DOWN FOR `curated_models`: `uq_curated_provider_model` makes
    (provider_id, model_id) unique, so a test that states a curated row for a NAMED provider
    clears that provider's rows first — see the two ollama_cloud files.

    Usage: `from tests import conftest as cf`, then
    `await cf.get_or_create_provider(session, name="ollama", base_url=...)`.
    """
    row = (
        await session.execute(select(Provider).where(Provider.name == name))
    ).scalar_one_or_none()
    if row is None:
        row = Provider(name=name, **fields)
        session.add(row)
    else:
        for field, value in fields.items():
            setattr(row, field, value)
    await session.flush()
    return row


# Provision at import, before any test: raw `sqlite3` reads and the fixtures that
# copy the database do not go through `test_engine`.
_provision_test_db()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create the test database and its engine."""
    # A copy of a real database when this machine has one, else create_all +
    # the reference fixtures — `_provision_test_db` has already run at import;
    # this keeps the copied path fresh for a session and adds anything the copy
    # predates (a newly added model), plus the FTS5 virtual table the ORM
    # cannot declare.
    _seed_test_db_from_a_real_one()

    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    # `create_all` on top adds anything the copy predates (a newly added
    # model), and the FTS5 virtual table the ORM cannot declare.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        await conn.run_sync(_create_fts5_table)

    # The reference rows the suite asserts on: skipped when the sandbox was
    # copied from a real database, inserted when create_all built it from
    # nothing (a clean clone).
    _load_reference_rows()

    yield engine

    # Cleanup — dispose the engine and remove the whole temporary installation.
    await engine.dispose()
    _cleanup_test_db()


def _create_fts5_table(conn):
    """Create the documents_fts virtual table and triggers (sync helper)."""
    from sqlalchemy import text

    # Create FTS5 virtual table
    conn.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title,
            content,
            summary,
            keywords,
            search_keywords,
            slug,
            category,
            subtopic,
            doc_type,
            context
        )
    """))

    # Create triggers to keep FTS index in sync
    conn.execute(text("""
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(
                rowid, title, content, summary, keywords, search_keywords,
                slug, category, subtopic, doc_type, context
            ) VALUES (
                NEW.id, NEW.title, NEW.content, NEW.summary, NEW.keywords,
                NEW.search_keywords, NEW.slug, NEW.category, NEW.subtopic,
                NEW.doc_type, NEW.context
            );
        END
    """))

    conn.execute(text("""
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            UPDATE documents_fts SET
                title = NEW.title,
                content = NEW.content,
                summary = NEW.summary,
                keywords = NEW.keywords,
                search_keywords = NEW.search_keywords,
                slug = NEW.slug,
                category = NEW.category,
                subtopic = NEW.subtopic,
                doc_type = NEW.doc_type,
                context = NEW.context
            WHERE rowid = NEW.id;
        END
    """))

    conn.execute(text("""
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            DELETE FROM documents_fts WHERE rowid = OLD.id;
        END
    """))


@pytest_asyncio.fixture(autouse=True, scope="function")
async def auto_clean_tables(test_engine) -> AsyncGenerator[None, None]:
    """Truncate all ORM-managed tables after each test function.

    Prevents cross-test data contamination caused by the session-scoped
    ``test_engine`` fixture.  Every test starts with a clean database.

    FTS virtual tables are managed by triggers on the real tables, so
    deleting from the parent table cascades correctly.  Auto-increment
    counters are reset when the ``sqlite_sequence`` table exists.
    """
    # Let the test run first
    yield

    # THE SETTINGS-CACHE CHECK (2026-09-25 — the cross-group interference, root-caused).
    #
    # `get_settings` is `@lru_cache`d, and a test that points DATABASE_URL at a
    # database of its own (test_provisioning does, deliberately) must clear that
    # cache to be heard. `monkeypatch` restores the ENV VAR afterwards, but the
    # CACHED settings object is not on monkeypatch's list — so it survives the
    # test still naming the throwaway database, and every later test in the same
    # xdist worker resolves the shared database from it. Those victims then fail
    # with `no such table: workflow_templates` / `workflow_compositions` /
    # `workflow_triggers` / `ab_test_configs` — the migration-only tables that
    # only the real database carries. That is the whole of the "cross-group
    # interference": passing alone, passing in `--group unit` (few victims share
    # the worker), failing in `--group all` (the workflow tests land there).
    #
    # So: name the test that left it poisoned, then always clear — the check
    # catches the instance, the clear stops the class.
    from app.core.config import get_settings as _get_settings

    # THE AVAILABILITY MEMO (2026-10-05 — phase 6, group 5). The probe memo is IN-PROCESS and
    # keyed by provider id, so a state one test read would answer the next test's row (the same ids
    # are recreated from the clean database) without any probe happening. Same class as the
    # settings cache below: `monkeypatch` cannot see it, so the fixture clears it.
    from app.domain.providers import availability as _availability

    _availability.clear_cache()
    # The NETWORK verdict's observation window is IN-PROCESS too (2026-10-14, the bridge's seam 2):
    # same class as the memo above — a call one test observed would corroborate the next test's
    # failure, and `monkeypatch` cannot see it.
    _availability.clear_observations()

    poisoned: str | None = None
    try:
        live = str(_get_settings().database_url)
        if live != TEST_DATABASE_URL:
            poisoned = live
    except Exception:
        pass  # a settings object this test could not build is not this check's business
    _get_settings.cache_clear()

    async with test_engine.begin() as conn:
        # Delete rows from all tables (reverse order handles FK constraints).
        # Tables whose rows are SEEDED CONTENT are skipped — see _SEEDED_TABLES
        # below: they are ORM-registered now, but nothing recreates their rows.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in _SEEDED_TABLES:
                continue
            await conn.execute(table.delete())

        # THE MIGRATION-ONLY TABLES need this too, and they split two ways:
        #
        #   runtime RECORDS — history, logs, approval state — must be cleared,
        #   or one test's rows and the COPY's inherited rows leak into the next
        #   (a prune test asserting `pruned == 0` saw 19 old executions from the
        #   database the copy was taken from);
        #
        #   SEEDED content — the canonical workflow kinds, the templates, the
        #   tool registry — must SURVIVE, because tests assert against it and
        #   nothing else recreates it.
        for table_name in _CLEANED_BY_HAND:  # the same list the guard reads
            try:
                await conn.execute(text(f'DELETE FROM "{table_name}"'))
            except Exception:
                pass  # absent in a schema that predates it
        # Reset auto-increment counters (no-op if sqlite_sequence absent)
        try:
            await conn.execute(text("DELETE FROM sqlite_sequence"))
        except Exception:
            pass

    # Raised LAST, so the cleanup above always runs: the test is named, not the
    # tests that would have been its victims.
    if poisoned:
        raise AssertionError(
            "this test left the settings cache pointing at another database:\n"
            f"      get_settings().database_url = {poisoned}\n"
            f"      the suite's own =             {TEST_DATABASE_URL}\n"
            "    `monkeypatch` restores the ENVIRONMENT VAR but not the `lru_cache`d settings\n"
            "    object, so every later test in this worker would have read that database —\n"
            "    which is the whole of the cross-group interference (the migration-only tables\n"
            "    are missing from a database the test built for itself). Clear it on the way out\n"
            "    as well as on the way in:\n"
            "      get_settings.cache_clear()\n"
            "    This autouse fixture clears it too, so the next test is safe either way."
        )


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Create test HTTP client.

    Overrides database dependency to use test database.
    Also overrides documents database dependency to use the same test database.
    """
    # Override main database dependency — mirrors production get_db_session()
    # which auto-commits after each request.
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async_session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Override documents database dependency — mirrors production
    # get_documents_session() which auto-commits after each request.
    async def override_get_documents_db() -> AsyncGenerator[AsyncSession, None]:
        async_session_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_documents_db] = override_get_documents_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

import pytest

# ── THE BACKEND-DEPENDENT TIER (2026-08-27, the development
#    decision in local/test-sweeps-redesign/03-progress.md):
#    skip + warn by default, --require-backend for the strict runs.
#    The pre-flight lives in the HARNESS (run_tests.py), not the
#    test-order — the ordering is a known issue. ────────────────


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "backend: requires a running backend (skips when it is down)",
    )
    config.addinivalue_line(
        "markers",
        "quarantine: the parked problem-children (04-quarantine.md) — "
        "excluded from the groups by default",
    )
    config.addinivalue_line(
        "markers",
        "live: requires a live external service (an LLM provider, Ollama, a "
        "remote API) — skips with a reason when it is absent",
    )
    config.addinivalue_line(
        "markers",
        'external(name): requires something OUTSIDE the project\'s control, '
        'naming WHICH dependency — @pytest.mark.external("ollama"). The name is '
        "matched against EXTERNAL_PROBES; an unregistered name FAILS the test "
        "rather than passing it. Supersedes `live`, which named one instance.",
    )
    config.addinivalue_line(
        "markers",
        "shared_db: this test uses the shared test database in a way the guard "
        "cannot undo — it stands up a database of its own, or it leaves rows "
        "behind for its siblings. Say WHICH in the test's docstring. See THE "
        "SHARED-DB GUARD below for what the marker waives.",
    )


# ── THE SHARED-DB GUARD — `@pytest.mark.shared_db` (TIGHTENING, level (b)) ────
#
# THE PROBLEM IT EXISTS FOR. A worker process runs every test it is handed
# against ONE database: `test_engine` copies a real, migrated database into
# TEST_ROOT, and `auto_clean_tables` truncates the ORM tables between tests. So a
# test that depends on database state it did not create gets whatever the
# previous test in its worker left behind, or whatever the copy happened to
# carry — and its verdict moves with the DISTRIBUTION of tests across workers.
# That is the class behind "one unchanged tree gave 1, then 3, then 1 failure"
# (three group runs, measured 2026-09-24) and behind the modules that pass alone
# and fail inside a group.
#
# WHAT IT CHECKS — two things, both mechanical:
#
#   1. OFF THE RAILS. The test ran SQL against a database OUTSIDE the test
#      installation — a file of its own, or (the one that matters most) the
#      PRODUCTION database, which is the failure the whole copy step exists to
#      prevent. A private database cannot see the migrated schema or the seeded
#      rows, so nothing it asserts is shared with any other test: it is a
#      private experiment wearing the suite's clothes. `:memory:` is exempt —
#      isolated by construction, and unable to touch anything on disk.
#   2. LEAKED STATE. The test left rows in a table NOTHING cleans — one with no
#      ORM model that `auto_clean_tables` also does not name. Those rows outlive
#      the test for the life of the worker, so the NEXT test reads them. The
#      failure names the tables and the delta, and blames the test that WROTE
#      them, not the one that happened to notice.
#
# WHAT IT DELIBERATELY DOES NOT CHECK: reads. Reading the seeded baseline — the
# canonical workflow kinds, the templates, the tool registry, the rows the
# migrations insert — is the whole reason the copy exists. A guard that demanded
# a declaration for every database touch would be satisfied by one mass edit and
# would stop carrying information. (Checked, not assumed: `test_engine` is in
# every test's fixture closure already, because the autouse cleanup requests it,
# so "fail the test that never requested the provisioning fixture" would have
# been a guard that could never fire.)
#
# THE DECLARATION: `@pytest.mark.shared_db` on a test that deliberately does
# either of the two things above. It waives both checks; the test's docstring
# should say which, so a reader learns that its neighbours are part of its
# contract.
#
# COST: one `SELECT COUNT(*)` per leak-prone table at setup and one at teardown,
# on two short-lived read-only connections, plus a dict lookup per query. It
# never fails a test for its OWN error — an unreadable count skips the check.
from sqlalchemy import event as _sa_event
from sqlalchemy.engine import Engine as _SaEngine

#: The four tables `auto_clean_tables` clears BY HAND (no ORM model to iterate).
#: A constant because the guard needs the same list to know what is ALREADY
#: cleaned — a second copy in the fixture would drift out of step silently.
_CLEANED_BY_HAND: tuple[str, ...] = (
    "workflow_execution_history",
    "workflow_approvals",
    "tool_usage_logs",
    "_sqlite_manager_audit_log",
)

#: Tables the per-test truncation must NOT touch: their rows are SEEDED content,
#: not test output, and nothing in the suite recreates them. They are ORM-registered
#: (so `create_all` builds them) but the rows still arrive with the database copy —
#: the canonical workflow kinds, the workflow templates, the demo composition.
_SEEDED_TABLES: frozenset[str] = frozenset(
    {
        "workflow_kinds",
        "workflow_templates",
        "workflow_compositions",
    }
)

#: The guard's window — one module-level global each, because pytest hooks have
#: no shared object to hang state on.
_recording = False
_off_rails: set[str] = set()
_start_counts: dict[str, int] | None = None
_call_passed: bool | None = None
_leak_prone: set[str] | None = None

#: Snapshots the guard could not take. Reported at the end of the session: a
#: guard that silently stopped checking is the failure mode this whole exercise
#: is about, so it does not get to have one.
_snapshots_missed = 0
_last_snapshot_error: str | None = None


class SharedDbGuardError(AssertionError):
    """A test broke the shared test database's contract (see the section above)."""


def _sqlite_read(sql: str) -> list[tuple]:
    """One short look at the test database — the guard's own eyes.

    READ-WRITE on purpose, despite only ever reading: a read-only connection
    cannot roll back a hot journal, so it fails exactly after a test that wrote
    — the moment the leak check matters most. Nothing here writes.
    """
    import sqlite3

    con = sqlite3.connect(_TEST_DB_PATH, timeout=5)
    try:
        return list(con.execute(sql))
    finally:
        con.close()


def _leak_prone_tables() -> set[str]:
    """The tables whose rows NOTHING clears between tests (computed once).

    Everything else is either an ORM table — `auto_clean_tables` truncates every
    one — or one of the four it names by hand. A row in one of THESE outlives
    the test that wrote it, and the next test in the worker reads it.

    The first call happens in the FIRST test's setup, which runs BEFORE the
    `test_engine` fixture copies the database in — so an empty (or absent)
    sqlite_master there is the normal state, not a verdict, and must not be
    cached. The set is computed once the database exists and then kept.
    """
    global _leak_prone
    if _leak_prone:
        return _leak_prone
    try:
        names = {r[0] for r in _sqlite_read("SELECT name FROM sqlite_master WHERE type='table'")}
    except Exception:
        return set()  # not provisioned yet — try again next test
    if not names:
        return set()
    # A table exempt from the truncation is still a table NOTHING clears: the
    # seeded ones are subtracted for the same reason they are skipped above.
    models = {t.name for t in Base.metadata.sorted_tables} - _SEEDED_TABLES
    _leak_prone = {
        n for n in names
        if not n.startswith("sqlite_") and n not in models and n not in _CLEANED_BY_HAND
    }
    return _leak_prone


def _row_counts() -> dict[str, int] | None:
    """The leak fingerprint: row counts for the tables nothing clears.

    A snapshot that cannot be taken is COUNTED, never swallowed: the count
    reaches the session summary, so a guard that has quietly stopped checking
    says so out loud. (It found this itself — the first version took the counts
    on a read-only connection, which fails after any writing test, so the leak
    check silently did not run.)
    """
    tables = _leak_prone_tables()
    if not tables:
        return None
    global _snapshots_missed, _last_snapshot_error
    for attempt in (1, 2):
        try:
            return {t: _sqlite_read(f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in sorted(tables)}
        except Exception as exc:
            _last_snapshot_error = f"{type(exc).__name__}: {exc}"
            if not Path(_TEST_DB_PATH).exists():
                return None  # the session is cleaning up after itself — nothing to check
            if attempt == 1:
                time.sleep(0.15)
    _snapshots_missed += 1
    return None


@_sa_event.listens_for(_SaEngine, "before_cursor_execute")
def _record_engine_use(conn, cursor, statement, parameters, context, executemany) -> None:
    """Note every database OUTSIDE the test installation that the test talks to.

    A listener on the Engine CLASS, not on one engine: the app builds its own
    engine at import, tests build others, and new ones can appear later.

    The line is drawn around TEST_ROOT, not around one file: the installation
    holds TWO databases (`cogitate.db` and `documents.db`) plus the wiki, the
    agent workspaces and the logs, and all of it is legitimately the suite's.
    Anything outside it is either a private database of the test's own — which
    cannot see the seeded baseline — or, far worse, the PRODUCTION database,
    which is the failure the copy step exists to prevent.
    """
    if not _recording:
        return
    try:
        database = conn.engine.url.database
    except Exception:
        return
    if not database or database == ":memory:":
        return
    try:
        outside = not str(Path(database).resolve()).startswith(str(Path(TEST_ROOT).resolve()))
    except Exception:
        return
    if outside:
        _off_rails.add(str(database))


# ── THE RAW-SQLITE HOLE — closed ────────────────────────────────────────────
# The listener above sees SQLAlchemy engines. The application ALSO opens PLAIN
# sqlite3 connections — the pipeline's usage logger, the tool registry's grant and
# delete readers, the audit services — and those never pass through
# `before_cursor_execute`. That is not a theoretical gap: it is where the rows came
# from. `executor.log_usage` resolved its target through `Paths.shared_db`, a
# dataclass FIELD DEFAULT (a fixed BASE_DIR/cogitate.db) that ignores DATABASE_URL,
# so every test that ran the pipeline INSERTED usage rows into the operator's LIVE
# database — 244 of them, over weeks — while every redirected path (agents, data,
# trash, logs) moved into TEST_ROOT. A guard watching engines alone saw none of it.
#
# One wrapper closes it. A plain connection outside the installation is off the
# rails for exactly the reason an engine is, and now says so in the same report.
_ORIGINAL_SQLITE3_CONNECT = sqlite3.connect

#: Closed by the suite's OWN provisioning — `_seed_test_db_from_a_real_one` copies
#: the live database into the sandbox, which means reading it. That read is the
#: isolation, not a breach of it, so it alone is exempt; the flag is set and
#: cleared around that one connection and nothing else reads it.
_PROVISIONING = False


def _recording_sqlite3_connect(database, *args, **kwargs):
    """`sqlite3.connect`, noting any open of the OPERATOR'S INSTALLATION.

    The line is drawn around the installation, not around TEST_ROOT — the same
    line the engine listener draws — but a raw connection needs one distinction
    the engine listener can make for free. An off-rails ENGINE means the app's
    own session factory resolved outside the sandbox: always a breach. A raw
    connection to a file the test itself created under pytest's `tmp_path` is a
    private experiment, isolated by construction like `:memory:`; the suite has
    ~70 of them, and flagging those would bury the ones that matter under a mass
    of declarations — the failure mode the guard's own notes warn about.

    So: under the project root and outside TEST_ROOT is the operator's
    installation — their database, their data directory — and that is a breach
    whatever opened it. `:memory:` and a `file:` URI are unwrapped the same way.
    """
    if _recording and not _PROVISIONING and database:
        target = str(database)
        path = target[5:].split("?", 1)[0] if target.startswith("file:") else target
        if path and path != ":memory:":
            try:
                resolved = str(Path(path).resolve())
                if (resolved.startswith(str(Path(_PROJECT_ROOT).resolve()))
                        and not resolved.startswith(str(Path(TEST_ROOT).resolve()))):
                    _off_rails.add(path)
            except Exception:
                pass  # unparseable target: not a verdict
    return _ORIGINAL_SQLITE3_CONNECT(database, *args, **kwargs)


sqlite3.connect = _recording_sqlite3_connect


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    """Open the guard's window before the test's own fixtures provision anything."""
    global _recording, _off_rails, _start_counts, _call_passed
    _recording = True
    _off_rails = set()
    _start_counts = _row_counts()
    _call_passed = None
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    global _call_passed
    report = yield
    if call.when == "call":
        _call_passed = report.passed
    return report


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Judge the test once its fixtures have torn down.

    The autouse cleanup tears down INSIDE this hook, so the post-yield point is
    the first moment the database is in the state the NEXT test will open it in.
    (A new-style wrapper, not `hookwrapper=True`: raising from an old-style
    wrapper's teardown produces a PluggyTeardownRaisedWarning instead of a clean
    failure.)

    Set ``SHARED_DB_GUARD_DEBUG=1`` to see what it saw for every test — the first
    thing to reach for when a failure looks like a false positive.
    """
    # The END snapshot is taken BEFORE the fixtures tear down, and judged after.
    # The watched tables are exactly the ones NO fixture clears, so the autouse
    # cleanup cannot change them — and taking it on this side also survives the
    # LAST test of a session, whose teardown finalizes the session fixtures and
    # deletes the whole test root. (Post-yield, that deletion made the leak check
    # silently skip the final test of every file — found by the guard's own test,
    # which is why that test exists.)
    end = _row_counts()
    yield
    global _recording
    _recording = False
    if os.environ.get("SHARED_DB_GUARD_DEBUG"):
        start_dbg = _start_counts or {}
        changed = {
            t: (start_dbg[t], end[t])
            for t in start_dbg
            if end and end.get(t) != start_dbg[t]
        }
        print(
            f"\n[shared-db guard] {item.name}: watched={len(_leak_prone_tables())} "
            f"start={'none' if _start_counts is None else len(_start_counts)} "
            f"end={'none' if end is None else len(end)} "
            f"changed={changed or 'nothing'} off_rails={sorted(_off_rails) or 'none'} "
            f"last_error={_last_snapshot_error}"
        )
    if item.get_closest_marker("shared_db"):
        return  # declared: both checks are waived
    if _call_passed is not True:
        return  # it already failed for its own reason — do not pile on

    problems: list[str] = []

    if _off_rails:
        listed = "\n".join(f"        {p}" for p in sorted(_off_rails))
        problems.append(
            "ran SQL against a database OUTSIDE the test installation:\n"
            f"{listed}\n"
            f"      the installation is {TEST_ROOT} — `cogitate.db` and `documents.db` live in it\n"
            "      Use the `client` / `test_session` / `test_engine` fixtures, which point at the\n"
            "      suite's own copy. If a database of its own is genuinely what the test needs,\n"
            "      declare @pytest.mark.shared_db and say why in the docstring."
        )

    if _start_counts and end:
        leaked = {t: (_start_counts[t], end[t]) for t in _start_counts if end.get(t) != _start_counts[t]}
        if leaked:
            listed = "\n".join(f"        {t}: {was} -> {now}" for t, (was, now) in sorted(leaked.items()))
            problems.append(
                "left rows in tables NOTHING cleans — the next test in this worker reads them:\n"
                f"{listed}\n"
                "      Clean up after yourself, or declare @pytest.mark.shared_db and name\n"
                "      the sibling that relies on the rows in the docstring."
            )

    if problems:
        raise SharedDbGuardError(
            f"{item.nodeid} broke the shared test database's contract:\n\n  - "
            + "\n\n  - ".join(problems)
        )


def pytest_terminal_summary(terminalreporter) -> None:
    """Say so when the guard could not check. A silent guard is the one failure
    mode it must not have."""
    if _snapshots_missed:
        terminalreporter.write_sep("=", "shared-db guard")
        terminalreporter.write_line(
            f"  {_snapshots_missed} database snapshot(s) could not be taken — "
            "those tests were NOT checked for leaked rows."
        )


def resolve_backend_available() -> bool:
    """Whether the backend is up — the `@pytest.mark.backend` tests' gate.

    THE RUNNER DECIDES FIRST. `scripts/testing/run_tests.py` probes the backend ONCE before pytest
    starts, while the machine is idle, and passes that answer in `COGITATE_BACKEND_UP`. Reading it
    here keeps the gate from disagreeing with the report's own header — and removes a LOAD
    AMPLIFIER: with `-n auto` every worker used to run its own probe inside the same second, so
    under a parallel start the 2s timeout lost the race and the SAME suite reported 8 skips on one
    run and 18 on the next (measured: the ten that flipped were exactly the `backend`-marked tests,
    while the runner's header still said "healthy").

    A bare `pytest` (no runner) probes for itself, with a timeout that tolerates a loaded box and
    one retry — a health check that turns load into a skipped test is worse than no check.
    """
    import os as _os
    import urllib.request

    override = _os.environ.get("COGITATE_BACKEND_UP")
    if override is not None:
        return override == "1"

    base = _os.environ.get("COGITATE_BACKEND_URL", "http://127.0.0.1:8000")
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(f"{base}/api/v1/health", timeout=5) as resp:
                return resp.status == 200
        except Exception:
            continue
    return False


@pytest.fixture(scope="session")
def backend_available() -> bool:
    """The session-frozen answer every `@pytest.mark.backend` test is gated on."""
    return resolve_backend_available()


@pytest.fixture(autouse=True)
def _skip_without_backend(request, backend_available):
    """Skip the backend-marked tests when the backend is down —
    the visible skip (the report counts it), never a silent pass
    and never a hang."""
    if request.node.get_closest_marker("backend") and not backend_available:
        pytest.skip("backend not running — the backend-dependent test skipped")


# ── THE LIVE TIER (2026-09-13, the test-harness roadmap Phase A) ──
#    Same contract as `backend` above: probe once, skip with a REASON.
#
#    A test that calls a real provider is not testing our code — it is
#    testing someone else's service and our credentials. Those can never
#    pass in CI and can never catch a regression in a code change, so they
#    must not sit in a sweep where their failure reads like a defect.
#
#    The skip is VISIBLE (the report counts it) — "a skip with a reason is
#    evidence; a pass by accident is a lie."


def _probe(url: str, timeout: float = 2.0) -> bool:
    """A fast reachability probe. Any failure means 'not available'."""
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def ollama_available() -> bool:
    """Is the LOCAL Ollama daemon reachable right now?

    Probe the SPECIFIC dependency, never "a provider exists somewhere".
    That distinction is the whole point of the tier, and getting it wrong
    is silent: a configured DeepSeek key answered "available" for a test
    whose handler calls Ollama for EMBEDDINGS, so the test ran and failed
    as though the code were broken. A remote chat key cannot embed.

    Tests needing a remote model should probe that provider explicitly.
    """
    return EXTERNAL_PROBES["ollama"]()


# ── THE EXTERNAL CLASS (THE EXTERNAL TRIAGE Phase A2) ──────────────────────
#
# THE CLASS IS DEFINED BY A QUESTION — *whose availability is it?* — and the
# answer must be "not ours". It was called `live` and that name WAS the bug the
# user found: "Ollama is too particular, not generic enough. Things that use or
# test particular services or LLMs outside the project's control should be
# segregated somehow." A category named after its first example stops being a
# category.
#
# SO: the CATEGORY is generic (`external`) and the SPECIFIC dependency is DATA —
# an argument on the marker. Two markers below are therefore NOT equivalent, and
# the difference is exactly the 2026-09-13 lesson:
#
#   @pytest.mark.external("ollama")     -> needs THAT daemon. A configured
#                                          DeepSeek key must NOT satisfy it.
#   @pytest.mark.external("embeddings") -> needs the CAPABILITY, which is a
#                                          different question from chat (a chat
#                                          key cannot embed).
#
# **An unregistered name FAILS the test rather than passing it.** A probe that
# answers for the wrong service is worse than no probe, so the gate refuses to
# guess: marking with a dependency nobody probes is a mistake the suite surfaces
# immediately instead of a green test that proves nothing.


def _probe_embeddings() -> bool:
    """Is an EMBEDDING provider reachable?

    Named for the NEED, not the vendor — because embeddings are a DIFFERENT
    capability from chat and one cannot answer for the other (the 2026-09-13
    lesson: a configured DeepSeek *chat* key answered "available" for a test
    whose handler needed Ollama *embeddings*, so it ran and failed as though our
    code were broken).

    Today the app embeds through local Ollama, so that is what this checks. The
    indirection is deliberate: the day a remote embedding provider lands, THIS
    function changes and no test does.
    """
    return EXTERNAL_PROBES["ollama"]()


def _probe_llama_cpp() -> bool:
    """The local llama.cpp server (the OpenAI-compatible endpoint)."""
    import os as _os

    base = _os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080")
    return _probe(f"{base.rstrip('/')}/v1/models")


def _probe_ollama() -> bool:
    """The local Ollama daemon."""
    import os as _os

    host = _os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    return _probe(f"{host.rstrip('/')}/api/tags")


#: THE REGISTRY. Keys name WHAT A TEST NEEDS, and each maps to a probe of the
#: thing that currently satisfies it.
#:
#: **There is deliberately NO generic "any LLM provider" key.** It was written
#: once and removed: a test whose fixture pins `provider="ollama"` needs THAT
#: daemon, so a broad "something is up" probe answers a question the test did
#: not ask — and llama.cpp running while Ollama is down would have reported
#: "available" for a test that then failed. Keys stay specific; a capability
#: key like `embeddings` is specific because it probes the implementation.
EXTERNAL_PROBES: dict[str, "Callable[[], bool]"] = {
    "ollama": _probe_ollama,
    "llama-cpp": _probe_llama_cpp,
    "embeddings": _probe_embeddings,
}

#: What each dependency IS, for the skip message — the user must be able to act
#: on a skip, and "external unavailable" is not actionable where
#: "local Ollama is not running" is.
DEPENDENCY_LABELS: dict[str, str] = {
    "ollama": "local Ollama",
    "llama-cpp": "the local llama.cpp server",
    "embeddings": "an embedding provider (the app embeds via local Ollama)",
}


@pytest.fixture(autouse=True)
def _skip_without_external(request):
    """Skip `external`-marked tests when their declared dependency is absent.

    The generic form of the tier: the marker NAMES the dependency, so one gate
    serves every external service and adding one is a line in EXTERNAL_PROBES
    rather than a new fixture and a new autouse gate.
    """
    marker = request.node.get_closest_marker("external")
    if marker is None:
        return

    deps = list(marker.args) or ["llm"]
    for dep in deps:
        if dep not in EXTERNAL_PROBES:
            # LOUD, not silent. An unprobed dependency would otherwise be a test
            # that always runs and fails mysteriously — or worse, always passes.
            pytest.fail(
                f"Unknown external dependency {dep!r}. Register a probe in "
                f"EXTERNAL_PROBES (known: {sorted(EXTERNAL_PROBES)})."
            )
        if not EXTERNAL_PROBES[dep]():
            pytest.skip(
                f"{DEPENDENCY_LABELS.get(dep, dep)} is not reachable — "
                f"the test needs {dep}, skipped"
            )


@pytest.fixture(scope="session")
def live_db_path() -> "Path":
    """The LIVE cogitate.db — resolved via the app's Paths (the
    ONE-resolver doctrine, 2026-08-27): the tests' shared-db path
    comes from the resolver, NEVER a literal or a parent-walk."""
    from pathlib import Path
    from app.core.config import Paths as CorePaths
    return Path(str(CorePaths.shared_db))
