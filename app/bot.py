"""
Главный файл Telegram бота для системы управления складом (aiogram 3.x).

Этот модуль:
- Создает Router для регистрации handlers
- Регистрирует все handlers из модулей
- Настраивает команды бота
- Предоставляет функцию register_handlers() для main.py
"""

import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database.models import User

# Настройка логирования
logger = logging.getLogger(__name__)


# ============================================================================
# СОЗДАНИЕ ГЛАВНОГО РОУТЕРА
# ============================================================================

main_router = Router(name="main")


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_main_menu_keyboard(user: User | None = None) -> InlineKeyboardMarkup:
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
            buttons.append([InlineKeyboardButton(text="📥 Приемка сырья", callback_data='arrival_start')])
        
        if user.can_produce:
            buttons.append([InlineKeyboardButton(text="🏭 Производство", callback_data='production_start')])
        
        if user.can_pack:
            buttons.append([InlineKeyboardButton(text="📦 Фасовка", callback_data='packing_start')])
        
        if user.can_ship:
            buttons.append([InlineKeyboardButton(text="🚚 Отгрузка", callback_data='shipment_start')])
        
        # Информационные кнопки (доступны всем)
        buttons.append([InlineKeyboardButton(text="📊 Остатки", callback_data='stock_start')])
        buttons.append([InlineKeyboardButton(text="📜 История", callback_data='history_start')])
        
        # Административная кнопка
        if user.is_admin:
            buttons.append([InlineKeyboardButton(text="👨‍💼 Администрирование", callback_data='admin_start')])
        
        # Справка
        buttons.append([InlineKeyboardButton(text="❓ Справка", callback_data='help')])
    else:
        # Меню для незарегистрированного пользователя
        buttons.append([InlineKeyboardButton(text="📖 Справка", callback_data='help')])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# КОМАНДА /START
# ============================================================================

@main_router.message(CommandStart())
async def start_command(message: Message, session: AsyncSession) -> None:
    """
    Обрабатывает команду /start.
    
    Регистрирует нового пользователя или приветствует существующего.
    """
    user = message.from_user
    
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
            keyboard = get_main_menu_keyboard(existing_user)
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
                "После назначения прав вам будут доступны операции."
            )
            keyboard = get_main_menu_keyboard(new_user)
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in start_command: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте позже."
        )


# ============================================================================
# КОМАНДА /HELP
# ============================================================================

@main_router.message(Command("help"))
async def help_command(message: Message, session: AsyncSession) -> None:
    """
    Обрабатывает команду /help.
    
    Показывает справку по доступным командам.
    """
    user = message.from_user
    
    try:
        # Получение пользователя
        stmt = select(User).where(User.telegram_id == user.id)
        db_user = await session.scalar(stmt)
        
        if not db_user:
            await message.answer(
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data='main_menu')]
        ])
        
        await message.answer(
            help_text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in help_command: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже."
        )


# ============================================================================
# CALLBACK: ГЛАВНОЕ МЕНЮ
# ============================================================================

@main_router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает главное меню при нажатии на кнопку.
    """
    await callback.answer()
    user = callback.from_user
    
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
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при загрузке меню."
        )


# ============================================================================
# CALLBACK: СПРАВКА
# ============================================================================

@main_router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Показывает справку при нажатии на кнопку.
    """
    await callback.answer()
    
    # Создаём фейковое сообщение для переиспользования логики help_command
    await help_command(callback.message, session)


# ============================================================================
# НЕИЗВЕСТНЫЕ КОМАНДЫ
# ============================================================================

@main_router.message(F.text.startswith('/'))
async def unknown_command(message: Message) -> None:
    """
    Обрабатывает неизвестные команды.
    
    В aiogram 3.x фильтр Command() требует хотя бы один аргумент.
    Для catch-all неизвестных команд используем F.text.startswith('/').
    """
    await message.answer(
        "❌ Неизвестная команда.\n"
        "Используйте /help для просмотра доступных команд."
    )


# ============================================================================
# НАСТРОЙКА КОМАНД БОТА
# ============================================================================

async def setup_bot_commands(bot: Bot) -> None:
    """
    Настраивает список команд бота в меню Telegram.
    
    Args:
        bot: Экземпляр бота
    """
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="arrival", description="Приемка сырья"),
        BotCommand(command="production", description="Производство"),
        BotCommand(command="packing", description="Фасовка"),
        BotCommand(command="shipment", description="Отгрузка"),
        BotCommand(command="stock", description="Остатки"),
        BotCommand(command="history", description="История"),
        BotCommand(command="admin", description="Администрирование"),
        BotCommand(command="cancel", description="Отмена"),
    ]
    
    await bot.set_my_commands(commands)
    logger.info("✅ Bot commands configured")


# ============================================================================
# ФУНКЦИЯ РЕГИСТРАЦИИ HANDLERS (для main.py)
# ============================================================================

def register_handlers(dp) -> None:
    """
    Регистрирует все handlers в dispatcher.
    
    Эта функция вызывается из main.py для подключения всех роутеров.
    
    Args:
        dp: Dispatcher из aiogram
    """
    logger.info("=" * 60)
    logger.info("🔧 РЕГИСТРАЦИЯ HANDLERS")
    logger.info("=" * 60)
    
    # 1. Главный роутер (команды /start, /help)
    dp.include_router(main_router)
    logger.info("✅ Main router registered")
    
    # 2. Административные панели (проверяют права)
    try:
        from app.handlers.admin_users import router as admin_users_router
        dp.include_router(admin_users_router)
        logger.info("✅ Admin users router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import admin_users router: {e}")
    
    try:
        from app.handlers.admin_warehouse import router as admin_warehouse_router
        dp.include_router(admin_warehouse_router)
        logger.info("✅ Admin warehouse router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import admin_warehouse router: {e}")
    
    # 3. Основные бизнес-процессы
    try:
        from app.handlers.arrival import arrival_router
        dp.include_router(arrival_router)
        logger.info("✅ Arrival router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import arrival router: {e}")
    
    try:
        from app.handlers.production import production_router
        dp.include_router(production_router)
        logger.info("✅ Production router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import production router: {e}")
    
    try:
        from app.handlers.packing import packing_router
        dp.include_router(packing_router)
        logger.info("✅ Packing router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import packing router: {e}")
    
    try:
        from app.handlers.shipment import shipment_router
        dp.include_router(shipment_router)
        logger.info("✅ Shipment router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import shipment router: {e}")
    
    # 4. Просмотр данных
    try:
        from app.handlers.stock import stock_router
        dp.include_router(stock_router)
        logger.info("✅ Stock router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import stock router: {e}")
    
    try:
        from app.handlers.history import router as history_router
        dp.include_router(history_router)
        logger.info("✅ History router registered")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import history router: {e}")
    
    # 5. Дополнительные handlers (если есть)
    try:
        from app.handlers.main_handlers import main_handlers_router
        dp.include_router(main_handlers_router)
        logger.info("✅ Main handlers router registered")
    except ImportError as e:
        logger.debug(f"ℹ️ Main handlers router not found: {e}")
    
    logger.info("=" * 60)
    logger.info("✅ HANDLER REGISTRATION COMPLETED")
    logger.info("=" * 60)
