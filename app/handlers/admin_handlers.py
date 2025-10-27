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

# ============================================================================
# УПРАВЛЕНИЕ ПОЛУФАБРИКАТАМИ
# ============================================================================

async def admin_semi_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления полуфабрикатами."""
    query = update.callback_query
    
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    db = SessionLocal()
    try:
        products = semi_product_service.get_semi_products(db)
        text = format_semi_product_list(products)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить полуфабрикат", callback_data="admin_semi_add")],
            [InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            f"{text}\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_semi_products_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_semi_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления полуфабриката."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        categories = category_service.get_categories(db, category_type=CategoryType.semi_product)
        
        if not categories:
            await query.edit_message_text(
                "❌ Нет категорий полуфабрикатов.\n"
                "Сначала создайте категорию.",
                reply_markup=get_back_to_settings_button()
            )
            return ConversationHandler.END
        
        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(cat.name, callback_data=f"admin_semi_cat_{cat.id}")
            ])
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="admin_semi_products")
        ])
        
        await query.edit_message_text(
            "⚙️ *Добавление полуфабриката*\n\n"
            "Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ADMIN_SEMI_CATEGORY
        
    except Exception as e:
        logger.error(f"Ошибка в admin_semi_add_start: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


async def admin_semi_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории для полуфабриката."""
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split("_")[-1])
    context.user_data["admin_semi_category_id"] = category_id
    
    await query.edit_message_text(
        "⚙️ *Добавление полуфабриката*\n\n"
        "Введите название полуфабриката:",
        parse_mode="Markdown"
    )
    
    return ADMIN_SEMI_NAME


