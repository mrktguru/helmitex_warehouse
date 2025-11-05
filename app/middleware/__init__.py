"""
Middleware для Telegram бота.

Этот модуль предоставляет middleware для обработки запросов:
- DatabaseMiddleware: Управление сессиями БД
- setup_middleware: Функция для регистрации middleware в dispatcher
"""

from .database import DatabaseMiddleware, DatabaseSessionMiddleware, setup_middleware

__all__ = [
    'DatabaseMiddleware',
    'DatabaseSessionMiddleware',
    'setup_middleware',
]

__version__ = '1.0.0'
