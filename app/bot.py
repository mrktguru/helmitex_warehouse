"""
Главный модуль Telegram бота.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.database.db import init_db
from app.config import TELEGRAM_BOT_TOKEN
from app.database.db import get_db
from app.services import user_service

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============= HANDLERS =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Регистрируем пользователя
    with next(get_db()) as db:
        db_user = user_service.get_or_create_user(
            db=db,
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name
        )
        is_admin = db_user.is_admin
    
    welcome_text = (
        f"🏭 Добро пожаловать в Helmitex Warehouse, {user.first_name}!\n\n"
        "Система складского учета готова к работе.\n\n"
        "📋 Основные команды:\n"
        "/warehouses - Управление складами\n"
        "/skus - Управление товарами\n"
        "/stock - Просмотр остатков\n"
        "/movements - История движений\n"
        "/orders - Управление заказами\n"
        "/help - Справка\n"
        "/status - Статус системы\n"
    )
    
    if is_admin:
        welcome_text += "\n👑 У вас есть права администратора"
    
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 Справка по командам:\n\n"
        "🏢 Склады:\n"
        "/warehouses - Список складов\n\n"
        "📦 Товары:\n"
        "/skus - Список товаров\n\n"
        "📊 Остатки:\n"
        "/stock - Остатки на складах\n\n"
        "🔄 Движения:\n"
        "/movements - История движений\n\n"
        "📋 Заказы:\n"
        "/orders - Список заказов\n\n"
        "ℹ️ Прочее:\n"
        "/help - Эта справка\n"
        "/status - Статус системы\n"
    )
    await update.message.reply_text(help_text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    with next(get_db()) as db:
        from app.services import warehouse_service, sku_service
        
        try:
            warehouses_count = len(warehouse_service.get_all_warehouses(db))
            skus_count = len(sku_service.get_all_skus(db))
        except:
            warehouses_count = 0
            skus_count = 0
    
    status_text = (
        "✅ Система работает нормально\n\n"
        f"🏢 Складов: {warehouses_count}\n"
        f"📦 Товаров: {skus_count}\n"
        "📊 База данных: подключена\n"
        "🤖 Бот: активен"
    )
    await update.message.reply_text(status_text)


async def warehouses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список складов"""
    with next(get_db()) as db:
        from app.services import warehouse_service
        whs = warehouse_service.get_all_warehouses(db)
    
    if not whs:
        await update.message.reply_text("📦 Складов пока нет")
        return
    
    text = "🏢 Список складов:\n\n"
    for wh in whs:
        text += f"• {wh.name}"
        if wh.location:
            text += f" ({wh.location})"
        text += "\n"
    
    await update.message.reply_text(text)


async def skus_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список товаров"""
    with next(get_db()) as db:
        from app.services import sku_service
        skus = sku_service.get_all_skus(db)
    
    if not skus:
        await update.message.reply_text("📦 Товаров пока нет")
        return
    
    text = "📦 Список товаров:\n\n"
    for sku in skus[:20]:  # Показываем первые 20
        text += f"• {sku.code} - {sku.name} ({sku.type.value})\n"
    
    if len(skus) > 20:
        text += f"\n... и еще {len(skus) - 20} товаров"
    
    await update.message.reply_text(text)


async def stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Остатки на складах"""
    await update.message.reply_text("📊 Функция просмотра остатков в разработке")


async def movements_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История движений"""
    await update.message.reply_text("🔄 Функция истории движений в разработке")


async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список заказов"""
    await update.message.reply_text("📋 Функция управления заказами в разработке")


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
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("warehouses", warehouses))
        application.add_handler(CommandHandler("skus", skus_list))
        application.add_handler(CommandHandler("stock", stock_list))
        application.add_handler(CommandHandler("movements", movements_list))
        application.add_handler(CommandHandler("orders", orders_list))

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
