"""
Обработчики для оформления прихода сырья.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import raw_material_service, category_service, stock_service
from app.database.models import CategoryType
from app.logger import get_logger

logger = get_logger("arrival_handlers")

# Состояния для ConversationHandler
ARRIVAL_SELECT_CATEGORY, ARRIVAL_SELECT_MATERIAL, ARRIVAL_ENTER_QUANTITY = range(3)


def get_back_to_main_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
    ]])


# ============================================================================
# ПРИХОД СЫРЬЯ - НАЧАЛО
# ============================================================================

async def arrival_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню прихода сырья."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        # Получаем категории сырья
        categories = category_service.get_categories(db, category_type=CategoryType.raw_material)
        
        if not categories:
            await query.edit_message_text(
                "❌ Нет категорий сырья.\n\n"
                "Администратор должен сначала создать категории в настройках.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с категориями
        keyboard = []
        for category in categories:
            keyboard.append([
                InlineKeyboardButton(
                    f"🌾 {category.name}",
                    callback_data=f"arrival_cat_{category.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "📥 *Приход сырья*\n\n"
            "Выберите категорию сырья:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ARRIVAL_SELECT_CATEGORY
        
    except Exception as e:
        logger.error(f"Ошибка в arrival_menu_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВЫБОР МАТЕРИАЛА
# ============================================================================

async def arrival_select_material_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор материала из категории."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID категории из callback_data
    category_id = int(query.data.split("_")[-1])
    context.user_data["arrival_category_id"] = category_id
    
    db = SessionLocal()
    try:
        # Получаем материалы в категории
        materials = raw_material_service.get_raw_materials(db, category_id=category_id)
        
        if not materials:
            category = category_service.get_category_by_id(db, category_id)
            await query.edit_message_text(
                f"❌ В категории '{category.name}' нет сырья.\n\n"
                f"Администратор должен сначала добавить сырье в настройках.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с материалами
        keyboard = []
        for material in materials:
            keyboard.append([
                InlineKeyboardButton(
                    f"{material.name} (остаток: {material.stock_quantity:.2f} {material.unit.value})",
                    callback_data=f"arrival_mat_{material.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 К категориям", callback_data="arrival_menu"),
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        category = category_service.get_category_by_id(db, category_id)
        
        await query.edit_message_text(
            f"📥 *Приход сырья*\n\n"
            f"Категория: *{category.name}*\n\n"
            f"Выберите сырье:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ARRIVAL_SELECT_MATERIAL
        
    except Exception as e:
        logger.error(f"Ошибка в arrival_select_material_callback: {e}", exc_info=True)
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

async def arrival_enter_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос количества для прихода."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID материала
    material_id = int(query.data.split("_")[-1])
    context.user_data["arrival_material_id"] = material_id
    
    db = SessionLocal()
    try:
        material = raw_material_service.get_raw_material_by_id(db, material_id)
        
        await query.edit_message_text(
            f"📥 *Приход сырья*\n\n"
            f"Категория: *{material.category.name}*\n"
            f"Сырье: *{material.name}*\n"
            f"Текущий остаток: *{material.stock_quantity:.2f} {material.unit.value}*\n\n"
            f"Введите количество прихода ({material.unit.value}):",
            parse_mode="Markdown"
        )
        
        return ARRIVAL_ENTER_QUANTITY
        
    except Exception as e:
        logger.error(f"Ошибка в arrival_enter_quantity_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# СОХРАНЕНИЕ ПРИХОДА
# ============================================================================

async def arrival_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение прихода сырья."""
    try:
        quantity = float(update.message.text.strip().replace(",", "."))
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ Количество должно быть больше 0.\n"
                "Попробуйте снова:"
            )
            return ARRIVAL_ENTER_QUANTITY
        
        material_id = context.user_data["arrival_material_id"]
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            # Получаем данные о материале до прихода
            material = raw_material_service.get_raw_material_by_id(db, material_id)
            old_stock = material.stock_quantity
            
            # Оформляем приход
            movement = stock_service.add_arrival(
                db,
                raw_material_id=material_id,
                quantity=quantity,
                operator_id=user_id
            )
            
            # Получаем обновленные данные
            material = raw_material_service.get_raw_material_by_id(db, material_id)
            
            await update.message.reply_text(
                f"✅ *Приход оформлен!*\n\n"
                f"📦 *{material.category.name} / {material.name}*\n"
                f"➕ Поступило: *{quantity:.2f} {material.unit.value}*\n"
                f"📊 Было на складе: {old_stock:.2f} {material.unit.value}\n"
                f"📊 Стало на складе: *{material.stock_quantity:.2f} {material.unit.value}*\n"
                f"📅 Дата: {movement.created_at.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=get_back_to_main_button(),
                parse_mode="Markdown"
            )
            
            logger.info(
                f"Приход сырья: {material.category.name}/{material.name} "
                f"+{quantity} {material.unit.value} (пользователь: {user_id})"
            )
            
            # Очищаем данные
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении прихода: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при сохранении: {e}",
                reply_markup=get_back_to_main_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        finally:
            db.close()
            
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа.\n"
            "Введите количество (например: 50 или 50.5):"
        )
        return ARRIVAL_ENTER_QUANTITY


# ============================================================================
# ОТМЕНА
# ============================================================================

async def arrival_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции прихода."""
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
