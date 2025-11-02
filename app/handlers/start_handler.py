"""
Обработчики команд start и help.
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.database.db import get_db
from app.services import user_service
from app.logger import get_logger

logger = get_logger("start_handler")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Регистрируем пользователя в БД
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
        "/help - Справка по командам\n"
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
        
        warehouses_count = len(warehouse_service.get_all_warehouses(db))
        skus_count = len(sku_service.get_all_skus(db))
    
    status_text = (
        "✅ Система работает нормально\n\n"
        f"🏢 Складов: {warehouses_count}\n"
        f"📦 Товаров: {skus_count}\n"
        "📊 База данных: подключена\n"
        "🤖 Бот: активен"
    )
    
    await update.message.reply_text(status_text)
