# app/utils/logger.py
"""
Модуль для настройки централизованного логирования приложения.

Предоставляет:
- Настройку форматтеров для красивого вывода логов
- Ротацию файлов логов по размеру и времени
- Различные уровни логирования для разных модулей
- Цветной вывод в консоль для удобства разработки
- Логирование в файлы с автоматической архивацией
- Интеграцию с config.py для управления настройками

Использует стандартную библиотеку logging с расширениями для ротации.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional

from app.config import settings


# Цветовые коды ANSI для красивого вывода в консоль
class ColoredFormatter(logging.Formatter):
    """
    Форматтер с цветным выводом для консоли.
    
    Использует ANSI escape коды для окрашивания разных уровней логирования:
    - DEBUG: Синий
    - INFO: Зеленый
    - WARNING: Желтый
    - ERROR: Красный
    - CRITICAL: Красный жирный
    """
    
    # ANSI коды цветов
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan (голубой)
        'INFO': '\033[32m',       # Green (зеленый)
        'WARNING': '\033[33m',    # Yellow (желтый)
        'ERROR': '\033[31m',      # Red (красный)
        'CRITICAL': '\033[1;31m', # Bold Red (жирный красный)
    }
    RESET = '\033[0m'  # Сброс цвета
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирует запись лога с добавлением цвета.
        
        Args:
            record: Запись лога
            
        Returns:
            str: Отформатированная строка с цветовыми кодами
        """
        # Получаем цвет для уровня логирования
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Сохраняем оригинальный levelname
        original_levelname = record.levelname
        
        # Добавляем цвет к levelname
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # Форматируем с помощью родительского класса
        formatted = super().format(record)
        
        # Восстанавливаем оригинальный levelname
        record.levelname = original_levelname
        
        return formatted


def setup_logging(
    log_level: Optional[str] = None,
    log_dir: Optional[str] = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
) -> None:
    """
    Настраивает систему логирования приложения.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   Если None, берется из settings.LOG_LEVEL
        log_dir: Директория для хранения файлов логов
                 Если None, берется из settings.LOG_DIR
        enable_file_logging: Включить логирование в файлы
        enable_console_logging: Включить вывод в консоль
    """
    # Используем настройки из config, если не переданы явно
    log_level = log_level or settings.LOG_LEVEL
    log_dir = log_dir or settings.LOG_DIR
    
    # Создаем директорию для логов, если не существует
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Получаем корневой logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие handlers (если есть)
    root_logger.handlers.clear()
    
    # Формат для консольного вывода (короткий)
    console_format = (
        '%(levelname)-8s | '
        '%(name)-25s | '
        '%(message)s'
    )
    
    # Формат для файлового вывода (детальный)
    file_format = (
        '%(asctime)s | '
        '%(levelname)-8s | '
        '%(name)-30s | '
        '%(funcName)-20s | '
        '%(lineno)-4d | '
        '%(message)s'
    )
    
    # Формат даты и времени
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # ========== КОНСОЛЬНЫЙ HANDLER ==========
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        # Используем цветной форматтер для консоли
        if settings.APP_ENV == "development":
            console_formatter = ColoredFormatter(
                console_format,
                datefmt=date_format,
            )
        else:
            # В production без цветов (для совместимости с системами логирования)
            console_formatter = logging.Formatter(
                console_format,
                datefmt=date_format,
            )
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # ========== ФАЙЛОВЫЕ HANDLERS ==========
    if enable_file_logging:
        # 1. Основной лог файл с ротацией по размеру (все уровни)
        main_log_file = log_path / 'app.log'
        main_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,  # Хранить 5 архивных файлов
            encoding='utf-8',
        )
        main_handler.setLevel(logging.DEBUG)  # Логируем все
        main_formatter = logging.Formatter(file_format, datefmt=date_format)
        main_handler.setFormatter(main_formatter)
        root_logger.addHandler(main_handler)
        
        # 2. Лог файл только для ошибок (ERROR и CRITICAL)
        error_log_file = log_path / 'error.log'
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=10,  # Хранить больше архивов для ошибок
            encoding='utf-8',
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(file_format, datefmt=date_format)
        error_handler.setFormatter(error_formatter)
        root_logger.addHandler(error_handler)
        
        # 3. Лог файл с ротацией по дням (для долгосрочного хранения)
        daily_log_file = log_path / 'daily.log'
        daily_handler = TimedRotatingFileHandler(
            daily_log_file,
            when='midnight',  # Ротация в полночь
            interval=1,  # Каждый день
            backupCount=30,  # Хранить 30 дней
            encoding='utf-8',
        )
        daily_handler.setLevel(logging.INFO)
        daily_formatter = logging.Formatter(file_format, datefmt=date_format)
        daily_handler.setFormatter(daily_formatter)
        root_logger.addHandler(daily_handler)
    
    # ========== НАСТРОЙКА УРОВНЕЙ ДЛЯ СТОРОННИХ БИБЛИОТЕК ==========
    # Уменьшаем verbosity для сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.INFO)  # aiogram - только INFO и выше
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)  # SQLAlchemy - только WARNING
    logging.getLogger('aiohttp').setLevel(logging.WARNING)  # aiohttp - только WARNING
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # urllib3 - только WARNING
    
    # В режиме разработки можем включить SQL запросы
    if settings.APP_ENV == "development" and log_level == "DEBUG":
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    
    # Логируем успешную инициализацию
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Логирование настроено: уровень={log_level}, директория={log_dir}")
    logger.info(f"📁 Файлы логов: app.log (основной), error.log (ошибки), daily.log (дневной)")


