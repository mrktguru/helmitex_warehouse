"""
Декораторы для проверки прав доступа.
"""
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from app.config import OWNER_TELEGRAM_ID
from app.logger import get_logger

logger = get_logger("decorators")


def admin_only(func):
    """
    Декоратор для ограничения доступа только администратору.
    
    Использование:
        @admin_only
        async def admin_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if user_id != OWNER_TELEGRAM_ID:
            logger.warning(f"Попытка доступа к админской функции от пользователя {user_id}")
            
            # Если это callback query
            if update.callback_query:
                await update.callback_query.answer(
                    "❌ У вас нет прав для этой операции",
                    show_alert=True
                )
            # Если это обычное сообщение
            else:
                await update.message.reply_text(
                    "❌ У вас нет прав для этой операции.\n"
                    "Эта функция доступна только администратору."
                )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def with_db_session(func):
    """
    Декоратор для автоматического управления сессией БД.
    
    Использование:
        @with_db_session
        async def some_function(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Session):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from app.database.db import SessionLocal
        
        db = SessionLocal()
        try:
            result = await func(update, context, db=db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка в функции {func.__name__}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    return wrapper
