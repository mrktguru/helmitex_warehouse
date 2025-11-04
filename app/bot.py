"""
Главный файл Telegram бота для системы управления складом.

Этот модуль:
- Инициализирует Application
- Регистрирует все handlers
- Настраивает команды бота
- Обрабатывает ошибки
- Управляет жизненным циклом приложения
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import User, get_session, engine
from app.handlers import (
    get_arrival_handler,
    get_production_handler,
    get_packing_handler,
    get_shipment_handler,
    get_stock_handler,
    get_history_handler,
    get_admin_warehouse_handler,
    get_admin_users_handler,
    get_handler_commands,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================================================
# MIDDLEWARE ДЛЯ СЕССИЙ БД
# ============================================================================

async def db_session_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Middleware для создания и управления сессиями БД.
    
    Создает новую сессию для каждого обновления и сохраняет её в context.bot_data.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        context.bot_data['db_session'] = session
        try:
            # Обработка обновления происходит здесь
            yield
            # Автоматический commit при успехе
            await session.commit()
        except Exception as e:
            # Автоматический rollback при ошибке
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            # Очистка сессии
            context.bot_data.pop('db_session', None)


# ============================================================================
# КОМАНДА /START
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.
    
    Регистрирует нового пользователя или приветствует существующего.
    """
    user = update.effective_user
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Проверка существования пользователя
        stmt = select(User).where(User.telegram_id == user.id)
        existing_user = await session.scalar(stmt)
        
        if existing_user:
            # Обновление информации
            existing_user.username = user.username
            existing_user.last_active = datetime.utcnow()
            await session.commit()
            
            welcome_text = (
                f"👋 Добро пожаловать, <b>{user.first_name}!</b>\n\n"
                "Выберите действие из меню ниже:"
            )
            is_new = False
        else:
            # Регистрация нового пользователя
            new_user = User(
                telegram_id=user.id,
                username=user.username,
                is_active=True,
                # По умолчанию нет прав, админ должен назначить
                can_receive_materials=False,
                can_produce=False,
                can_pack=False,
                can_ship=False,
                is_admin=False
            )
            session.add(new_user)
            await session.commit()
            
            welcome_text = (
                f"👋 Добро пожаловать в систему, <b>{user.first_name}!</b>\n\n"
                "✅ Вы успешно зарегистрированы.\n\n"
                "⚠️ <b>Права доступа не назначены.</b>\n"
                "Обратитесь к администратору для получения прав.\n\n"
                "После назначения прав вам будут доступны операции:"
            )
            is_new = True
        
        # Главное меню
        keyboard = get_main_menu_keyboard(existing_user if not is_new else new_user)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при регистрации. Попробуйте позже."
        )


