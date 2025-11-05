# app/__init__.py
"""
Helmitex Warehouse - Telegram бот для складского учета.

Основные компоненты:
- database: Модели данных и подключение к БД
- handlers: Обработчики Telegram сообщений
- services: Бизнес-логика
- middleware: Промежуточное ПО
- utils: Вспомогательные функции
- validators: Валидация пользовательского ввода
"""

__version__ = "1.0.1"
__author__ = "Helmitex Team"

from .config import settings

# Экспорт для совместимости
APP_NAME = settings.APP_NAME
APP_VERSION = settings.APP_VERSION

__all__ = ["settings", "APP_NAME", "APP_VERSION"]
