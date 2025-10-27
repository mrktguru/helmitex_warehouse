"""
Обработчики для просмотра остатков на складе.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import (
    raw_material_service,
    semi_product_service,
    finished_product_service,
    stock_service
)
from app.utils.formatters import (
    format_raw_material_list,
    format_semi_product_list,
    format_finished_product_list,
    format_movement_history
)
from app.database.models import MovementType
from app.logger import get_logger

logger = get_logger("stock_handlers")


def get_back_to_stock_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню остатков."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 К остаткам", callback_data="stock_menu")
    ]])


def get_back_to_history_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню истории."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 К истории", callback_data="history_menu")
    ]])


# ============================================================================
# ОСТАТКИ
# ============================================================================

async def stock_raw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Остатки сырья."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        materials = raw_material_service.get_raw_materials(db)
        text = format_raw_material_list(materials)
        
        # Проверяем низкие остатки
        low_stock = raw_material_service.get_low_stock_materials(db)
        if low_stock:
            text += "\n\n⚠️ *Низкие остатки:*\n"
            for material in low_stock:
                text += (
                    f"• {material.category.name} / {material.name}: "
                    f"{material.stock_quantity:.2f} {material.unit.value} "
                    f"(мин: {material.min_stock:.2f})\n"
                )
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_stock_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении остатков сырья: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_stock_button()
        )
    finally:
        db.close()


async def stock_semi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Остатки полуфабрикатов."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        products = semi_product_service.get_semi_products(db)
        text = format_semi_product_list(products)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_stock_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении остатков полуфабрикатов: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_stock_button()
        )
    finally:
        db.close()


async def stock_finished_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Остатки готовой продукции."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        products = finished_product_service.get_finished_products(db)
        text = format_finished_product_list(products)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_stock_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении остатков готовой продукции: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_stock_button()
        )
    finally:
        db.close()


# ============================================================================
# ИСТОРИЯ ОПЕРАЦИЙ
# ============================================================================

async def history_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История всех операций."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        movements = stock_service.get_movements(db, limit=20)
        text = format_movement_history(movements)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_history_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_history_button()
        )
    finally:
        db.close()


async def history_arrival_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История прихода сырья."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        movements = stock_service.get_movements(db, movement_type=MovementType.arrival, limit=20)
        text = format_movement_history(movements)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_history_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении истории прихода: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_history_button()
        )
    finally:
        db.close()


async def history_production_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История производства."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        movements = stock_service.get_movements(
            db, 
            movement_type=MovementType.production_output, 
            limit=20
        )
        text = format_movement_history(movements)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_history_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении истории производства: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_history_button()
        )
    finally:
        db.close()


async def history_packing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История фасовки."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        movements = stock_service.get_movements(
            db, 
            movement_type=MovementType.packing_output, 
            limit=20
        )
        text = format_movement_history(movements)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_history_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении истории фасовки: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_history_button()
        )
    finally:
        db.close()


async def history_shipment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История отгрузок."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        movements = stock_service.get_movements(
            db, 
            movement_type=MovementType.shipment, 
            limit=20
        )
        text = format_movement_history(movements)
        
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_history_button(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при получении истории отгрузок: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при получении данных: {e}",
            reply_markup=get_back_to_history_button()
        )
    finally:
        db.close()
