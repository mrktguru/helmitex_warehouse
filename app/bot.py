"""
Главный модуль Telegram бота с инлайн-кнопками и ConversationHandler.
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
from app.handlers.arrival_handler import (
    arrival_start,
    select_category,
    select_sku,
    enter_quantity,
    confirm_arrival,
    SELECT_CATEGORY,
    SELECT_SKU,
    ENTER_QUANTITY,
    CONFIRM
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


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
            InlineKeyboardButton("📦 Товары", callback_data="settings_skus"),
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
    
    elif data == "arrival_history":
        with get_db() as db:
            from app.services import movement_service
            from app.database.models import MovementType
            
            try:
                user = update.effective_user
                db_user = user_service.get_or_create_user(
                    db=db,
                    telegram_id=user.id,
                    username=user.username,
                    full_name=user.full_name
                )
                
                movements = movement_service.get_user_movements(db, db_user.id, limit=10)
                # Фильтруем только приходы
                arrivals = [m for m in movements if m.type == MovementType.in_]
                
                if arrivals:
                    text = "📋 *История прихода сырья:*\n\n"
                    for mov in arrivals:
                        text += f"• {mov.sku.name}\n"
                        text += f"  Количество: {mov.quantity} {mov.sku.unit.value}\n"
                        text += f"  Дата: {mov.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                else:
                    text = "📋 *История прихода сырья*\n\nОпераций пока нет."
            except Exception as e:
                logger.error(f"Error: {e}")
                text = "❌ Ошибка при загрузке истории"
        
        await query.edit_message_text(
            text,
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
            "Функция в разработке.",
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
    
    elif data == "settings_skus":
        with get_db() as db:
            from app.services import sku_service
            try:
                skus = sku_service.get_all_skus(db)
                if skus:
                    text = "📦 *Товары:*\n\n"
                    for sku in skus[:10]:
                        text += f"• {sku.name}"
                        if sku.category:
                            text += f" ({sku.category.value})"
                        text += f" - {sku.unit.value}\n"
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
        with get_db() as db:
            from app.services import stock_service, warehouse_service
            
            try:
                warehouse = warehouse_service.get_default_warehouse(db)
                
                if not warehouse:
                    text = "📊 *Остатки*\n\nСклад не найден."
                else:
                    stocks = stock_service.get_warehouse_stock(db, warehouse.id)
                    
                    if stocks:
                        text = f"📊 *Остатки на складе {warehouse.name}:*\n\n"
                        for stock in stocks[:15]:
                            text += f"• {stock.sku.name}\n"
                            text += f"  {stock.quantity} {stock.sku.unit.value}\n"
                        if len(stocks) > 15:
                            text += f"\n_...и еще {len(stocks) - 15} позиций_"
                    else:
                        text = "📊 *Остатки*\n\nНет остатков на складе."
            except Exception as e:
                logger.error(f"Error: {e}")
                text = "❌ Ошибка при загрузке остатков"
        
        await query.edit_message_text(
            text,
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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text(
        "❌ Операция отменена",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


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

        # ConversationHandler для прихода сырья
        arrival_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(arrival_start, pattern="^arrival_add$")],
            states={
                SELECT_CATEGORY: [CallbackQueryHandler(select_category, pattern="^cat_")],
                SELECT_SKU: [CallbackQueryHandler(select_sku, pattern="^sku_")],
                ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
                CONFIRM: [CallbackQueryHandler(confirm_arrival, pattern="^(confirm_arrival|cancel_arrival)$")]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True
        )

        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(arrival_conv_handler)
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
