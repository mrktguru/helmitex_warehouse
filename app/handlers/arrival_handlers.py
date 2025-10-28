"""
Обработчики для прихода сырья.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.database.db import get_db
from app.database.models import CategoryType, UnitType, SKUType
from app.services import user_service, sku_service, movement_service, warehouse_service
from app.database.models import MovementType

logger = logging.getLogger(__name__)

# Состояния разговора
SELECT_CATEGORY, SELECT_SKU, ENTER_QUANTITY, CONFIRM = range(4)


def get_category_keyboard():
    """Клавиатура выбора категории"""
    keyboard = []
    for category in CategoryType:
        keyboard.append([InlineKeyboardButton(
            category.value,
            callback_data=f"cat_{category.name}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="arrival")])
    return InlineKeyboardMarkup(keyboard)


def get_sku_keyboard(category: CategoryType):
    """Клавиатура выбора товара по категории"""
    with get_db() as db:
        skus = sku_service.get_skus_by_category(db, category)
    
    keyboard = []
    if skus:
        for sku in skus:
            keyboard.append([InlineKeyboardButton(
                f"{sku.name} ({sku.unit.value})",
                callback_data=f"sku_{sku.id}"
            )])
    else:
        keyboard.append([InlineKeyboardButton(
            "➕ Добавить новый товар",
            callback_data="add_new_sku"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="arrival_add")])
    return InlineKeyboardMarkup(keyboard)


async def arrival_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления прихода"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📥 *Приход сырья*\n\n"
        "Шаг 1/3: Выберите категорию сырья:",
        reply_markup=get_category_keyboard(),
        parse_mode='Markdown'
    )
    
    return SELECT_CATEGORY


async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории"""
    query = update.callback_query
    await query.answer()
    
    category_name = query.data.replace("cat_", "")
    category = CategoryType[category_name]
    
    # Сохраняем в контекст
    context.user_data['arrival_category'] = category
    
    await query.edit_message_text(
        f"📥 *Приход сырья*\n\n"
        f"Категория: *{category.value}*\n\n"
        f"Шаг 2/3: Выберите товар:",
        reply_markup=get_sku_keyboard(category),
        parse_mode='Markdown'
    )
    
    return SELECT_SKU


async def select_sku(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор товара"""
    query = update.callback_query
    await query.answer()
    
    sku_id = int(query.data.replace("sku_", ""))
    
    with get_db() as db:
        sku = sku_service.get_sku(db, sku_id)
    
    if not sku:
        await query.edit_message_text(
            "❌ Товар не найден",
            reply_markup=get_category_keyboard()
        )
        return SELECT_CATEGORY
    
    # Сохраняем в контекст
    context.user_data['arrival_sku'] = sku
    
    await query.edit_message_text(
        f"📥 *Приход сырья*\n\n"
        f"Категория: *{sku.category.value}*\n"
        f"Товар: *{sku.name}*\n"
        f"Единица: *{sku.unit.value}*\n\n"
        f"Шаг 3/3: Введите количество ({sku.unit.value}):",
        parse_mode='Markdown'
    )
    
    return ENTER_QUANTITY


async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод количества"""
    try:
        quantity = float(update.message.text.replace(',', '.'))
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ Количество должно быть больше нуля.\n"
                "Попробуйте еще раз:"
            )
            return ENTER_QUANTITY
        
        sku = context.user_data['arrival_sku']
        
        # Сохраняем количество
        context.user_data['arrival_quantity'] = quantity
        
        # Подтверждение
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_arrival"),
                InlineKeyboardButton("❌ Отменить", callback_data="cancel_arrival")
            ]
        ]
        
        await update.message.reply_text(
            f"📥 *Подтверждение прихода*\n\n"
            f"Категория: *{sku.category.value}*\n"
            f"Товар: *{sku.name}*\n"
            f"Количество: *{quantity} {sku.unit.value}*\n\n"
            f"Подтвердите операцию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return CONFIRM
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа.\n"
            "Введите количество (например: 10 или 10.5):"
        )
        return ENTER_QUANTITY


async def confirm_arrival(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и сохранение прихода"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_arrival":
        await query.edit_message_text(
            "❌ Операция отменена",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Получаем данные
    sku = context.user_data['arrival_sku']
    quantity = context.user_data['arrival_quantity']
    user = update.effective_user
    
    try:
        with get_db() as db:
            # Получаем пользователя
            db_user = user_service.get_or_create_user(
                db=db,
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name
            )
            
            # Получаем склад по умолчанию
            warehouse = warehouse_service.get_default_warehouse(db)
            if not warehouse:
                # Создаем склад по умолчанию если его нет
                warehouse = warehouse_service.create_warehouse(
                    db=db,
                    name="Основной склад",
                    is_default=True
                )
            
            # Создаем движение (приход)
            movement = movement_service.create_movement(
                db=db,
                warehouse_id=warehouse.id,
                sku_id=sku.id,
                movement_type=MovementType.in_,
                quantity=quantity,
                user_id=db_user.id,
                notes=f"Приход сырья через Telegram бот"
            )
            
            # Получаем новый остаток
            from app.services import stock_service
            stock = stock_service.get_stock(db, warehouse.id, sku.id)
        
        await query.edit_message_text(
            f"✅ *Приход оформлен успешно!*\n\n"
            f"Категория: *{sku.category.value}*\n"
            f"Товар: *{sku.name}*\n"
            f"Количество: *{quantity} {sku.unit.value}*\n"
            f"Остаток на складе: *{stock.quantity} {sku.unit.value}*\n\n"
            f"Операция #{movement.id}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error creating arrival: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при оформлении прихода:\n{str(e)}",
            parse_mode='Markdown'
        )
    
    context.user_data.clear()
    return ConversationHandler.END
