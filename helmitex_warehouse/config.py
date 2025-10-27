"""
Конфигурация приложения Helmitex Warehouse.
Загружает настройки из переменных окружения.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Загружаем переменные окружения
load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Создаем необходимые директории
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Telegram Bot
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_TELEGRAM_ID: int = int(os.getenv("OWNER_TELEGRAM_ID", "0"))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

if OWNER_TELEGRAM_ID == 0:
    raise ValueError("OWNER_TELEGRAM_ID не установлен в переменных окружения")

# Database
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://warehouse:warehouse@localhost:5432/warehouse"
)

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Optional[str] = os.getenv("LOG_FILE", str(LOGS_DIR / "warehouse.log"))

# Application Settings
APP_NAME: str = "Helmitex Warehouse"
APP_VERSION: str = "1.0.0"
DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Database Settings
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_ECHO: bool = os.getenv("DB_ECHO", "False").lower() in ("true", "1", "yes")

# Validation Settings
MAX_SKU_CODE_LENGTH: int = 50
MAX_SKU_NAME_LENGTH: int = 200
MAX_CATEGORY_NAME_LENGTH: int = 100
MIN_RECIPE_YIELD: float = 50.0
MAX_RECIPE_YIELD: float = 100.0

# Production Settings
RECIPE_COMPONENT_TOLERANCE: float = 0.01  # Допустимая погрешность суммы компонентов (1%)


def validate_config():
    """Валидация конфигурации при запуске."""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не установлен")
    
    if OWNER_TELEGRAM_ID == 0:
        errors.append("OWNER_TELEGRAM_ID не установлен или равен 0")
    
    if not DATABASE_URL:
        errors.append("DATABASE_URL не установлен")
    
    if errors:
        raise ValueError(f"Ошибки конфигурации:\n" + "\n".join(f"- {e}" for e in errors))


# Валидируем конфигурацию при импорте
validate_config()
