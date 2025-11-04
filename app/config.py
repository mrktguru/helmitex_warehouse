"""
Конфигурация приложения.

Этот модуль загружает настройки из переменных окружения
и предоставляет их через объект settings.

Использует pydantic-settings для валидации и типизации.
"""

import os
from typing import Optional
from pydantic import Field, field_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки приложения из переменных окружения.
    
    Все настройки загружаются из .env файла или переменных окружения.
    """
    
    # ========================================================================
    # TELEGRAM BOT
    # ========================================================================
    
    TELEGRAM_BOT_TOKEN: str = Field(
        ...,
        description="Токен Telegram бота от @BotFather"
    )
    
    ADMIN_TELEGRAM_ID: Optional[int] = Field(
        default=None,
        description="Telegram ID главного администратора (для уведомлений)"
    )
    
    # ========================================================================
    # DATABASE
    # ========================================================================
    
    DATABASE_URL: str = Field(
        ...,
        description="URL подключения к PostgreSQL (asyncpg драйвер)"
    )
    
    DB_ECHO: bool = Field(
        default=False,
        description="Логировать SQL запросы (для отладки)"
    )
    
    DB_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Размер пула соединений"
    )
    
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Максимальное количество дополнительных соединений"
    )
    
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Таймаут ожидания соединения (секунды)"
    )
    
    DB_POOL_RECYCLE: int = Field(
        default=3600,
        ge=300,
        le=7200,
        description="Время жизни соединения в пуле (секунды)"
    )
    
    # ========================================================================
    # APPLICATION
    # ========================================================================
    
    APP_NAME: str = Field(
        default="Helmitex Warehouse",
        description="Название приложения"
    )
    
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Версия приложения"
    )
    
    DEBUG: bool = Field(
        default=False,
        description="Режим отладки"
    )
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    TIMEZONE: str = Field(
        default="UTC",
        description="Временная зона приложения"
    )
    
    # ========================================================================
    # BUSINESS LOGIC
    # ========================================================================
    
    DEFAULT_BARREL_CAPACITY: float = Field(
        default=200.0,
        gt=0,
        description="Стандартная вместимость бочки (кг)"
    )
    
    MIN_BARREL_WEIGHT: float = Field(
        default=0.1,
        gt=0,
        description="Минимальный вес для считывания бочки непустой (кг)"
    )
    
    MIN_OUTPUT_PERCENTAGE: float = Field(
        default=50.0,
        ge=0,
        le=100,
        description="Минимальный процент выхода в рецепте (%)"
    )
    
    MAX_OUTPUT_PERCENTAGE: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Максимальный процент выхода в рецепте (%)"
    )
    
    RESERVE_EXPIRY_DAYS: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Срок действия резерва по умолчанию (дни)"
    )
    
    # ========================================================================
    # PAGINATION
    # ========================================================================
    
    DEFAULT_PAGE_SIZE: int = Field(
        default=10,
        ge=5,
        le=100,
        description="Размер страницы по умолчанию"
    )
    
    MAX_PAGE_SIZE: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Максимальный размер страницы"
    )
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    MAX_SKU_NAME_LENGTH: int = Field(
        default=100,
        ge=10,
        le=255,
        description="Максимальная длина названия SKU"
    )
    
    MAX_WAREHOUSE_NAME_LENGTH: int = Field(
        default=100,
        ge=10,
        le=255,
        description="Максимальная длина названия склада"
    )
    
    MAX_RECIPE_NAME_LENGTH: int = Field(
        default=100,
        ge=10,
        le=255,
        description="Максимальная длина названия рецепта"
    )
    
    MAX_NOTES_LENGTH: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Максимальная длина текстовых заметок"
    )
    
    # ========================================================================
    # SECURITY
    # ========================================================================
    
    ALLOWED_TELEGRAM_IDS: Optional[list[int]] = Field(
        default=None,
        description="Список разрешенных Telegram ID (whitelist). Если None - доступ для всех"
    )
    
    RATE_LIMIT_REQUESTS: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Максимум запросов от пользователя"
    )
    
    RATE_LIMIT_PERIOD: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Период для rate limiting (секунды)"
    )
    
    # ========================================================================
    # FEATURES FLAGS
    # ========================================================================
    
    ENABLE_NOTIFICATIONS: bool = Field(
        default=True,
        description="Включить уведомления администраторам"
    )
    
    ENABLE_STATISTICS: bool = Field(
        default=True,
        description="Включить сбор статистики"
    )
    
    ENABLE_AUDIT_LOG: bool = Field(
        default=True,
        description="Включить журнал аудита действий"
    )
    
    # ========================================================================
    # VALIDATORS
    # ========================================================================
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Валидация уровня логирования."""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v_upper
    
    @field_validator('DATABASE_URL')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Валидация URL базы данных."""
        if not v.startswith('postgresql'):
            raise ValueError("DATABASE_URL must start with 'postgresql' or 'postgresql+asyncpg'")
        
        # Рекомендуем asyncpg для async работы
        if 'asyncpg' not in v:
            import warnings
            warnings.warn(
                "Consider using 'postgresql+asyncpg://' for better async performance",
                UserWarning
            )
        
        return v
    
    @field_validator('TELEGRAM_BOT_TOKEN')
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Валидация токена Telegram бота."""
        if not v or len(v) < 20:
            raise ValueError("Invalid TELEGRAM_BOT_TOKEN")
        
        # Базовая проверка формата токена
        parts = v.split(':')
        if len(parts) != 2:
            raise ValueError("TELEGRAM_BOT_TOKEN must be in format 'bot_id:token'")
        
        return v
    
    @field_validator('TIMEZONE')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Валидация временной зоны."""
        try:
            import pytz
            pytz.timezone(v)
        except:
            # Если pytz не установлен или зона неверна, используем UTC
            return "UTC"
        return v
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def get_database_url_sync(self) -> str:
        """
        Возвращает синхронный URL для БД (для Alembic).
        
        Returns:
            str: DATABASE_URL с psycopg2 драйвером
        """
        return self.DATABASE_URL.replace('+asyncpg', '').replace('postgresql+', 'postgresql+psycopg2+')
    
    def is_production(self) -> bool:
        """
        Проверяет, запущено ли приложение в production режиме.
        
        Returns:
            bool: True если production (DEBUG=False)
        """
        return not self.DEBUG
    
    def get_log_config(self) -> dict:
        """
        Возвращает конфигурацию для logging.
        
        Returns:
            dict: Конфигурация логирования
        """
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': self.LOG_LEVEL,
                    'formatter': 'detailed' if self.DEBUG else 'default',
                    'stream': 'ext://sys.stdout',
                },
            },
            'root': {
                'level': self.LOG_LEVEL,
                'handlers': ['console'],
            },
        }
    
    def get_sqlalchemy_config(self) -> dict:
        """
        Возвращает конфигурацию для SQLAlchemy engine.
        
        Returns:
            dict: Параметры для create_async_engine
        """
        return {
            'url': self.DATABASE_URL,
            'echo': self.DB_ECHO,
            'pool_size': self.DB_POOL_SIZE,
            'max_overflow': self.DB_MAX_OVERFLOW,
            'pool_timeout': self.DB_POOL_TIMEOUT,
            'pool_recycle': self.DB_POOL_RECYCLE,
            'pool_pre_ping': True,  # Проверка соединений перед использованием
        }
    
    def is_user_allowed(self, telegram_id: int) -> bool:
        """
        Проверяет, разрешен ли доступ пользователю (whitelist).
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            bool: True если доступ разрешен
        """
        # Если whitelist не настроен, разрешаем всем
        if self.ALLOWED_TELEGRAM_IDS is None:
            return True
        
        return telegram_id in self.ALLOWED_TELEGRAM_IDS
    
    # ========================================================================
    # PYDANTIC CONFIG
    # ========================================================================
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',  # Игнорировать неизвестные переменные
    )


# Создание глобального экземпляра настроек
settings = Settings()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_settings() -> Settings:
    """
    Возвращает глобальный объект настроек.
    
    Returns:
        Settings: Экземпляр настроек
    """
    return settings


def reload_settings() -> Settings:
    """
    Перезагружает настройки из переменных окружения.
    
    Полезно для тестирования или динамической перезагрузки конфигурации.
    
    Returns:
        Settings: Новый экземпляр настроек
    """
    global settings
    settings = Settings()
    return settings


def print_settings(hide_sensitive: bool = True) -> None:
    """
    Выводит текущие настройки в консоль.
    
    Args:
        hide_sensitive: Скрывать ли чувствительные данные (токены, пароли)
    """
    print("=" * 60)
    print("APPLICATION SETTINGS")
    print("=" * 60)
    
    for field_name, field_info in settings.model_fields.items():
        value = getattr(settings, field_name)
        
        # Скрываем чувствительные данные
        if hide_sensitive and any(keyword in field_name.lower() for keyword in ['token', 'password', 'secret', 'key']):
            value = "***HIDDEN***"
        
        print(f"{field_name}: {value}")
    
    print("=" * 60)


def validate_settings() -> tuple[bool, list[str]]:
    """
    Валидирует все настройки приложения.
    
    Returns:
        tuple: (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        # Проверка критических настроек
        if not settings.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is not set")
        
        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL is not set")
        
        # Проверка валидности URL БД
        if 'postgresql' not in settings.DATABASE_URL.lower():
            errors.append("DATABASE_URL must be a PostgreSQL connection string")
        
        # Проверка логических значений
        if settings.MIN_OUTPUT_PERCENTAGE > settings.MAX_OUTPUT_PERCENTAGE:
            errors.append("MIN_OUTPUT_PERCENTAGE cannot be greater than MAX_OUTPUT_PERCENTAGE")
        
        if settings.DEFAULT_PAGE_SIZE > settings.MAX_PAGE_SIZE:
            errors.append("DEFAULT_PAGE_SIZE cannot be greater than MAX_PAGE_SIZE")
        
    except Exception as e:
        errors.append(f"Validation error: {str(e)}")
    
    return len(errors) == 0, errors


# Экспорт
__all__ = [
    'Settings',
    'settings',
    'get_settings',
    'reload_settings',
    'print_settings',
    'validate_settings',
]


# Валидация настроек при импорте
if __name__ != '__main__':
    is_valid, errors = validate_settings()
    if not is_valid:
        import warnings
        for error in errors:
            warnings.warn(f"Configuration error: {error}", UserWarning)
