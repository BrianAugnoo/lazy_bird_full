from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from sqlmodel import SQLModel
import lazy_bird.models # noqa: F401

from alembic import context

from lazy_bird.database import selected_sql_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

def _resolve_url() -> str:
    """Resolve the target database URL.

    Priority:
    1. URL set programmatically (switch_database / initialize_selected_sql_database).
    2. The URL of the currently selected SQL adapter.
    3. The static value from alembic.ini as a last resort.
    """
    if config.attributes.get("url_from_code"):
        return config.get_main_option("sqlalchemy.url")
    return selected_sql_url() or config.get_main_option("sqlalchemy.url")

# Configure logging from alembic.ini only for the Alembic CLI: inside the application,
# fileConfig would replace the loguru bridge installed by lazy_bird.logging_config.
if config.config_file_name is not None and not config.attributes.get("url_from_code"):
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _resolve_url()
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
    config.set_main_option("sqlalchemy.url", _resolve_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
