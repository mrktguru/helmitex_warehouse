"""
Обработчики для отгрузки готовой продукции.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import finished_product_service, stock_service
from app.logger import get_logger

logger = get_logger("shipment_handlers")

# Состояния для ConversationHandler
SHIPMENT_SELECT_PRODUCT, SHIPMENT_ENTER_QUANTITY, SHIPMENT_ENTER_DESTINATION = range(3)


def get_back_to_main_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
    ]])


# ============================================================================
# ОТГРУЗКА - НАЧАЛО
# ============================================================================

async def shipment_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню отгрузки."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        # Получаем готовую продукцию с остатками
        products = finished_product_service.get_finished_products(db)
        available_products = [p for p in products if p.stock_quantity > 0]
        
        if not available_products:
            await query.edit_message_text(
                "❌ Нет готовой продукции на складе.\n\n"
                "Сначала нужно произвести и расфасовать продукцию.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с продукцией
        keyboard = []
        for product in available_products:
            keyboard.append([
                InlineKeyboardButton(
                    f"📦 {product.name} ({product.package_type} {product.package_weight}кг) "
                    f"- {int(product.stock_quantity)} шт",
                    callback_data=f"ship_prod_{product.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "🚚 *Отгрузка*\n\n"
            "Выберите продукцию для отгрузки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return SHIPMENT_SELECT_PRODUCT
        
    except Exception as e:
        logger.error(f"Ошибка в shipment_menu_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВВОД КОЛИЧЕСТВА
# ============================================================================

async def shipment_enter_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос количества для отгрузки."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID продукции
    product_id = int(query.data.split("_")[-1])
    context.user_data["shipment_product_id"] = product_id
    
    db = SessionLocal()
    try:
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        
        await query.edit_message_text(
            f"🚚 *Отгрузка*\n\n"
            f"Продукция: *{product.category.name} / {product.name}*\n"
            f"Тара: {product.package_type} {product.package_weight}кг\n"
            f"Доступно: *{int(product.stock_quantity)} шт*\n\n"
            f"Введите количество для отгрузки (шт):",
            parse_mode="Markdown"
        )
        
        return SHIPMENT_ENTER_QUANTITY
        
    except Exception as e:
        logger.error(f"Ошибка в shipment_enter_quantity_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВВОД НАПРАВЛЕНИЯ ОТГРУЗКИ
# ============================================================================

async def shipment_enter_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос направления отгрузки."""
    try:
        quantity = int(update.message.text.strip())
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ Количество должно быть больше 0.\n"
                "Попробуйте снова:"
            )
            return SHIPMENT_ENTER_QUANTITY
        
        context.user_data["shipment_quantity"] = quantity
        
        # Проверяем наличие
        db = SessionLocal()
        try:
            product_id = context.user_data["shipment_product_id"]
            product = finished_product_service.get_finished_product_by_id(db, product_id)
            
            if quantity > product.stock_quantity:
                await update.message.reply_text(
                    f"❌ Недостаточно продукции на складе.\n"
                    f"Доступно: {int(product.stock_quantity)} шт\n"
                    f"Запрошено: {quantity} шт\n\n"
                    f"Введите меньшее количество:",
                    reply_markup=get_back_to_main_button()
                )
                return SHIPMENT_ENTER_QUANTITY
            
            # Предлагаем популярные направления
            keyboard = [
                [InlineKeyboardButton("🛒 Wildberries", callback_data="ship_dest_Wildberries")],
                [InlineKeyboardButton("🛒 Ozon", callback_data="ship_dest_Ozon")],
                [InlineKeyboardButton("🛒 Яндекс.Маркет", callback_data="ship_dest_YandexMarket")],
                [InlineKeyboardButton("✏️ Другое (ввести вручную)", callback_data="ship_dest_custom")],
                [InlineKeyboardButton("➡️ Без указания", callback_data="ship_dest_none")],
                [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
            ]
            
            await update.message.reply_text(
                f"🚚 *Отгрузка*\n\n"
                f"Продукция: *{product.name}*\n"
                f"Количество: *{quantity} шт*\n\n"
                f"Выберите направление отгрузки или введите свое:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
            return SHIPMENT_ENTER_DESTINATION
            
        except Exception as e:
            logger.error(f"Ошибка при проверке количества: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка: {e}",
                reply_markup=get_back_to_main_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        finally:
            db.close()
            
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа.\n"
            "Введите целое количество (например: 50):"
        )
        return SHIPMENT_ENTER_QUANTITY


# ============================================================================
# СОХРАНЕНИЕ ОТГРУЗКИ
# ============================================================================

async def shipment_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отгрузки (выбор из кнопок)."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем направление
    if query.data == "ship_dest_custom":
        await query.edit_message_text(
            "✏️ Введите направление отгрузки (например: Wildberries, Ozon, название магазина):"
        )
        return SHIPMENT_ENTER_DESTINATION
    
    if query.data == "ship_dest_none":
        destination = None
    else:
        destination = query.data.replace("ship_dest_", "")
    
    await shipment_save_final(update, context, destination)
    return ConversationHandler.END


async def shipment_save_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отгрузки (ввод вручную)."""
    destination = update.message.text.strip()
    await shipment_save_final(update, context, destination)
    return ConversationHandler.END


async def shipment_save_final(update: Update, context: ContextTypes.DEFAULT_TYPE, destination: str):
    """Финальное сохранение отгрузки."""
    product_id = context.user_data["shipment_product_id"]
    quantity = context.user_data["shipment_quantity"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        # Получаем данные до отгрузки
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        old_stock = product.stock_quantity
        
        # Выполняем отгрузку
        shipment = stock_service.create_shipment(
            db,
            finished_product_id=product_id,
            quantity=quantity,
            operator_id=user_id,
            destination=destination
        )
        
        # Получаем обновленные данные
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        
        destination_text = f"→ *{destination}*" if destination else ""
        
        text = (
            f"✅ *Отгрузка оформлена!*\n\n"
            f"📦 *{product.category.name} / {product.name}*\n"
            f"   {product.package_type} {product.package_weight}кг\n\n"
            f"🚚 Отгружено: *{quantity} шт* {destination_text}\n"
            f"📊 Было на складе: {int(old_stock)} шт\n"
            f"📊 Осталось на складе: *{int(product.stock_quantity)} шт*\n\n"
            f"📅 Дата: {shipment.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
        
        logger.info(
            f"Отгрузка: {product.name} {quantity} шт → {destination or 'не указано'} "
            f"(пользователь: {user_id})"
        )# Файл 17: `app/handlers/shipment_handlers.py` (НОВЫЙ - ОТГРУЗКА)

```python
"""
Обработчики для отгрузки готовой продукции.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import finished_product_service, stock_service
from app.logger import get_logger

logger = get_logger("shipment_handlers")

# Состояния для ConversationHandler
SHIPMENT_SELECT_PRODUCT, SHIPMENT_ENTER_QUANTITY, SHIPMENT_ENTER_DESTINATION = range(3)


def get_back_to_main_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
    ]])


