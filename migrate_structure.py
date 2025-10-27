"""
Скрипт для миграции структуры проекта.
Запустить один раз для реорганизации файлов.
"""
import os
import shutil
from pathlib import Path

def create_directory_structure():
    """Создает новую структуру директорий."""
    
    base_dir = Path(__file__).parent
    app_dir = base_dir / "helmitex_warehouse"
    
    # Создаем основные директории
    directories = [
        app_dir,
        app_dir / "database",
        app_dir / "services",
        app_dir / "handlers",
        app_dir / "validators",
        app_dir / "utils",
        base_dir / "alembic" / "versions",
        base_dir / "tests" / "test_services",
        base_dir / "tests" / "test_handlers",
        base_dir / "tests" / "test_validators",
        base_dir / "logs",
        base_dir / "data",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        # Создаем __init__.py в Python пакетах
        if "helmitex_warehouse" in str(directory) or "tests" in str(directory):
            init_file = directory / "__init__.py"
            if not init_file.exists():
                init_file.touch()
    
    print("✅ Структура директорий создана")


def move_files():
    """Перемещает файлы в новую структуру."""
    
    base_dir = Path(__file__).parent
    app_dir = base_dir / "helmitex_warehouse"
    
    # Маппинг: старый путь -> новый путь
    file_moves = {
        # Основные файлы
        "bot.py": app_dir / "bot.py",
        "config.py": app_dir / "config.py",
        
        # Database
        "db.py": app_dir / "database" / "db.py",
        "models.py": app_dir / "database" / "models.py",
        
        # Services (разбиваем services.py на отдельные файлы)
        "services.py": app_dir / "services" / "_original_services.py",  # Временно
        
        # Handlers (разбиваем handlers.py на отдельные файлы)
        "handlers.py": app_dir / "handlers" / "_original_handlers.py",  # Временно
        
        # Utils
        "utils.py": app_dir / "utils" / "helpers.py",
    }
    
    for old_path, new_path in file_moves.items():
        old_file = base_dir / old_path
        if old_file.exists():
            shutil.copy2(old_file, new_path)
            print(f"✅ Скопирован: {old_path} -> {new_path}")
        else:
            print(f"⚠️  Файл не найден: {old_path}")
    
    print("\n✅ Файлы перемещены")


def create_init_files():
    """Создает __init__.py файлы с правильными импортами."""
    
    base_dir = Path(__file__).parent
    app_dir = base_dir / "helmitex_warehouse"
    
    # helmitex_warehouse/__init__.py
    (app_dir / "__init__.py").write_text('''"""
Helmitex Warehouse - Telegram бот для складского учета.
"""

__version__ = "1.0.0"
__author__ = "Helmitex Team"

from .config import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION"]
''')
    
    # helmitex_warehouse/database/__init__.py
    (app_dir / "database" / "__init__.py").write_text('''"""
Модуль работы с базой данных.
"""

from .db import engine, SessionLocal, init_db, get_db
from .models import Base, SKU, Category, Recipe, RecipeComponent, Barrel, Production

__all__ = [
    "engine",
    "SessionLocal", 
    "init_db",
    "get_db",
    "Base",
    "SKU",
    "Category",
    "Recipe",
    "RecipeComponent",
    "Barrel",
    "Production",
]
''')
    
    # helmitex_warehouse/services/__init__.py
    (app_dir / "services" / "__init__.py").write_text('''"""
Бизнес-логика приложения.
"""

# Импорты будут добавлены после разделения services.py
''')
    
    # helmitex_warehouse/handlers/__init__.py
    (app_dir / "handlers" / "__init__.py").write_text('''"""
Telegram bot handlers.
"""

# Импорты будут добавлены после разделения handlers.py
''')
    
    # helmitex_warehouse/validators/__init__.py
    (app_dir / "validators" / "__init__.py").write_text('''"""
Валидаторы данных.
"""
''')
    
    # helmitex_warehouse/utils/__init__.py
    (app_dir / "utils" / "__init__.py").write_text('''"""
Вспомогательные функции.
"""
''')
    
    print("✅ __init__.py файлы созданы")


def create_config_files():
    """Создает конфигурационные файлы."""
    
    base_dir = Path(__file__).parent
    
    # .env.example
    (base_dir / ".env.example").write_text('''# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
OWNER_TELEGRAM_ID=your_telegram_id_here

# Database Configuration
DATABASE_URL=postgresql+psycopg2://warehouse:warehouse@localhost:5432/warehouse

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/warehouse.log

# Application Settings
DEBUG=False
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_ECHO=False
''')
    
    # .gitignore
    (base_dir / ".gitignore").write_text('''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment variables
.env

# Logs
logs/
*.log

# Data
data/

# Database
*.db
*.sqlite

# Testing
.pytest_cache/
.coverage
htmlcov/

# Alembic
alembic/versions/*.pyc
''')
    
    # pytest.ini
    (base_dir / "pytest.ini").write_text('''[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --cov=helmitex_warehouse
    --cov-report=html
    --cov-report=term-missing
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
''')
    
    # pyproject.toml
    (base_dir / "pyproject.toml").write_text('''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "helmitex-warehouse"
version = "1.0.0"
description = "Telegram bot for warehouse management"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "python-telegram-bot==21.5",
    "SQLAlchemy==2.0.34",
    "psycopg2-binary==2.9.9",
    "python-dotenv==1.0.1",
    "alembic==1.13.1",
    "pydantic==2.5.3",
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.3",
    "pytest-asyncio==0.21.1",
    "pytest-cov==4.1.0",
    "pytest-mock==3.12.0",
    "black==23.12.1",
    "flake8==6.1.0",
    "mypy==1.7.1",
    "isort==5.13.2",
]

[tool.black]
line-length = 100
target-version = ['py310']
include = '\\.pyi?$'

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
''')
    
    print("✅ Конфигурационные файлы созданы")


def main():
    """Основная функция миграции."""
    print("🚀 Начинаем миграцию структуры проекта...\n")
    
    create_directory_structure()
    print()
    
    move_files()
    print()
    
    create_init_files()
    print()
    
    create_config_files()
    print()
    
    print("=" * 80)
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА!")
    print("=" * 80)
    print("\n📋 Следующие шаги:")
    print("1. Проверьте перемещенные файлы")
    print("2. Обновите импорты в файлах (будет в следующем этапе)")
    print("3. Разделите services.py и handlers.py на модули")
    print("4. Удалите старые файлы из корня после проверки")
    print("5. Запустите: python -m helmitex_warehouse")


if __name__ == "__main__":
    main()
