"""
Обработчики для фасовки полуфабрикатов в готовую продукцию.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import semi_product_service, finished_product_service, stock_service
from app.logger import get_logger

logger = get_logger("packing_handlers")

# Состояния для ConversationHandler
PACKING_SELECT_SEMI, PACKING_SELECT_FINISHED, PACKING_ENTER_QUANTITY = range(3)


def get_back_to_main_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
    ]])


# ============================================================================
# ФАСОВКА - НАЧАЛО
# ============================================================================

async def packing_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню фасовки."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        # Получаем полуфабрикаты с остатками
        semi_products = semi_product_service.get_semi_products(db)
        available_products = [p for p in semi_products if p.stock_quantity > 0]
        
        if not available_products:
            await query.edit_message_text(
                "❌ Нет полуфабрикатов на складе.\n\n"
                "Сначала нужно произвести полуфабрикаты.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с полуфабрикатами
        keyboard = []
        for product in available_products:
            keyboard.append([
                InlineKeyboardButton(
                    f"⚙️ {product.category.name} / {product.name} "
                    f"({product.stock_quantity:.2f} {product.unit.value})",
                    callback_data=f"pack_semi_{product.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "📦 *Фасовка*\n\n"
            "Выберите полуфабрикат для фасовки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return PACKING_SELECT_SEMI
        
    except Exception as e:
        logger.error(f"Ошибка в packing_menu_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВЫБОР ГОТОВОЙ ПРОДУКЦИИ
# ============================================================================

async def packing_select_finished_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор готовой продукции для фасовки."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID полуфабриката
    semi_product_id = int(query.data.split("_")[-1])
    context.user_data["packing_semi_id"] = semi_product_id
    
    db = SessionLocal()
    try:
        semi_product = semi_product_service.get_semi_product_by_id(db, semi_product_id)
        
        # Получаем готовую продукцию
        finished_products = finished_product_service.get_finished_products(db)
        
        if not finished_products:
            await query.edit_message_text(
                "❌ Нет готовой продукции в справочнике.\n\n"
                "Администратор должен сначала добавить готовую продукцию в настройках.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с готовой продукцией
        keyboard = []
        for product in finished_products:
            keyboard.append([
                InlineKeyboardButton(
                    f"📦 {product.name} ({product.package_type} {product.package_weight}кг)",
                    callback_data=f"pack_fin_{product.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 К полуфабрикатам", callback_data="packing_menu"),
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            f"📦 *Фасовка*\n\n"
            f"Полуфабрикат: *{semi_product.category.name} / {semi_product.name}*\n"
            f"Доступно: *{semi_product.stock_quantity:.2f} {semi_product.unit.value}*\n\n"
            f"Выберите готовую продукцию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return PACKING_SELECT_FINISHED
        
    except Exception as e:
        logger.error(f"Ошибка в packing_select_finished_callback: {e}", exc_info=True)
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

async def packing_enter_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос количества упаковок."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID готовой продукции
    finished_product_id = int(query.data.split("_")[-1])
    context.user_data["packing_finished_id"] = finished_product_id
    
    db = SessionLocal()
    try:
        semi_product = semi_product_service.get_semi_product_by_id(
            db, context.user_data["packing_semi_id"]
        )
        finished_product = finished_product_service.get_finished_product_by_id(
            db, finished_product_id
        )
        
        # Рассчитываем максимальное количество упаковок
        max_packages = int(semi_product.stock_quantity / finished_product.package_weight)
        
        await query.edit_message_text(
            f"📦 *Фасовка*\n\n"
            f"Полуфабрикат: *{semi_product.category.name} / {semi_product.name}*\n"
            f"Доступно: *{semi_product.stock_quantity:.2f} {semi_product.unit.value}*\n\n"
            f"Готовая продукция: *{finished_product.name}*\n"
            f"Тара: {finished_product.package_type} {finished_product.package_weight}кг\n\n"
            f"Максимум упаковок: *{max_packages} шт*\n\n"
            f"Введите количество упаковок:",
            parse_mode="Markdown"
        )
        
        return PACKING_ENTER_QUANTITY
        
    except Exception as e:
        logger.error(f"Ошибка в packing_enter_quantity_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# СОХРАНЕНИЕ ФАСОВКИ
# ============================================================================

async def packing_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение фасовки."""
    try:
        quantity = int(update.message.text.strip())
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ Количество должно быть больше 0.\n"
                "Попробуйте снова:"
            )
            return PACKING_ENTER_QUANTITY
        
        semi_product_id = context.user_data["packing_semi_id"]
        finished_product_id = context.user_data["packing_finished_id"]
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            # Получаем данные до фасовки
            semi_product = semi_product_service.get_semi_product_by_id(db, semi_product_id)
            finished_product = finished_product_service.get_finished_product_by_id(db, finished_product_id)
            
            old_semi_stock = semi_product.stock_quantity
            old_finished_stock = finished_product.stock_quantity
            weight_needed = finished_product.package_weight * quantity
            
            # Проверяем достаточно ли полуфабриката
            if weight_needed > old_semi_stock:
                await update.message.reply_text(
                    f"❌ Недостаточно полуфабриката.\n"
                    f"Требуется: {weight_needed:.2f} {semi_product.unit.value}\n"
                    f"Доступно: {old_semi_stock:.2f} {semi_product.unit.value}\n\n"
                    f"Введите меньшее количество:",
                    reply_markup=get_back_to_main_button()
                )
                return PACKING_ENTER_QUANTITY
            
            # Выполняем фасовку
            packing = stock_service.create_packing(
                db,
                semi_product_id=semi_product_id,
                finished_product_id=finished_product_id,
                quantity=quantity,
                operator_id=user_id
            )
            
            # Получаем обновленные данные
            semi_product = semi_product_service.get_semi_product_by_id(db, semi_product_id)
            finished_product = finished_product_service.get_finished_product_by_id(db, finished_product_id)
            
            await update.message.reply_text(
                f"✅ *Фасовка завершена!*\n\n"
                f"*Списано полуфабриката:*\n"
                f"⚙️ {semi_product.category.name} / {semi_product.name}\n"
                f"   -{weight_needed:.2f} {semi_product.unit.value}\n"
                f"   Было: {old_semi_stock:.2f}, стало: {semi_product.stock_quantity:.2f}\n\n"
                f"*Получено готовой продукции:*\n"
                f"📦 {finished_product.name}\n"
                f"   +{quantity} шт\n"
                f"   Было: {int(old_finished_stock)}, стало: {int(finished_product.stock_quantity)}\n\n"
                f"📅 Дата: {packing.created_at.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
            
            logger.info(
                f"Фасовка: {finished_product.name} {quantity} шт "
                f"({weight_needed} кг полуфабриката) (пользователь: {user_id})"
            )
            
            # Очищаем данные
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Ошибка при фасовке: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при фасовке: {e}",
                reply_markup=get_back_to_main_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        finally:
            db.close()
            
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа.\n"
            "Введите целое количество упаковок (например: 50):"
        )
        return PACKING_ENTER_QUANTITY


# ============================================================================
# ОТМЕНА
# ============================================================================

async def packing_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции фасовки."""
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