def get_logger(name: str) -> logging.Logger:
    """
    Получает logger для конкретного модуля.
    
    Args:
        name: Имя модуля (обычно __name__)
        
    Returns:
        logging.Logger: Настроенный logger
        
    Example:
        from app.utils.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("Сообщение в лог")
    """
    return logging.getLogger(name)


def log_function_call(logger: logging.Logger):
    """
    Декоратор для логирования вызовов функций.
    
    Логирует:
    - Имя функции и параметры при входе
    - Результат выполнения при выходе
    - Ошибки при исключениях
    
    Args:
        logger: Logger для записи логов
        
    Example:
        logger = get_logger(__name__)
        
        @log_function_call(logger)
        async def process_order(order_id: int):
            # ... обработка заказа
            return result
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"🔵 Вызов {func_name}() | args={args}, kwargs={kwargs}")
            
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"🟢 {func_name}() завершена | result={result}")
                return result
            except Exception as e:
                logger.error(f"🔴 Ошибка в {func_name}(): {e}", exc_info=True)
                raise
        
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"🔵 Вызов {func_name}() | args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"🟢 {func_name}() завершена | result={result}")
                return result
            except Exception as e:
                logger.error(f"🔴 Ошибка в {func_name}(): {e}", exc_info=True)
                raise
        
        # Определяем, асинхронная ли функция
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_database_query(logger: logging.Logger, query_name: str):
    """
    Декоратор для логирования запросов к БД с измерением времени выполнения.
    
    Args:
        logger: Logger для записи логов
        query_name: Название запроса для логов
        
    Example:
        logger = get_logger(__name__)
        
        @log_database_query(logger, "get_user_by_id")
        async def get_user(session: AsyncSession, user_id: int):
            # ... запрос к БД
            return user
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            
            start_time = time.time()
            logger.debug(f"🔍 Запрос к БД: {query_name}")
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if execution_time > 1.0:
                    # Медленный запрос
                    logger.warning(
                        f"🐌 Медленный запрос: {query_name} | {execution_time:.3f}s"
                    )
                else:
                    logger.debug(
                        f"✅ Запрос выполнен: {query_name} | {execution_time:.3f}s"
                    )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"❌ Ошибка запроса: {query_name} | {execution_time:.3f}s | {e}",
                    exc_info=True,
                )
                raise
        
        return wrapper
    
    return decorator


def configure_uvicorn_logging() -> dict:
    """
    Возвращает конфигурацию логирования для Uvicorn (если используется).
    
    Returns:
        dict: Конфигурация logging для Uvicorn
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"level": "INFO"},
        },
    }


# Автоматическая настройка логирования при импорте модуля (опционально)
# Если не хотите автоматическую настройку - закомментируйте следующую строку
# setup_logging()
