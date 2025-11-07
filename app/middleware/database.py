# app/middleware/database.py
"""
Middleware для автоматического предоставления сессий БД в handlers.

Предоставляет:
- Автоматическое создание и закрытие сессий БД для каждого запроса
- Передачу сессии в handler через data['session']
- Обработку ошибок подключения к БД
- Логирование времени выполнения запросов
- Мониторинг производительности работы с БД

Интегрируется с aiogram dispatcher и использует app/database/connection.py.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.exc import (
    SQLAlchemyError,
    OperationalError,
    IntegrityError,
    DataError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import SessionLocal, get_session_maker
from app.config import settings


logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для управления сессиями базы данных в handlers.
    
    Функциональность:
    1. Создает новую сессию БД для каждого входящего события
    2. Передает сессию в handler через data['session']
    3. Автоматически коммитит изменения при успешном выполнении
    4. Откатывает транзакцию при ошибках
    5. Логирует время выполнения запросов
    6. Обрабатывает ошибки подключения к БД
    
    Использование:
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
    """
    
    def __init__(self):
        """Инициализация middleware."""
        super().__init__()
        self.slow_query_threshold = 1.0  # Порог медленных запросов (секунды)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Основной метод middleware для обработки события.
        
        Args:
            handler: Следующий handler в цепочке
            event: Событие от Telegram (Message, CallbackQuery и т.д.)
            data: Словарь с данными для передачи в handler
            
        Returns:
            Any: Результат выполнения handler
        """
        # Проверяем, что SessionLocal инициализирован
        if SessionLocal is None:
            logger.error("❌ SessionLocal не инициализирован! Вызовите init_db() при старте.")
            await self._send_error_message(
                event,
                "⚠️ Сервис временно недоступен. Попробуйте позже."
            )
            return
        
        # Получаем информацию о пользователе для логирования
        user_info = self._get_user_info(event)
        event_type = self._get_event_type(event)
        
        # Создаем сессию БД
        async with session_maker() as session:
            # Добавляем сессию в data для передачи в handler
            data["session"] = session
            
            # Засекаем время начала выполнения
            start_time = time.time()
            
            try:
                # Вызываем handler
                result = await handler(event, data)
                
                # Коммитим изменения, если не было ошибок
                await session.commit()
                
                # Вычисляем время выполнения
                execution_time = time.time() - start_time
                
                # Логируем успешное выполнение
                self._log_request(
                    user_info=user_info,
                    event_type=event_type,
                    execution_time=execution_time,
                    success=True,
                )
                
                return result
                
            except OperationalError as e:
                # Ошибка подключения к БД
                await session.rollback()
                logger.error(
                    f"❌ Ошибка подключения к БД | {user_info} | {event_type}: {e}",
                    exc_info=True,
                )
                await self._send_error_message(
                    event,
                    "⚠️ Проблема с подключением к базе данных. Попробуйте позже."
                )
                
            except IntegrityError as e:
                # Ошибка целостности данных (дубликаты, нарушение FK и т.д.)
                await session.rollback()
                logger.error(
                    f"❌ Ошибка целостности данных | {user_info} | {event_type}: {e}",
                    exc_info=True,
                )
                await self._send_error_message(
                    event,
                    "⚠️ Ошибка сохранения данных. Проверьте корректность введенных данных."
                )
                
            except DataError as e:
                # Ошибка данных (неверный формат, выход за пределы и т.д.)
                await session.rollback()
                logger.error(
                    f"❌ Ошибка формата данных | {user_info} | {event_type}: {e}",
                    exc_info=True,
                )
                await self._send_error_message(
                    event,
                    "⚠️ Неверный формат данных. Проверьте введенные значения."
                )
                
            except SQLAlchemyError as e:
                # Общая ошибка SQLAlchemy
                await session.rollback()
                logger.error(
                    f"❌ Ошибка БД | {user_info} | {event_type}: {e}",
                    exc_info=True,
                )
                await self._send_error_message(
                    event,
                    "⚠️ Произошла ошибка при работе с базой данных."
                )
                
            except Exception as e:
                # Любая другая ошибка
                await session.rollback()
                execution_time = time.time() - start_time
                
                logger.error(
                    f"❌ Неожиданная ошибка | {user_info} | {event_type} | "
                    f"{execution_time:.3f}s: {e}",
                    exc_info=True,
                )
                
                # В режиме разработки показываем детальную ошибку
                if settings.APP_ENV == "development":
                    error_msg = f"⚠️ Ошибка: {type(e).__name__}\n{str(e)}"
                else:
                    error_msg = "⚠️ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                
                await self._send_error_message(event, error_msg)
                
            finally:
                # Закрываем сессию (на всякий случай, хотя context manager это делает)
                await session.close()
    
    def _get_user_info(self, event: TelegramObject) -> str:
        """
        Извлекает информацию о пользователе из события.
        
        Args:
            event: Событие от Telegram
            
        Returns:
            str: Строка с информацией о пользователе (ID, username)
        """
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        else:
            return "Unknown"
        
        if user:
            username = f"@{user.username}" if user.username else "no_username"
            return f"User {user.id} ({username})"
        
        return "Unknown User"
    
    def _get_event_type(self, event: TelegramObject) -> str:
        """
        Определяет тип события для логирования.
        
        Args:
            event: Событие от Telegram
            
        Returns:
            str: Тип события (Message, CallbackQuery и т.д.)
        """
        if isinstance(event, Message):
            # Для сообщений указываем тип контента
            if event.text:
                return f"Message: {event.text[:50]}"
            elif event.photo:
                return "Message: [photo]"
            elif event.document:
                return "Message: [document]"
            else:
                return "Message: [other]"
        elif isinstance(event, CallbackQuery):
            # Для callback указываем data
            return f"Callback: {event.data}"
        else:
            return event.__class__.__name__
    
    def _log_request(
        self,
        user_info: str,
        event_type: str,
        execution_time: float,
        success: bool,
    ) -> None:
        """
        Логирует информацию о выполнении запроса.
        
        Args:
            user_info: Информация о пользователе
            event_type: Тип события
            execution_time: Время выполнения в секундах
            success: Успешность выполнения
        """
        # Форматируем время выполнения
        time_str = f"{execution_time:.3f}s"
        
        # Определяем статус
        status = "✅" if success else "❌"
        
        # Проверяем, не медленный ли запрос
        if execution_time > self.slow_query_threshold:
            logger.warning(
                f"🐌 Медленный запрос | {status} | {user_info} | {event_type} | {time_str}"
            )
        else:
            logger.info(
                f"{status} | {user_info} | {event_type} | {time_str}"
            )
    
    async def _send_error_message(
        self,
        event: TelegramObject,
        error_text: str,
    ) -> None:
        """
        Отправляет сообщение об ошибке пользователю.
        
        Args:
            event: Событие от Telegram
            error_text: Текст ошибки для отправки
        """
        try:
            if isinstance(event, Message):
                await event.answer(error_text)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(error_text)
                await event.answer()  # Убираем "часики" на кнопке
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")


class DatabaseSessionMiddleware(BaseMiddleware):
    """
    Упрощенная версия middleware для сессий БД без расширенного логирования.
    
    Использует простой подход: создает сессию, передает в handler, закрывает.
    Без детального логирования и обработки специфичных ошибок.
    
    Подходит для production, если не требуется детальный мониторинг.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Упрощенная обработка события с сессией БД.
        
        Args:
            handler: Следующий handler в цепочке
            event: Событие от Telegram
            data: Словарь с данными для передачи в handler
            
        Returns:
            Any: Результат выполнения handler
        """
            session_maker = SessionLocal or get_session_maker()
            if session_maker is None:
                logger.error("❌ SessionLocal не инициализирован!")
                return
        
        async with session_maker() as session:
            data["session"] = session
            
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Ошибка в handler: {e}", exc_info=True)
                raise
            finally:
                await session.close()


def setup_middleware(dp) -> None:
    """
    Регистрирует database middleware в dispatcher.
    
    Args:
        dp: Dispatcher от aiogram
        
    Example:
        from aiogram import Dispatcher
        from app.middleware.database import setup_middleware
        
        dp = Dispatcher()
        setup_middleware(dp)
    """
    # Выбираем middleware в зависимости от настроек
    if settings.APP_ENV == "development":
        # В разработке используем расширенный middleware с детальным логированием
        middleware = DatabaseMiddleware()
        logger.info("✅ Включен DatabaseMiddleware с расширенным логированием")
    else:
        # В production используем упрощенный middleware
        middleware = DatabaseSessionMiddleware()
        logger.info("✅ Включен DatabaseSessionMiddleware (упрощенный)")
    
    # Регистрируем middleware для всех типов событий
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    
    logger.info("✅ Database middleware зарегистрирован в dispatcher")
