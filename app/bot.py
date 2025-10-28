"""
Главный модуль Telegram бота с инлайн-кнопками.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

from app.database.db import init_db, get_db
from app.config import TELEGRAM_BOT_TOKEN
from app.services import user_service

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAIN_MENU = 0
ARRIVAL_MENU = 1
PRODUCTION_MENU = 2
SHIPMENT_MENU = 3
SETTINGS_MENU = 4


# ============= КЛАВИАТУРЫ =============

def get_main_keyboard():
    """Главное меню с инлайн-кнопками"""
    keyboard = [
        [
            InlineKeyboardButton("📥 Приход сырья", callback_data="arrival"),
            InlineKeyboardButton("🏭 Выпуск продукции", callback_data="production")
        ],
        [
            InlineKeyboardButton("📤 Отгрузка", callback_data="shipment"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📊 Остатки", callback_data="stock"),
            InlineKeyboardButton("📋 История", callback_data="history")
        ],
        [
            InlineKeyboardButton("ℹ️ Справка", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_arrival_keyboard():
    """Меню прихода сырья"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить приход", callback_data="arrival_add")],
        [InlineKeyboardButton("📋 История прихода", callback_data="arrival_history")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_production_keyboard():
    """Меню выпуска продукции"""
    keyboard = [
        [InlineKeyboardButton("➕ Новое производство", callback_data="production_new")],
        [InlineKeyboardButton("📋 История производства", callback_data="production_history")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_shipment_keyboard():
    """Меню отгрузки"""
    keyboard = [
        [InlineKeyboardButton("➕ Новая отгрузка", callback_data="shipment_new")],
        [InlineKeyboardButton("📋 История отгрузок", callback_data="shipment_history")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_settings_keyboard():
    """Меню настроек"""
    keyboard = [
        [
            InlineKeyboardButton("🏢 Склады", callback_data="settings_warehouses"),
            InlineKeyboardButton("📦 Товары", callback_data="settings_skus")
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="settings_users"),
            InlineKeyboardButton("📊 Статистика", callback_data="settings_stats")
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard():
    """Кнопка назад"""
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)


# ============= HANDLERS =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Регистрируем пользователя
    with get_db() as db:
        db_user = user_service.get_or_create_user(
            db=db,
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name
        )
        is_admin = db_user.is_admin
    
    welcome_text = (
        f"🏭 *Helmitex Warehouse*\n\n"
        f"Добро пожаловать, {user.first_name}!\n\n"
        "Выберите действие:"
    )
    
    if is_admin:
        welcome_text += "\n\n👑 _У вас есть права администратора_"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Главное меню
    if data == "main_menu":
        await query.edit_message_text(
            "🏭 *Helmitex Warehouse*\n\nВыберите действие:",
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
    
    # Приход сырья
    elif data == "arrival":
        await query.edit_message_text(
            "📥 *Приход сырья*\n\nВыберите действие:",
            reply_markup=get_arrival_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "arrival_add":
        await query.edit_message_text(
            "➕ *Добавить приход сырья*\n\n"
            "Функция в разработке.\n"
            "Скоро здесь можно будет оформить приход сырья.",
            reply_markup=get_arrival_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "arrival_history":
        await query.edit_message_text(
            "📋 *История прихода сырья*\n\n"
            "Последние операции прихода будут отображаться здесь.",
            reply_markup=get_arrival_keyboard(),
            parse_mode='Markdown'
        )
    
    # Выпуск продукции
    elif data == "production":
        await query.edit_message_text(
            "🏭 *Выпуск продукции*\n\nВыберите действие:",
            reply_markup=get_production_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "production_new":
        await query.edit_message_text(
            "➕ *Новое производство*\n\n"
            "Функция в разработке.\n"
            "Скоро здесь можно будет оформить выпуск продукции.",
            reply_markup=get_production_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "production_history":
        await query.edit_message_text(
            "📋 *История производства*\n\n"
            "Последние операции производства будут отображаться здесь.",
            reply_markup=get_production_keyboard(),
            parse_mode='Markdown'
        )
    
    # Отгрузка
    elif data == "shipment":
        await query.edit_message_text(
            "📤 *Отгрузка*\n\nВыберите действие:",
            reply_markup=get_shipment_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "shipment_new":
        await query.edit_message_text(
            "➕ *Новая отгрузка*\n\n"
            "Функция в разработке.\n"
            "Скоро здесь можно будет оформить отгрузку.",
            reply_markup=get_shipment_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "shipment_history":
        await query.edit_message_text(
            "📋 *История отгрузок*\n\n"
            "Последние отгрузки будут отображаться здесь.",
            reply_markup=get_shipment_keyboard(),
            parse_mode='Markdown'
        )
    
    # Настройки
    elif data == "settings":
        await query.edit_message_text(
            "⚙️ *Настройки*\n\nВыберите раздел:",
            reply_markup=get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "settings_warehouses":
        with get_db() as db:
            from app.services import warehouse_service
            try:
                whs = warehouse_service.get_all_warehouses(db)
                if whs:
                    text = "🏢 *Склады:*\n\n"
                    for wh in whs:
                        text += f"• {wh.name}"
                        if wh.location:
                            text += f" ({wh.location})"
                        text += "\n"
                else:
                    text = "🏢 *Склады*\n\nСкладов пока нет."
            except Exception as e:
                logger.error(f"Error: {e}")
                text = "❌ Ошибка при загрузке складов"
        
        await query.edit_message_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "settings_skus":
        with get_db() as db:
            from app.services import sku_service
            try:
                skus = sku_service.get_all_skus(db)
                if skus:
                    text = "📦 *Товары:*\n\n"
                    for sku in skus[:10]:
                        text += f"• {sku.code} - {sku.name}\n"
                    if len(skus) > 10:
                        text += f"\n_...и еще {len(skus) - 10} товаров_"
                else:
                    text = "📦 *Товары*\n\nТоваров пока нет."
            except Exception as e:
                logger.error(f"Error: {e}")
                text = "❌ Ошибка при загрузке товаров"
        
        await query.edit_message_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "settings_users":
        await query.edit_message_text(
            "👥 *Пользователи*\n\nУправление пользователями в разработке.",
            reply_markup=get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    elif data == "settings_stats":
        with get_db() as db:
            from app.services import warehouse_service, sku_service
            try:
                wh_count = len(warehouse_service.get_all_warehouses(db))
                sku_count = len(sku_service.get_all_skus(db))
                text = (
                    "📊 *Статистика системы*\n\n"
                    f"🏢 Складов: {wh_count}\n"
                    f"📦 Товаров: {sku_count}\n"
                    f"✅ Статус: Работает"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
                text = "❌ Ошибка при загрузке статистики"
        
        await query.edit_message_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    # Остатки
    elif data == "stock":
        await query.edit_message_text(
            "📊 *Остатки на складах*\n\nФункция в разработке.",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
    
    # История
    elif data == "history":
        await query.edit_message_text(
            "📋 *История операций*\n\nФункция в разработке.",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
    
    # Справка
    elif data == "help":
        help_text = (
            "ℹ️ *Справка по системе*\n\n"
            "*Основные разделы:*\n\n"
            "📥 *Приход сырья* - регистрация поступления материалов\n"
            "🏭 *Выпуск продукции* - учет производства\n"
            "📤 *Отгрузка* - отгрузка готовой продукции\n"
            "⚙️ *Настройки* - управление системой\n\n"
            "Для начала работы выберите нужный раздел в главном меню."
        )
        await query.edit_message_text(
            help_text,
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )


# ============= MAIN =============

def main():
    """Запуск бота"""
    logger.info("=" * 80)
    logger.info("Запуск Helmitex Warehouse Bot")
    logger.info("=" * 80)

    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        init_db()
        logger.info("✅ База данных инициализирована")

        # Создание приложения
        logger.info("Создание Telegram приложения...")
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))

        logger.info("✅ Обработчики зарегистрированы")

        # Запуск polling
        logger.info("🚀 Запуск polling...")
        logger.info("Бот готов к работе!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