# ============================================================================
# ОТГРУЗКА - НАЧАЛО
# ============================================================================

async def shipment_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню отгрузки."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        # Получаем готовую продукцию с остатками
        products = finished_product_service.get_finished_products(db)
        available_products = [p for p in products if p.stock_quantity > 0]
        
        if not available_products:
            await query.edit_message_text(
                "❌ Нет готовой продукции на складе.\n\n"
                "Сначала нужно произвести и расфасовать продукцию.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с продукцией
        keyboard = []
        for product in available_products:
            keyboard.append([
                InlineKeyboardButton(
                    f"📦 {product.name} ({product.package_type} {product.package_weight}кг) "
                    f"- {int(product.stock_quantity)} шт",
                    callback_data=f"ship_prod_{product.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "🚚 *Отгрузка*\n\n"
            "Выберите продукцию для отгрузки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return SHIPMENT_SELECT_PRODUCT
        
    except Exception as e:
        logger.error(f"Ошибка в shipment_menu_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВВОД КОЛИЧЕСТВА
# ============================================================================

async def shipment_enter_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос количества для отгрузки."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID продукции
    product_id = int(query.data.split("_")[-1])
    context.user_data["shipment_product_id"] = product_id
    
    db = SessionLocal()
    try:
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        
        await query.edit_message_text(
            f"🚚 *Отгрузка*\n\n"
            f"Продукция: *{product.category.name} / {product.name}*\n"
            f"Тара: {product.package_type} {product.package_weight}кг\n"
            f"Доступно: *{int(product.stock_quantity)} шт*\n\n"
            f"Введите количество для отгрузки (шт):",
            parse_mode="Markdown"
        )
        
        return SHIPMENT_ENTER_QUANTITY
        
    except Exception as e:
        logger.error(f"Ошибка в shipment_enter_quantity_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВВОД НАПРАВЛЕНИЯ ОТГРУЗКИ
# ============================================================================

async def shipment_enter_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос направления отгрузки."""
    try:
        quantity = int(update.message.text.strip())
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ Количество должно быть больше 0.\n"
                "Попробуйте снова:"
            )
            return SHIPMENT_ENTER_QUANTITY
        
        context.user_data["shipment_quantity"] = quantity
        
        # Предлагаем популярные направления
        keyboard = [
            [InlineKeyboardButton("🛒 Wildberries", callback_data="ship_dest_Wildberries")],
            [InlineKeyboardButton("🛒 Ozon", callback_data="ship_dest_Ozon")],
            [InlineKeyboardButton("🛒 Яндекс.Маркет", callback_data="ship_dest_YandexMarket")],
            [InlineKeyboardButton("📝 Другое (ввести вручную)", callback_data="ship_dest_custom")],
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="ship_dest_skip")],
            [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            f"🚚 *Отгрузка*\n\n"
            f"Количество: *{quantity} шт*\n\n"
            f"Куда отгружаем?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return SHIPMENT_ENTER_DESTINATION
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа.\n"
            "Введите целое количество (например: 50):"
        )
        return SHIPMENT_ENTER_QUANTITY


# ============================================================================
# СОХРАНЕНИЕ ОТГРУЗКИ
# ============================================================================

async def shipment_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отгрузки (выбор из кнопок)."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем направление
    if query.data == "ship_dest_skip":
        destination = None
    elif query.data == "ship_dest_custom":
        await query.edit_message_text(
            "📝 Введите название маркетплейса или покупателя:"
        )
        return SHIPMENT_ENTER_DESTINATION
    else:
        destination = query.data.split("_")[-1]
    
    await shipment_complete(update, context, destination)
    return ConversationHandler.END


async def shipment_save_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отгрузки (ввод текстом)."""
    destination = update.message.text.strip()
    await shipment_complete(update, context, destination)
    return ConversationHandler.END


async def shipment_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, destination: str = None):
    """Завершение отгрузки."""
    product_id = context.user_data["shipment_product_id"]
    quantity = context.user_data["shipment_quantity"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        # Получаем данные до отгрузки
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        old_stock = product.stock_quantity
        
        # Проверяем достаточно ли продукции
        if quantity > old_stock:
            error_text = (
                f"❌ Недостаточно продукции на складе.\n"
                f"Требуется: {quantity} шт\n"
                f"Доступно: {int(old_stock)} шт"
            )
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    error_text,
                    reply_markup=get_back_to_main_button()
                )
            else:
                await update.message.reply_text(
                    error_text,
                    reply_markup=get_back_to_main_button()
                )
            
            context.user_data.clear()
            return
        
        # Выполняем отгрузку
        shipment = stock_service.create_shipment(
            db,
            finished_product_id=product_id,
            quantity=quantity,
            operator_id=user_id,
            destination=destination
        )
        
        # Получаем обновленные данные
        product = finished_product_service.get_finished_product_by_id(db, product_id)
        
        dest_text = f"→ *{destination}*" if destination else ""
        
        result_text = (
            f"✅ *Отгрузка оформлена!*\n\n"
            f"📦 *{product.category.name} / {product.name}*\n"
            f"   {product.package_type} {product.package_weight}кг\n\n"
            f"🚚 Отгружено: *{quantity} шт* {dest_text}\n"
            f"📊 Было на складе: {int(old_stock)} шт\n"
            f"📊 Осталось на складе: *{int(product.stock_quantity)} шт*\n\n"
            f"📅 Дата: {shipment.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                result_text,
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                result_text,
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
        
        logger.info(
            f"Отгрузка: {product.name} {quantity} шт → {destination or 'не указано'} "
            f"(пользователь: {user_id})"
        )
        
        # Очищаем данные
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при отгрузке: {e}", exc_info=True)
        error_text = f"❌ Ошибка при отгрузке: {e}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                error_text,
                reply_markup=get_back_to_main_button()
            )
        else:
            await update.message.reply_text(
                error_text,
                reply_markup=get_back_to_main_button()
            )
        
        context.user_data.clear()
    finally:
        db.close()


# ============================================================================
# ОТМЕНА
# ============================================================================

async def shipment_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции отгрузки."""
    context.user_data.clear()
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "❌ Операция отменена",
            reply_markup=get_back_to_main_button()
        )
    else:
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=get_back_to_main_button()
        )
    
    return ConversationHandler.END
