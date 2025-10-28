from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Хак для импорта с относительными путями
import importlib.util
import pathlib

# Загружаем db.py напрямую
db_path = pathlib.Path(__file__).parent.parent / "db.py"
spec = importlib.util.spec_from_file_location("db", db_path)
db_module = importlib.util.module_from_spec(spec)
sys.modules["db"] = db_module
spec.loader.exec_module(db_module)

# Загружаем models.py напрямую
models_path = pathlib.Path(__file__).parent.parent / "models.py"
spec = importlib.util.spec_from_file_location("models", models_path)
models_module = importlib.util.module_from_spec(spec)
sys.modules["models"] = models_module
spec.loader.exec_module(models_module)

Base = db_module.Base
target_metadata = Base.metadata

# Получаем DATABASE_URL из переменных окружения
database_url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://warehouse:warehouse@db:5432/warehouse')
config.set_main_option('sqlalchemy.url', database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
