"""
Alembic environment configuration.

Configures Alembic to work with SQLAlchemy models.
Uses synchronous engine for migrations.
"""

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy import create_engine

from alembic import context

from app.core.config import get_settings
from app.core.database import Base

# Autogenerate reads `Base.metadata`, which is EMPTY unless the model modules
# have been imported — `from app.core.database import Base` alone sees no
# tables. This one import pulls in every model (the package's `__init__`
# imports them all), so `target_metadata` is the real schema.
import app.infrastructure.database  # noqa: F401,E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# THE DATABASE URL COMES FROM THE APP, NOT THIS FILE.
#
# The app resolves `settings.database_url` from `DATABASE_URL` (see
# core/config.py), and alembic has to migrate the database the app will open —
# not a second one at a hardcoded path. Otherwise a `DATABASE_URL` override (a
# stranger's alternate install, a VM test) migrates the project's default
# `cogitate.db` while the app reads somewhere else, silently.
#
# Two mechanical differences: alembic drives a SYNCHRONOUS engine, so the app's
# async driver is stripped; and configparser treats `%` as interpolation, so a
# literal `%` in the URL has to be doubled.
def _sync_url(url: str) -> str:
    """The app's database URL, in the dialect alembic's sync engine can open."""
    return url.replace("+aiosqlite", "")


config.set_main_option("sqlalchemy.url", _sync_url(get_settings().database_url).replace("%", "%%"))


def _configured_url() -> str:
    """The database URL resolved above — never None once env.py has run."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "alembic env.py did not resolve a database URL — settings.database_url is empty"
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _configured_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use synchronous engine for Alembic
    connectable = create_engine(
        _configured_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
