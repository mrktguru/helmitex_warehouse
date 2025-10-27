"""
Обработчики админ-панели для управления справочниками.
Только для администратора (OWNER_TELEGRAM_ID).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import (
    category_service,
    raw_material_service,
    semi_product_service,
    finished_product_service,
    recipe_service
)
from app.database.models import CategoryType, UnitType, RecipeStatus
from app.utils.formatters import (
    format_category_list,
    format_raw_material_list,
    format_semi_product_list,
    format_finished_product_list,
    format_recipe_list,
    format_recipe_details
)
from app.utils.decorators import admin_only
from app.config import OWNER_TELEGRAM_ID
from app.logger import get_logger

logger = get_logger("admin_handlers")

# Состояния для ConversationHandler
(
    ADMIN_CATEGORY_NAME, ADMIN_CATEGORY_TYPE,
    ADMIN_RAW_CATEGORY, ADMIN_RAW_NAME, ADMIN_RAW_UNIT,
    ADMIN_SEMI_CATEGORY, ADMIN_SEMI_NAME, ADMIN_SEMI_UNIT,
    ADMIN_FINISHED_CATEGORY, ADMIN_FINISHED_NAME, ADMIN_FINISHED_PACKAGE_TYPE,
    ADMIN_FINISHED_PACKAGE_WEIGHT,
    ADMIN_RECIPE_NAME, ADMIN_RECIPE_SEMI, ADMIN_RECIPE_YIELD, ADMIN_RECIPE_COMPONENTS
) = range(17)


def get_back_to_settings_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в настройки."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")
    ]])


# ============================================================================
# УПРАВЛЕНИЕ КАТЕГОРИЯМИ
# ============================================================================

async def admin_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления категориями."""
    query = update.callback_query
    
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    db = SessionLocal()
    try:
        categories = category_service.get_categories(db)
        text = format_category_list(categories)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить категорию", callback_data="admin_cat_add")],
            [InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            f"{text}\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_categories_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_category_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления категории."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🌾 Сырье", callback_data="admin_cat_type_raw")],
        [InlineKeyboardButton("⚙️ Полуфабрикаты", callback_data="admin_cat_type_semi")],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data="admin_cat_type_finished")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_categories")]
    ]
    
    await query.edit_message_text(
        "📁 *Добавление категории*\n\n"
        "Выберите тип категории:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ADMIN_CATEGORY_TYPE


async def admin_category_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа категории."""
    query = update.callback_query
    await query.answer()
    
    type_map = {
        "admin_cat_type_raw": CategoryType.raw_material,
        "admin_cat_type_semi": CategoryType.semi_product,
        "admin_cat_type_finished": CategoryType.finished_product
    }
    
    category_type = type_map.get(query.data)
    context.user_data["admin_category_type"] = category_type
    
    type_names = {
        CategoryType.raw_material: "Сырье",
        CategoryType.semi_product: "Полуфабрикаты",
        CategoryType.finished_product: "Готовая продукция"
    }
    
    await query.edit_message_text(
        f"📁 *Добавление категории*\n\n"
        f"Тип: *{type_names[category_type]}*\n\n"
        f"Введите название категории:",
        parse_mode="Markdown"
    )
    
    return ADMIN_CATEGORY_NAME


async def admin_category_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение категории."""
    name = update.message.text.strip()
    category_type = context.user_data["admin_category_type"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        category = category_service.create_category(
            db,
            name=name,
            category_type=category_type,
            created_by=user_id
        )
        
        await update.message.reply_text(
            f"✅ Категория '{name}' создана!\n"
            f"ID: {category.id}",
            reply_markup=get_back_to_settings_button()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании категории: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# УПРАВЛЕНИЕ СЫРЬЕМ
# ============================================================================

async def admin_raw_materials_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления сырьем."""
    query = update.callback_query
    
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    db = SessionLocal()
    try:
        materials = raw_material_service.get_raw_materials(db)
        text = format_raw_material_list(materials)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить сырье", callback_data="admin_raw_add")],
            [InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            f"{text}\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_raw_materials_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_raw_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления сырья."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        categories = category_service.get_categories(db, category_type=CategoryType.raw_material)
        
        if not categories:
            await query.edit_message_text(
                "❌ Нет категорий сырья.\n"
                "Сначала создайте категорию.",
                reply_markup=get_back_to_settings_button()
            )
            return ConversationHandler.END
        
        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(cat.name, callback_data=f"admin_raw_cat_{cat.id}")
            ])
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="admin_raw_materials")
        ])
        
        await query.edit_message_text(
            "🌾 *Добавление сырья*\n\n"
            "Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ADMIN_RAW_CATEGORY
        
    except Exception as e:
        logger.error(f"Ошибка в admin_raw_add_start: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


async def admin_raw_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории для сырья."""
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split("_")[-1])
    context.user_data["admin_raw_category_id"] = category_id
    
    await query.edit_message_text(
        "🌾 *Добавление сырья*\n\n"
        "Введите название сырья:",
        parse_mode="Markdown"
    )
    
    return ADMIN_RAW_NAME


async def admin_raw_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия сырья."""
    name = update.message.text.strip()
    context.user_data["admin_raw_name"] = name
    
    keyboard = [
        [InlineKeyboardButton("кг", callback_data="admin_raw_unit_kg")],
        [InlineKeyboardButton("л", callback_data="admin_raw_unit_liter")],
        [InlineKeyboardButton("г", callback_data="admin_raw_unit_gram")],
        [InlineKeyboardButton("мл", callback_data="admin_raw_unit_ml")],
        [InlineKeyboardButton("шт", callback_data="admin_raw_unit_piece")]
    ]
    
    await update.message.reply_text(
        f"🌾 *Добавление сырья*\n\n"
        f"Название: *{name}*\n\n"
        f"Выберите единицу измерения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ADMIN_RAW_UNIT


async def admin_raw_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение сырья."""
    query = update.callback_query
    await query.answer()
    
    unit_map = {
        "admin_raw_unit_kg": UnitType.kg,
        "admin_raw_unit_liter": UnitType.liter,
        "admin_raw_unit_gram": UnitType.gram,
        "admin_raw_unit_ml": UnitType.ml,
        "admin_raw_unit_piece": UnitType.piece
    }
    
    unit = unit_map.get(query.data)
    category_id = context.user_data["admin_raw_category_id"]
    name = context.user_data["admin_raw_name"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        material = raw_material_service.create_raw_material(
            db,
            category_id=category_id,
            name=name,
            unit=unit,
            created_by=user_id
        )
        
        await query.edit_message_text(
            f"✅ Сырье добавлено!\n\n"
            f"📦 {material.category.name} / {material.name}\n"
            f"Единица: {material.unit.value}\n"
            f"ID: {material.id}",
            reply_markup=get_back_to_settings_button()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании сырья: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()
