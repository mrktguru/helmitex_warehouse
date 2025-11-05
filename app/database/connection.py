# app/database/connection.py
"""
Модуль для подключения к базе данных PostgreSQL через SQLAlchemy.

Предоставляет:
- Создание async engine для работы с PostgreSQL
- Фабрику сессий для работы с БД
- Функции для инициализации и закрытия соединений
- Генератор сессий для dependency injection

Использует настройки из app.config.py для конфигурации подключения.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from app.config import settings
from app.database.models import Base

# Настройка логирования
logger = logging.getLogger(__name__)


# Глобальные переменные для engine и session factory
engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def create_engine() -> AsyncEngine:
    """
    Создает и настраивает async engine для подключения к PostgreSQL.
    
    Настройки:
    - URL берется из settings.DATABASE_URL
    - echo=True в режиме разработки для логирования SQL-запросов
    - pool_size и max_overflow для управления пулом соединений
    - pool_pre_ping для проверки жизнеспособности соединений
    
    Returns:
        AsyncEngine: Настроенный async engine SQLAlchemy
    """
    # Получаем конфигурацию SQLAlchemy из settings
    sqlalchemy_config = settings.get_sqlalchemy_config()
    
    # Определяем класс пула в зависимости от окружения
    # В debug режиме используем NullPool (без пула) для тестирования
    pool_class = NullPool if settings.DEBUG else QueuePool
    
    return create_async_engine(
        settings.DATABASE_URL,
        echo=sqlalchemy_config["echo"],  # Логирование SQL в dev режиме
        pool_size=sqlalchemy_config["pool_size"],  # Размер пула соединений
        max_overflow=sqlalchemy_config["max_overflow"],  # Доп. соединения сверх pool_size
        pool_pre_ping=sqlalchemy_config["pool_pre_ping"],  # Проверка соединения перед использованием
        pool_timeout=sqlalchemy_config["pool_timeout"],  # Таймаут ожидания соединения
        pool_recycle=sqlalchemy_config["pool_recycle"],  # Переиспользование соединений
        poolclass=pool_class,  # Класс пула соединений
        future=True,  # Использование SQLAlchemy 2.0 style API
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Создает фабрику для создания async сессий SQLAlchemy.
    
    Args:
        engine: Async engine для подключения к БД
        
    Returns:
        async_sessionmaker: Фабрика для создания AsyncSession
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Не сбрасывать объекты после commit
        autoflush=False,  # Не делать autoflush перед каждым запросом
        autocommit=False,  # Явные commit/rollback
    )


async def init_db() -> None:
    """
    Инициализация подключения к базе данных.
    
    Создает:
    - Async engine для PostgreSQL
    - Session factory для создания сессий
    
    Должна вызываться при старте приложения (в main.py или bot.py).
    """
    global engine, SessionLocal
    
    # Создаем engine
    engine = create_engine()
    
    # Создаем фабрику сессий
    SessionLocal = create_session_factory(engine)
    
    # Логируем успешное подключение
    import logging
    logger = logging.getLogger(__name__)
    logger.info("✅ База данных инициализирована")


async def close_db() -> None:
    """
    Закрытие подключения к базе данных.
    
    Корректно закрывает engine и освобождает все соединения пула.
    Должна вызываться при остановке приложения (в main.py или bot.py).
    """
    global engine
    
    if engine:
        await engine.dispose()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info("✅ Подключение к базе данных закрыто")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор для получения async сессии БД (dependency injection).
    
    Используется в handlers и middleware для работы с базой данных.
    Автоматически закрывает сессию после использования.
    
    Yields:
        AsyncSession: Сессия SQLAlchemy для работы с БД
        
    Raises:
        RuntimeError: Если база данных не инициализирована
        
    Example:
        async with get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """
    if SessionLocal is None:
        raise RuntimeError(
            "База данных не инициализирована! "
            "Вызовите init_db() перед использованием get_session()"
        )
    
    # Создаем новую сессию
    async with SessionLocal() as session:
        try:
            yield session
            # Если не было ошибок - коммитим изменения
            await session.commit()
        except Exception:
            # В случае ошибки - откатываем транзакцию
            await session.rollback()
            raise
        finally:
            # Всегда закрываем сессию
            await session.close()


async def create_tables() -> None:
    """
    Создает все таблицы в базе данных на основе моделей SQLAlchemy.
    
    ⚠️ ВНИМАНИЕ: Используется только для разработки и тестирования!
    В production используйте Alembic миграции для управления схемой БД.
    
    Создает все таблицы, определенные в Base.metadata из models.py.
    """
    global engine
    
    if engine is None:
        raise RuntimeError(
            "База данных не инициализирована! "
            "Вызовите init_db() перед использованием create_tables()"
        )
    
    async with engine.begin() as conn:
        # Создаем все таблицы из Base.metadata
        await conn.run_sync(Base.metadata.create_all)
        
    import logging
    logger = logging.getLogger(__name__)
    logger.info("✅ Таблицы базы данных созданы")


async def drop_tables() -> None:
    """
    Удаляет все таблицы из базы данных.
    
    ⚠️ ОПАСНО: Полностью удаляет все данные!
    Используется только в тестовом окружении для очистки БД.
    
    Raises:
        RuntimeError: Если попытка выполнить в production окружении
    """
    global engine
    
    if settings.is_production():
        raise RuntimeError(
            "❌ Нельзя удалять таблицы в production окружении! "
            "Используйте Alembic миграции для управления схемой."
        )
    
    if engine is None:
        raise RuntimeError(
            "База данных не инициализирована! "
            "Вызовите init_db() перед использованием drop_tables()"
        )
    
    async with engine.begin() as conn:
        # Удаляем все таблицы из Base.metadata
        await conn.run_sync(Base.metadata.drop_all)
        
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Все таблицы базы данных удалены")
