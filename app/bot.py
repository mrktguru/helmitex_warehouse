"""
Главный модуль Telegram бота.
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.database.db import init_db, get_db
from app.config import TELEGRAM_BOT_TOKEN
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
    with get_db() as db:
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
        "📚 Справка по командам Helmitex Warehouse:\n\n"
        "🏢 Склады:\n"
        "/warehouses - Список складов\n"
        "/add_warehouse - Добавить склад\n\n"
        "📦 Товары:\n"
        "/skus - Список товаров\n"
        "/add_sku - Добавить товар\n\n"
        "📊 Остатки:\n"
        "/stock - Остатки на складах\n"
        "/low_stock - Товары с низким остатком\n\n"
        "🔄 Движения:\n"
        "/movements - История движений\n"
        "/add_in - Оприходовать товар\n"
        "/add_out - Списать товар\n"
        "/transfer - Переместить товар\n\n"
        "📋 Заказы:\n"
        "/orders - Список заказов\n"
        "/new_order - Создать заказ\n\n"
        "ℹ️ Прочее:\n"
        "/help - Эта справка\n"
        "/status - Статус системы\n"
    )
    await update.message.reply_text(help_text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    with get_db() as db:
        from app.services import warehouse_service, sku_service
        
        try:
            warehouses_count = len(warehouse_service.get_all_warehouses(db))
            skus_count = len(sku_service.get_all_skus(db))
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
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
    with get_db() as db:
        from app.services import warehouse_service
        
        try:
            whs = warehouse_service.get_all_warehouses(db)
        except Exception as e:
            logger.error(f"Error getting warehouses: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка складов")
            return
    
    if not whs:
        await update.message.reply_text("📦 Складов пока нет\n\nИспользуйте /add_warehouse для добавления")
        return
    
    text = "🏢 Список складов:\n\n"
    for wh in whs:
        text += f"• {wh.name}"
        if wh.location:
            text += f" ({wh.location})"
        text += f" [ID: {wh.id}]\n"
    
    await update.message.reply_text(text)


async def skus_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список товаров"""
    with get_db() as db:
        from app.services import sku_service
        
        try:
            skus = sku_service.get_all_skus(db)
        except Exception as e:
            logger.error(f"Error getting SKUs: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка товаров")
            return
    
    if not skus:
        await update.message.reply_text("📦 Товаров пока нет\n\nИспользуйте /add_sku для добавления")
        return
    
    text = "📦 Список товаров:\n\n"
    for sku in skus[:20]:  # Показываем первые 20
        text += f"• {sku.code} - {sku.name}\n"
        text += f"  Тип: {sku.type.value}, Ед.изм: {sku.unit}\n"
    
    if len(skus) > 20:
        text += f"\n... и еще {len(skus) - 20} товаров"
    
    await update.message.reply_text(text)


async def stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Остатки на складах"""
    with get_db() as db:
        from app.services import stock_service, warehouse_service
        
        try:
            warehouses_list = warehouse_service.get_all_warehouses(db)
            
            if not warehouses_list:
                await update.message.reply_text("📦 Нет складов для отображения остатков")
                return
            
            text = "📊 Остатки на складах:\n\n"
            
            for wh in warehouses_list:
                stocks = stock_service.get_warehouse_stock(db, wh.id)
                text += f"🏢 {wh.name}:\n"
                
                if not stocks:
                    text += "  Нет остатков\n\n"
                    continue
                
                for stock in stocks[:10]:  # Первые 10 позиций
                    text += f"  • {stock.sku.code}: {stock.quantity} {stock.sku.unit}\n"
                
                if len(stocks) > 10:
                    text += f"  ... и еще {len(stocks) - 10} позиций\n"
                text += "\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Error getting stock: {e}")
            await update.message.reply_text("❌ Ошибка при получении остатков")


async def movements_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История движений"""
    with get_db() as db:
        from app.services import movement_service
        
        try:
            user = update.effective_user
            db_user = user_service.get_or_create_user(
                db=db,
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name
            )
            
            movements = movement_service.get_user_movements(db, db_user.id, limit=10)
            
            if not movements:
                await update.message.reply_text("🔄 История движений пуста")
                return
            
            text = "🔄 Последние движения:\n\n"
            
            for mov in movements:
                text += f"• {mov.type.value.upper()}: {mov.sku.code}\n"
                text += f"  Количество: {mov.quantity} {mov.sku.unit}\n"
                text += f"  Склад: {mov.warehouse.name}\n"
                if mov.notes:
                    text += f"  Примечание: {mov.notes}\n"
                text += f"  Дата: {mov.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Error getting movements: {e}")
            await update.message.reply_text("❌ Ошибка при получении истории движений")


async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список заказов"""
    with get_db() as db:
        from app.services import order_service
        
        try:
            orders = order_service.get_orders(db, limit=10)
            
            if not orders:
                await update.message.reply_text("📋 Заказов пока нет")
                return
            
            text = "📋 Последние заказы:\n\n"
            
            for order in orders:
                text += f"• {order.order_number}\n"
                text += f"  Тип: {order.type.value}\n"
                text += f"  Статус: {order.status.value}\n"
                text += f"  Склад: {order.warehouse.name}\n"
                text += f"  Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await update.message.reply_text(text)
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка заказов")


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
