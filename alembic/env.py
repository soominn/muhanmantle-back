from __future__ import annotations

import sys
from pathlib import Path

# Alembic is often run from any cwd; ensure project root is on PYTHONPATH.
_BACK_ROOT = Path(__file__).resolve().parents[1]
if str(_BACK_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACK_ROOT))

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import app objects so Alembic sees our models and the DB URL
from app.core.config import settings
from app.db.base import Base
import app.models.answer_word  # noqa: F401 — registers model on Base.metadata
import app.models.base_word  # noqa: F401
import app.models.game_session  # noqa: F401
import app.models.game_shout  # noqa: F401
import app.models.base_word_candidate  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
