from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config, pool, create_engine
from sqlalchemy.orm import declarative_base
from alembic import context

# Добавляем путь
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Создаем Base напрямую без импорта
Base = declarative_base()

# Импортируем модели напрямую, игнорируя ошибки импорта
try:
    exec(open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models.py')).read())
except Exception as e:
    print(f"Warning: Could not load models.py: {e}")

target_metadata = Base.metadata

database_url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://warehouse:warehouse@db:5432/warehouse')
config.set_main_option('sqlalchemy.url', database_url)


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
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
