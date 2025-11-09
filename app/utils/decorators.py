"""
Декораторы для проверки прав доступа (aiogram 3.x).
"""
from functools import wraps
from typing import Callable, Any
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("decorators")


def admin_only(func: Callable) -> Callable:
    """
    Декоратор для ограничения доступа только администраторам.
    
    В aiogram 3.x проверяет права через settings.ADMIN_IDS.
    
    Использование:
        @admin_only
        async def admin_function(message: Message, session: AsyncSession):
            ...
            
        @admin_only
        async def admin_callback(callback: CallbackQuery, session: AsyncSession):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Получаем первый аргумент (Message или CallbackQuery)
        event = args[0] if args else None
        
        if not event:
            logger.error("admin_only: не передано событие")
            return
        
        # Определяем пользователя
        if isinstance(event, Message):
            user_id = event.from_user.id
            message = event
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            message = event.message
        else:
            logger.error(f"admin_only: неизвестный тип события {type(event)}")
            return
        
        # Проверяем права администратора
        if user_id not in settings.ADMIN_IDS:
            logger.warning(f"Попытка доступа к админской функции от пользователя {user_id}")
            
            error_text = (
                "❌ У вас нет прав для этой операции.\n"
                "Эта функция доступна только администраторам."
            )
            
            # Отправляем сообщение об ошибке
            if isinstance(event, CallbackQuery):
                await event.answer(error_text, show_alert=True)
                if message:
                    try:
                        await message.answer(error_text)
                    except Exception:
                        pass
            else:
                await message.answer(error_text)
            
            return
        
        # Если проверка прошла - вызываем функцию
        return await func(*args, **kwargs)
    
    return wrapper


def owner_only(func: Callable) -> Callable:
    """
    Декоратор для ограничения доступа только владельцу (первый ID в ADMIN_IDS).
    
    Использование:
        @owner_only
        async def owner_function(message: Message, session: AsyncSession):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Получаем первый аргумент (Message или CallbackQuery)
        event = args[0] if args else None
        
        if not event:
            logger.error("owner_only: не передано событие")
            return
        
        # Определяем пользователя
        if isinstance(event, Message):
            user_id = event.from_user.id
            message = event
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            message = event.message
        else:
            logger.error(f"owner_only: неизвестный тип события {type(event)}")
            return
        
        # Проверяем, что это владелец (первый админ)
        owner_id = settings.ADMIN_IDS[0] if settings.ADMIN_IDS else None
        
        if not owner_id or user_id != owner_id:
            logger.warning(f"Попытка доступа к функции владельца от пользователя {user_id}")
            
            error_text = (
                "❌ У вас нет прав для этой операции.\n"
                "Эта функция доступна только владельцу системы."
            )
            
            # Отправляем сообщение об ошибке
            if isinstance(event, CallbackQuery):
                await event.answer(error_text, show_alert=True)
                if message:
                    try:
                        await message.answer(error_text)
                    except Exception:
                        pass
            else:
                await message.answer(error_text)
            
            return
        
        # Если проверка прошла - вызываем функцию
        return await func(*args, **kwargs)
    
    return wrapper


def with_db_session(func: Callable) -> Callable:
    """
    Декоратор для автоматического управления сессией БД.
    
    ⚠️ ВНИМАНИЕ: В aiogram 3.x с middleware этот декоратор обычно НЕ НУЖЕН!
    Сессия автоматически передается через DatabaseMiddleware.
    
    Оставлен для совместимости, но рекомендуется использовать
    session из параметра handler'а напрямую.
    
    Использование:
        @with_db_session
        async def some_function(message: Message, session: AsyncSession):
            # session уже передан через middleware
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # В aiogram 3.x сессия передается через middleware
        # Этот декоратор просто пробрасывает вызов
        logger.debug(f"with_db_session: вызов {func.__name__}")
        return await func(*args, **kwargs)
    
    return wrapper


# Для обратной совместимости со старым кодом
def check_admin(func: Callable) -> Callable:
    """
    Алиас для admin_only для обратной совместимости.
    
    Deprecated: используйте @admin_only
    """
    logger.warning("check_admin устарел, используйте @admin_only")
    return admin_only(func)
