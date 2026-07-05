import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# env.py lives at backend/alembic/env.py. The application is imported as the
# `backend` package (e.g. `from backend.core.config import settings`), so the
# repo root — the parent of backend/ — must be on sys.path. Deriving it from
# __file__ makes migrations work regardless of the current working directory.
#   parents[0] = alembic/, parents[1] = backend/, parents[2] = repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.config import settings
from backend.database import Base
import backend.models  # noqa: F401  registers every model on Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Pull the live DB URL from settings (loads backend/.env) rather than the
# alembic.ini placeholder, so migrations hit the same database as the app.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for 'autogenerate' support. Importing backend.models above is
# what populates this — without it autogenerate would emit empty migrations.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
