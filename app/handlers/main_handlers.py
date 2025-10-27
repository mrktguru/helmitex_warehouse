"""
Главные обработчики: меню, навигация, базовые команды.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import OWNER_TELEGRAM_ID
from app.logger import get_logger

logger = get_logger("main_handlers")


# ============================================================================
# КЛАВИАТУРЫ (МЕНЮ)
# ============================================================================

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню с учетом прав пользователя."""
    keyboard = [
        [
            InlineKeyboardButton("📥 Приход сырья", callback_data="arrival_menu"),
            InlineKeyboardButton("⚙️ Производство", callback_data="production_menu")
        ],
        [
            InlineKeyboardButton("📦 Фасовка", callback_data="packing_menu"),
            InlineKeyboardButton("🚚 Отгрузка", callback_data="shipment_menu")
        ],
        [
            InlineKeyboardButton("📊 Остатки", callback_data="stock_menu"),
            InlineKeyboardButton("📈 История", callback_data="history_menu")
        ]
    ]
    
    # Кнопка настроек только для администратора
    if user_id == OWNER_TELEGRAM_ID:
        keyboard.append([
            InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data="admin_settings")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def get_stock_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню остатков."""
    keyboard = [
        [InlineKeyboardButton("🌾 Сырье", callback_data="stock_raw")],
        [InlineKeyboardButton("⚙️ Полуфабрикаты", callback_data="stock_semi")],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data="stock_finished")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек (только для админа)."""
    keyboard = [
        [InlineKeyboardButton("📁 Категории", callback_data="admin_categories")],
        [InlineKeyboardButton("🌾 Сырье", callback_data="admin_raw_materials")],
        [InlineKeyboardButton("⚙️ Полуфабрикаты", callback_data="admin_semi_products")],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data="admin_finished_products")],
        [InlineKeyboardButton("📋 Технологические карты", callback_data="admin_recipes")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """Кнопка назад."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Назад", callback_data=callback_data)
    ]])


# ============================================================================
# КОМАНДЫ
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")
    
    is_admin = user.id == OWNER_TELEGRAM_ID
    admin_text = "\n\n🔐 *Вы вошли как администратор*" if is_admin else ""
    
    await update.message.reply_text(
        f"👋 *Добро пожаловать в Helmitex Warehouse!*\n\n"
        f"Система складского учета для управления:\n"
        f"• Приходом сырья\n"
        f"• Производством полуфабрикатов\n"
        f"• Фасовкой готовой продукции\n"
        f"• Отгрузками{admin_text}\n\n"
        f"Выберите раздел:",
        reply_markup=get_main_menu_keyboard(user.id),
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи."""
    help_text = (
        "ℹ️ *Справка по боту*\n\n"
        "*Основные операции:*\n"
        "📥 *Приход сырья* - оформление поступления сырья на склад\n"
        "⚙️ *Производство* - замес полуфабрикатов по технологическим картам\n"
        "📦 *Фасовка* - упаковка полуфабрикатов в готовую продукцию\n"
        "🚚 *Отгрузка* - отгрузка готовой продукции\n\n"
        "*Просмотр данных:*\n"
        "📊 *Остатки* - текущие остатки на складе\n"
        "📈 *История* - история всех операций\n\n"
        "*Команды:*\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/stock - Быстрый просмотр остатков\n\n"
        "*Поддержка:* @your_support"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown"
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрый просмотр остатков."""
    await update.message.reply_text(
        "📊 *Остатки на складе*\n\nВыберите категорию:",
        reply_markup=get_stock_menu_keyboard(),
        parse_mode="Markdown"
    )


# ============================================================================
# ОБРАБОТЧИКИ CALLBACK (НАВИГАЦИЯ)
# ============================================================================

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    is_admin = user_id == OWNER_TELEGRAM_ID
    admin_text = "\n\n🔐 *Режим администратора*" if is_admin else ""
    
    await query.edit_message_text(
        f"🏠 *Главное меню*{admin_text}\n\nВыберите раздел:",
        reply_markup=get_main_menu_keyboard(user_id),
        parse_mode="Markdown"
    )


async def stock_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню остатков."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 *Остатки на складе*\n\nВыберите категорию:",
        reply_markup=get_stock_menu_keyboard(),
        parse_mode="Markdown"
    )


async def admin_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек (только для админа)."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    await query.edit_message_text(
        "⚙️ *НАСТРОЙКИ*\n\n"
        "Управление справочниками системы.\n"
        "Выберите раздел:",
        reply_markup=get_admin_settings_keyboard(),
        parse_mode="Markdown"
    )


async def history_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню истории операций."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Приход сырья", callback_data="history_arrival")],
        [InlineKeyboardButton("⚙️ Производство", callback_data="history_production")],
        [InlineKeyboardButton("📦 Фасовка", callback_data="history_packing")],
        [InlineKeyboardButton("🚚 Отгрузка", callback_data="history_shipment")],
        [InlineKeyboardButton("📊 Все операции", callback_data="history_all")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "📈 *История операций*\n\nВыберите тип операций:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