async def admin_semi_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия полуфабриката."""
    name = update.message.text.strip()
    context.user_data["admin_semi_name"] = name
    
    keyboard = [
        [InlineKeyboardButton("кг", callback_data="admin_semi_unit_kg")],
        [InlineKeyboardButton("л", callback_data="admin_semi_unit_liter")]
    ]
    
    await update.message.reply_text(
        f"⚙️ *Добавление полуфабриката*\n\n"
        f"Название: *{name}*\n\n"
        f"Выберите единицу измерения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ADMIN_SEMI_UNIT


async def admin_semi_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение полуфабриката."""
    query = update.callback_query
    await query.answer()
    
    unit_map = {
        "admin_semi_unit_kg": UnitType.kg,
        "admin_semi_unit_liter": UnitType.liter
    }
    
    unit = unit_map.get(query.data)
    category_id = context.user_data["admin_semi_category_id"]
    name = context.user_data["admin_semi_name"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        product = semi_product_service.create_semi_product(
            db,
            category_id=category_id,
            name=name,
            unit=unit,
            created_by=user_id
        )
        
        await query.edit_message_text(
            f"✅ Полуфабрикат добавлен!\n\n"
            f"⚙️ {product.category.name} / {product.name}\n"
            f"Единица: {product.unit.value}\n"
            f"ID: {product.id}",
            reply_markup=get_back_to_settings_button()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании полуфабриката: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# УПРАВЛЕНИЕ ГОТОВОЙ ПРОДУКЦИЕЙ
# ============================================================================

async def admin_finished_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления готовой продукцией."""
    query = update.callback_query
    
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    db = SessionLocal()
    try:
        products = finished_product_service.get_finished_products(db)
        text = format_finished_product_list(products)
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить продукцию", callback_data="admin_finished_add")],
            [InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            f"{text}\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_finished_products_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_finished_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления готовой продукции."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        categories = category_service.get_categories(db, category_type=CategoryType.finished_product)
        
        if not categories:
            await query.edit_message_text(
                "❌ Нет категорий готовой продукции.\n"
                "Сначала создайте категорию.",
                reply_markup=get_back_to_settings_button()
            )
            return ConversationHandler.END
        
        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(cat.name, callback_data=f"admin_fin_cat_{cat.id}")
            ])
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="admin_finished_products")
        ])
        
        await query.edit_message_text(
            "📦 *Добавление готовой продукции*\n\n"
            "Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ADMIN_FINISHED_CATEGORY
        
    except Exception as e:
        logger.error(f"Ошибка в admin_finished_add_start: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


async def admin_finished_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории для готовой продукции."""
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split("_")[-1])
    context.user_data["admin_finished_category_id"] = category_id
    
    await query.edit_message_text(
        "📦 *Добавление готовой продукции*\n\n"
        "Введите название продукции:",
        parse_mode="Markdown"
    )
    
    return ADMIN_FINISHED_NAME


async def admin_finished_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия готовой продукции."""
    name = update.message.text.strip()
    context.user_data["admin_finished_name"] = name
    
    keyboard = [
        [InlineKeyboardButton("Пакет", callback_data="admin_fin_pkg_paket")],
        [InlineKeyboardButton("Банка", callback_data="admin_fin_pkg_banka")],
        [InlineKeyboardButton("Коробка", callback_data="admin_fin_pkg_korobka")],
        [InlineKeyboardButton("Другое", callback_data="admin_fin_pkg_custom")]
    ]
    
    await update.message.reply_text(
        f"📦 *Добавление готовой продукции*\n\n"
        f"Название: *{name}*\n\n"
        f"Выберите тип тары:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ADMIN_FINISHED_PACKAGE_TYPE


async def admin_finished_package_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа тары."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_fin_pkg_custom":
        await query.edit_message_text(
            "📦 *Добавление готовой продукции*\n\n"
            "Введите тип тары (например: Ведро, Мешок и т.д.):",
            parse_mode="Markdown"
        )
        return ADMIN_FINISHED_PACKAGE_TYPE
    
    package_map = {
        "admin_fin_pkg_paket": "Пакет",
        "admin_fin_pkg_banka": "Банка",
        "admin_fin_pkg_korobka": "Коробка"
    }
    
    package_type = package_map.get(query.data)
    context.user_data["admin_finished_package_type"] = package_type
    
    await query.edit_message_text(
        f"📦 *Добавление готовой продукции*\n\n"
        f"Название: *{context.user_data['admin_finished_name']}*\n"
        f"Тара: *{package_type}*\n\n"
        f"Введите вес упаковки (кг):",
        parse_mode="Markdown"
    )
    
    return ADMIN_FINISHED_PACKAGE_WEIGHT


async def admin_finished_package_type_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод кастомного типа тары."""
    package_type = update.message.text.strip()
    context.user_data["admin_finished_package_type"] = package_type
    
    await update.message.reply_text(
        f"📦 *Добавление готовой продукции*\n\n"
        f"Название: *{context.user_data['admin_finished_name']}*\n"
        f"Тара: *{package_type}*\n\n"
        f"Введите вес упаковки (кг):",
        parse_mode="Markdown"
    )
    
    return ADMIN_FINISHED_PACKAGE_WEIGHT


async def admin_finished_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение готовой продукции."""
    try:
        package_weight = float(update.message.text.strip().replace(",", "."))
        
        if package_weight <= 0:
            await update.message.reply_text("❌ Вес должен быть больше 0. Попробуйте снова:")
            return ADMIN_FINISHED_PACKAGE_WEIGHT
        
        category_id = context.user_data["admin_finished_category_id"]
        name = context.user_data["admin_finished_name"]
        package_type = context.user_data["admin_finished_package_type"]
        user_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            product = finished_product_service.create_finished_product(
                db,
                category_id=category_id,
                name=name,
                package_type=package_type,
                package_weight=package_weight,
                created_by=user_id
            )
            
            await update.message.reply_text(
                f"✅ Готовая продукция добавлена!\n\n"
                f"📦 {product.category.name} / {product.name}\n"
                f"Тара: {product.package_type} {product.package_weight}кг\n"
                f"ID: {product.id}",
                reply_markup=get_back_to_settings_button()
            )
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Ошибка при создании готовой продукции: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка: {e}",
                reply_markup=get_back_to_settings_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        finally:
            db.close()
            
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа. Введите вес (например: 0.5 или 1):"
        )
        return ADMIN_FINISHED_PACKAGE_WEIGHT


# ============================================================================
# ОТМЕНА
# ============================================================================

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена админской операции."""
    context.user_data.clear()
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "❌ Операция отменена",
            reply_markup=get_back_to_settings_button()
        )
    else:
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=get_back_to_settings_button()
        )
    
    return ConversationHandler.END
