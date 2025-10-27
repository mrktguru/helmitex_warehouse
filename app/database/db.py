"""
Модуль для работы с базой данных.
Настройка SQLAlchemy engine, сессий и базовых операций.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from contextlib import contextmanager
from typing import Generator

from app.config import (
    DATABASE_URL,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT,
    DB_ECHO
)
from app.logger import get_logger

logger = get_logger("database")

# Создание engine с настройками из конфигурации
engine = create_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    echo=DB_ECHO,
    future=True
)

# Фабрика сессий
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True
)

# Базовый класс для моделей
Base = declarative_base()


def init_db():
    """
    Инициализация базы данных.
    Создает все таблицы, определенные в моделях.
    """
    try:
        logger.info("Инициализация базы данных...")
        from app.database.models import (
            SKU, Category, Recipe, RecipeComponent, 
            Barrel, Production, SemiBatch, ProductionUsedRaw
        )
        Base.metadata.create_all(bind=engine)
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)
        raise


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Контекстный менеджер для получения сессии БД.
    
    Использование:
        with get_db() as db:
            # работа с БД
            pass
    
    Yields:
        Session: Сессия SQLAlchemy
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка в транзакции БД: {e}", exc_info=True)
        raise
    finally:
        db.close()


def get_session() -> Session:
    """
    Получить новую сессию БД.
    
    ВАЖНО: Не забудьте закрыть сессию после использования!
    
    Returns:
        Session: Новая сессия SQLAlchemy
    """
    return SessionLocal()
