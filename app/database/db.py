"""
Базовый класс для SQLAlchemy моделей.

Этот модуль определяет Base класс, от которого наследуются все модели БД.
"""

from sqlalchemy.orm import declarative_base

# Создаём базовый класс для всех моделей
Base = declarative_base()

__all__ = ['Base']
