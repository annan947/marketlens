"""Migrations use the same environment configuration as the API."""
from alembic import context
from backend.config import Settings
from backend.db import Base, Database

url = Settings.from_env().database_url
if not url:
    raise RuntimeError('Set MARKETLENS_DATABASE_URL before running migrations')

if context.is_offline_mode():
    context.configure(url=url.get_secret_value(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(url.get_secret_value())
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()
