from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Добавляем корневую директорию в путь
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Динамическая загрузка модулей с обработкой относительных импортов
def load_module_with_relative_imports(module_name, file_path):
    """Загружает модуль Python с поддержкой относительных импортов"""
    import importlib.util
    
    # Создаем временный пакет для относительных импортов
    if '__init__' not in sys.modules:
        import types
        init_module = types.ModuleType('__init__')
        sys.modules['__init__'] = init_module
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    
    # Добавляем модуль в sys.modules ДО загрузки
    sys.modules[module_name] = module
    
    try:
        spec.loader.exec_module(module)
    except ImportError as e:
        # Если относительный импорт не работает, пробуем абсолютный
        if str(e).startswith("attempted relative import"):
            # Перезагружаем файл, заменяя относительные импорты на абсолютные
            with open(file_path, 'r') as f:
                code = f.read()
            # Заменяем относительные импорты на абсолютные
            code = code.replace('from .', 'from ')
            code = code.replace('import .', 'import ')
            exec(compile(code, file_path, 'exec'), module.__dict__)
    
    return module

# Загружаем config.py
config_path = os.path.join(parent_dir, 'config.py')
if os.path.exists(config_path):
    config_module = load_module_with_relative_imports('config', config_path)

# Загружаем db.py
db_path = os.path.join(parent_dir, 'db.py')
if os.path.exists(db_path):
    db_module = load_module_with_relative_imports('db', db_path)
    Base = db_module.Base
else:
    raise FileNotFoundError(f"db.py not found at {db_path}")

# Загружаем models.py
models_path = os.path.join(parent_dir, 'models.py')
if os.path.exists(models_path):
    models_module = load_module_with_relative_imports('models', models_path)
else:
    raise FileNotFoundError(f"models.py not found at {models_path}")

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