# ============================================================================
# КОМАНДА /HELP
# ============================================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /help.
    
    Показывает справку по доступным командам.
    """
    user = update.effective_user
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение пользователя
        stmt = select(User).where(User.telegram_id == user.id)
        db_user = await session.scalar(stmt)
        
        if not db_user:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте /start"
            )
            return
        
        help_text = (
            "📖 <b>Справка по системе</b>\n\n"
            "<b>Основные команды:</b>\n"
            "/start - Запуск бота и регистрация\n"
            "/help - Эта справка\n"
            "/cancel - Отмена текущей операции\n\n"
        )
        
        # Операционные команды
        if any([db_user.can_receive_materials, db_user.can_produce, 
                db_user.can_pack, db_user.can_ship]):
            help_text += "<b>Операции:</b>\n"
            
            if db_user.can_receive_materials:
                help_text += "📥 /arrival - Приемка сырья на склад\n"
            
            if db_user.can_produce:
                help_text += "🏭 /production - Производство полуфабрикатов\n"
            
            if db_user.can_pack:
                help_text += "📦 /packing - Фасовка готовой продукции\n"
            
            if db_user.can_ship:
                help_text += "🚚 /shipment - Отгрузка продукции\n"
            
            help_text += "\n"
        
        # Информационные команды (доступны всем)
        help_text += (
            "<b>Информация:</b>\n"
            "📊 /stock - Просмотр остатков\n"
            "📜 /history - История операций\n\n"
        )
        
        # Административные команды
        if db_user.is_admin:
            help_text += (
                "<b>Администрирование:</b>\n"
                "👨‍💼 /admin - Административная панель\n"
                "  • Управление складами\n"
                "  • Управление номенклатурой\n"
                "  • Технологические карты\n"
                "  • Управление пользователями\n\n"
            )
        
        help_text += (
            "<b>О системе:</b>\n"
            "Система управления складом для производства "
            "краски и шпатлевки с полным циклом:\n"
            "  Сырье → Производство → Фасовка → Отгрузка\n\n"
            "По вопросам обращайтесь к администратору."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
        ])
        
        await update.message.reply_text(
            help_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже."
        )


# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

def get_main_menu_keyboard(user: Optional[User] = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню на основе прав пользователя.
    
    Args:
        user: Объект пользователя из БД
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с доступными кнопками
    """
    buttons = []
    
    if user:
        # Операционные кнопки
        if user.can_receive_materials:
            buttons.append([InlineKeyboardButton("📥 Приемка сырья", callback_data='arrival_start')])
        
        if user.can_produce:
            buttons.append([InlineKeyboardButton("🏭 Производство", callback_data='production_start')])
        
        if user.can_pack:
            buttons.append([InlineKeyboardButton("📦 Фасовка", callback_data='packing_start')])
        
        if user.can_ship:
            buttons.append([InlineKeyboardButton("🚚 Отгрузка", callback_data='shipment_start')])
        
        # Информационные кнопки (доступны всем)
        buttons.append([InlineKeyboardButton("📊 Остатки", callback_data='stock_view_start')])
        buttons.append([InlineKeyboardButton("📜 История", callback_data='history_start')])
        
        # Административная кнопка
        if user.is_admin:
            buttons.append([InlineKeyboardButton("👨‍💼 Администрирование", callback_data='admin_panel_start')])
        
        # Справка
        buttons.append([InlineKeyboardButton("❓ Справка", callback_data='help')])
    else:
        # Меню для незарегистрированного пользователя
        buttons.append([InlineKeyboardButton("📖 Справка", callback_data='help')])
    
    return InlineKeyboardMarkup(buttons)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает главное меню.
    """
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение пользователя
        stmt = select(User).where(User.telegram_id == user.id)
        db_user = await session.scalar(stmt)
        
        if not db_user:
            text = (
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации."
            )
            keyboard = None
        else:
            # Обновление времени активности
            db_user.last_active = datetime.utcnow()
            await session.commit()
            
            text = (
                f"🏠 <b>Главное меню</b>\n\n"
                f"Пользователь: @{db_user.username or 'неизвестен'}\n"
            )
            
            # Показ прав
            permissions = []
            if db_user.can_receive_materials:
                permissions.append("Приемка")
            if db_user.can_produce:
                permissions.append("Производство")
            if db_user.can_pack:
                permissions.append("Фасовка")
            if db_user.can_ship:
                permissions.append("Отгрузка")
            if db_user.is_admin:
                permissions.append("Администратор")
            
            if permissions:
                text += f"Права: {', '.join(permissions)}\n"
            
            text += "\nВыберите действие:"
            
            keyboard = get_main_menu_keyboard(db_user)
        
        if query:
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        
    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}")
        error_text = "❌ Произошла ошибка при загрузке меню."
        
        if query:
            await query.message.edit_text(error_text)
        else:
            await update.message.reply_text(error_text)


# ============================================================================
# ОБРАБОТКА ОШИБОК
# ============================================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает ошибки, возникающие при работе бота.
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Пытаемся отправить сообщение пользователю
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка при обработке вашего запроса.\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
    except Exception as e:
        logger.error(f"Error in error_handler: {e}")


# ============================================================================
# ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД
# ============================================================================

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает неизвестные команды.
    """
    await update.message.reply_text(
        "❌ Неизвестная команда.\n"
        "Используйте /help для просмотра доступных команд."
    )


# ============================================================================
# НАСТРОЙКА КОМАНД БОТА
# ============================================================================

async def setup_commands(application: Application) -> None:
    """
    Настраивает список команд бота в меню Telegram.
    """
    commands = [
        BotCommand("start", "Запуск бота"),
        BotCommand("help", "Справка"),
        BotCommand("arrival", "Приемка сырья"),
        BotCommand("production", "Производство"),
        BotCommand("packing", "Фасовка"),
        BotCommand("shipment", "Отгрузка"),
        BotCommand("stock", "Остатки"),
        BotCommand("history", "История"),
        BotCommand("admin", "Администрирование"),
        BotCommand("cancel", "Отмена"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands configured")


# ============================================================================
# POST_INIT И POST_SHUTDOWN
# ============================================================================

async def post_init(application: Application) -> None:
    """
    Выполняется после инициализации бота.
    """
    logger.info("Bot started successfully")
    await setup_commands(application)
    
    # Можно добавить уведомление администратору о запуске
    # admin_id = settings.ADMIN_TELEGRAM_ID
    # if admin_id:
    #     await application.bot.send_message(
    #         admin_id,
    #         "✅ Бот запущен и готов к работе!"
    #     )


async def post_shutdown(application: Application) -> None:
    """
    Выполняется перед остановкой бота.
    """
    logger.info("Bot shutting down...")
    
    # Закрытие соединений с БД
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main() -> None:
    """
    Главная функция запуска бота.
    """
    # Создание Application
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Базовые команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(show_main_menu, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(help_command, pattern='^help$'))
    
    # Регистрация всех ConversationHandlers
    # Группа 0 - Административные handlers (высокий приоритет)
    application.add_handler(get_admin_warehouse_handler(), group=0)
    application.add_handler(get_admin_users_handler(), group=0)
    
    # Группа 1 - Операционные handlers
    application.add_handler(get_arrival_handler(), group=1)
    application.add_handler(get_production_handler(), group=1)
    application.add_handler(get_packing_handler(), group=1)
    application.add_handler(get_shipment_handler(), group=1)
    
    # Группа 2 - Информационные handlers
    application.add_handler(get_stock_handler(), group=2)
    application.add_handler(get_history_handler(), group=2)
    
    # Обработчик неизвестных команд (последний)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("Starting bot polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == '__main__':
    main()
