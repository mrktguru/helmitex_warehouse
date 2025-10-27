"""
Настройка системы логирования для приложения.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Настраивает систему логирования.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу логов (если None, логи только в консоль)
        max_bytes: Максимальный размер файла лога перед ротацией
        backup_count: Количество резервных копий логов
        
    Returns:
        Настроенный logger
    """
    # Создаем корневой logger
    logger = logging.getLogger("helmitex_warehouse")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Формат логов
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (если указан путь)
    if log_file:
        # Создаем директорию для логов если не существует
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Логируем старт системы
    logger.info("=" * 80)
    logger.info(f"Система логирования инициализирована (уровень: {log_level})")
    logger.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if log_file:
        logger.info(f"Логи сохраняются в: {log_file}")
    logger.info("=" * 80)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получает logger для конкретного модуля.
    
    Args:
        name: Имя модуля
        
    Returns:
        Logger для модуля
    """
    return logging.getLogger(f"helmitex_warehouse.{name}")
