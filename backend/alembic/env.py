from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import all models so autogenerate sees every table
from app.config import settings
from app.database import ensure_sqlite_dir
from app.models import Base  # noqa: F401 — side-effect import registers all tables

config = context.config

# Migrate the same DB the app serves. In deploy, APP_DB_PATH points at the
# persistent volume (sqlite:////data/app.db); locally it defaults to the ini
# value (sqlite:///./app.db). Override the ini URL so the two never diverge.
config.set_main_option("sqlalchemy.url", settings.app_db_path)
# Create the DB's parent dir so the first `alembic upgrade` doesn't fail with
# "unable to open database file" on a fresh volume.
ensure_sqlite_dir(settings.app_db_path)

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
