from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.database import Base
from app.core.config import settings
import app.models  # noqa: F401 — imports every model so Base.metadata is populated

config = context.config
# ConfigParser (which Alembic's Config wraps) treats "%" as the start of an
# interpolation token. Database passwords can legitimately contain "%", so
# it must be escaped to "%%" before being stored, or set_main_option crashes
# with "invalid interpolation syntax" on any password containing it.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
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
