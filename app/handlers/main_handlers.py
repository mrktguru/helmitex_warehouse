"""
Главные обработчики: меню, навигация, базовые команды (aiogram 3.x).
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("main_handlers")

# Создаём роутер для главных handlers
main_handlers_router = Router(name="main_handlers")


# ============================================================================
# КЛАВИАТУРЫ (МЕНЮ)
# ============================================================================

def get_main_menu_keyboard(user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню с учетом прав пользователя."""
    keyboard = [
        [
            InlineKeyboardButton(text="📥 Приход сырья", callback_data="arrival_menu"),
            InlineKeyboardButton(text="⚙️ Производство", callback_data="production_menu")
        ],
        [
            InlineKeyboardButton(text="📦 Фасовка", callback_data="packing_menu"),
            InlineKeyboardButton(text="🚚 Отгрузка", callback_data="shipment_menu")
        ],
        [
            InlineKeyboardButton(text="📊 Остатки", callback_data="stock_menu"),
            InlineKeyboardButton(text="📈 История", callback_data="history_menu")
        ]
    ]
    
    # Кнопка настроек только для администратора
    if is_admin or user_id in settings.ADMIN_IDS:
        keyboard.append([
            InlineKeyboardButton(text="⚙️ НАСТРОЙКИ", callback_data="admin_settings")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_stock_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню остатков."""
    keyboard = [
        [InlineKeyboardButton(text="🌾 Сырье", callback_data="stock_raw")],
        [InlineKeyboardButton(text="⚙️ Полуфабрикаты", callback_data="stock_semi")],
        [InlineKeyboardButton(text="📦 Готовая продукция", callback_data="stock_finished")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек (только для админа)."""
    keyboard = [
        [InlineKeyboardButton(text="📁 Категории", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🌾 Сырье", callback_data="admin_raw_materials")],
        [InlineKeyboardButton(text="⚙️ Полуфабрикаты", callback_data="admin_semi_products")],
        [InlineKeyboardButton(text="📦 Готовая продукция", callback_data="admin_finished_products")],
        [InlineKeyboardButton(text="📋 Технологические карты", callback_data="admin_recipes")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_button(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """Кнопка назад."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)
    ]])


# ============================================================================
# КОМАНДЫ
# ============================================================================

@main_handlers_router.message(Command("help"))
async def help_command(message: Message):
    """Команда помощи."""
    help_text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        "<b>Основные операции:</b>\n"
        "📥 <b>Приход сырья</b> - оформление поступления сырья на склад\n"
        "⚙️ <b>Производство</b> - замес полуфабрикатов по технологическим картам\n"
        "📦 <b>Фасовка</b> - упаковка полуфабрикатов в готовую продукцию\n"
        "🚚 <b>Отгрузка</b> - отгрузка готовой продукции\n\n"
        "<b>Просмотр данных:</b>\n"
        "📊 <b>Остатки</b> - текущие остатки на складе\n"
        "📈 <b>История</b> - история всех операций\n\n"
        "<b>Команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/stock - Быстрый просмотр остатков\n\n"
        "<b>Поддержка:</b> @your_support"
    )
    
    await message.answer(help_text)


@main_handlers_router.message(Command("stock"))
async def stock_command(message: Message):
    """Быстрый просмотр остатков."""
    await message.answer(
        "📊 <b>Остатки на складе</b>\n\nВыберите категорию:",
        reply_markup=get_stock_menu_keyboard()
    )


# ============================================================================
# ОБРАБОТЧИКИ CALLBACK (НАВИГАЦИЯ)
# ============================================================================

@main_handlers_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Возврат в главное меню."""
    await callback.answer()
    
    user_id = callback.from_user.id
    is_admin = user_id in settings.ADMIN_IDS
    admin_text = "\n\n🔐 <b>Режим администратора</b>" if is_admin else ""
    
    await callback.message.edit_text(
        f"🏠 <b>Главное меню</b>{admin_text}\n\nВыберите раздел:",
        reply_markup=get_main_menu_keyboard(user_id, is_admin)
    )


@main_handlers_router.callback_query(F.data == "stock_menu")
async def stock_menu_callback(callback: CallbackQuery):
    """Меню остатков."""
    await callback.answer()
    
    await callback.message.edit_text(
        "📊 <b>Остатки на складе</b>\n\nВыберите категорию:",
        reply_markup=get_stock_menu_keyboard()
    )


@main_handlers_router.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: CallbackQuery):
    """Меню настроек (только для админа)."""
    user_id = callback.from_user.id
    
    if user_id not in settings.ADMIN_IDS:
        await callback.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await callback.answer()
    
    await callback.message.edit_text(
        "⚙️ <b>НАСТРОЙКИ</b>\n\n"
        "Управление справочниками системы.\n"
        "Выберите раздел:",
        reply_markup=get_admin_settings_keyboard()
    )


@main_handlers_router.callback_query(F.data == "history_menu")
async def history_menu_callback(callback: CallbackQuery):
    """Меню истории операций."""
    await callback.answer()
    
    keyboard = [
        [InlineKeyboardButton(text="📥 Приход сырья", callback_data="history_arrival")],
        [InlineKeyboardButton(text="⚙️ Производство", callback_data="history_production")],
        [InlineKeyboardButton(text="📦 Фасовка", callback_data="history_packing")],
        [InlineKeyboardButton(text="🚚 Отгрузка", callback_data="history_shipment")],
        [InlineKeyboardButton(text="📊 Все операции", callback_data="history_all")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "📈 <b>История операций</b>\n\nВыберите тип операций:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
