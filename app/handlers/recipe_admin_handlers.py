"""
Обработчики для управления технологическими картами (только админ).
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import recipe_service, semi_product_service, raw_material_service
from app.database.models import RecipeStatus
from app.utils.formatters import format_recipe_list, format_recipe_details
from app.utils.helpers import parse_key_value_lines, validate_percentage_sum
from app.config import OWNER_TELEGRAM_ID
from app.logger import get_logger

logger = get_logger("recipe_admin_handlers")

# Состояния для ConversationHandler
RECIPE_NAME, RECIPE_SEMI, RECIPE_YIELD, RECIPE_COMPONENTS = range(4)


def get_back_to_settings_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в настройки."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")
    ]])


# ============================================================================
# УПРАВЛЕНИЕ РЕЦЕПТАМИ
# ============================================================================

async def admin_recipes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления рецептами."""
    query = update.callback_query
    
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
        return
    
    await query.answer()
    
    db = SessionLocal()
    try:
        recipes = recipe_service.get_recipes(db)
        text = format_recipe_list(recipes)
        
        keyboard = [
            [InlineKeyboardButton("➕ Создать ТК", callback_data="admin_recipe_add")],
            [InlineKeyboardButton("📝 Черновики", callback_data="admin_recipe_drafts")],
            [InlineKeyboardButton("🔙 К настройкам", callback_data="admin_settings")]
        ]
        
        await query.edit_message_text(
            f"{text}\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_recipes_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_recipe_drafts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список черновиков рецептов."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        recipes = recipe_service.get_recipes(db, status=RecipeStatus.draft)
        
        if not recipes:
            await query.edit_message_text(
                "📝 Черновиков нет",
                reply_markup=get_back_to_settings_button()
            )
            return
        
        keyboard = []
        for recipe in recipes:
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {recipe.name} (ID: {recipe.id})",
                    callback_data=f"admin_recipe_view_{recipe.id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("🔙 К рецептам", callback_data="admin_recipes")
        ])
        
        await query.edit_message_text(
            "📝 *Черновики рецептов*\n\nВыберите рецепт для просмотра:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_recipe_drafts_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_recipe_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр рецепта."""
    query = update.callback_query
    await query.answer()
    
    recipe_id = int(query.data.split("_")[-1])
    
    db = SessionLocal()
    try:
        recipe = recipe_service.get_recipe_by_id(db, recipe_id)
        text = format_recipe_details(recipe)
        
        keyboard = []
        
        if recipe.status == RecipeStatus.draft:
            keyboard.append([
                InlineKeyboardButton("✅ Активировать", callback_data=f"admin_recipe_activate_{recipe_id}")
            ])
        elif recipe.status == RecipeStatus.active:
            keyboard.append([
                InlineKeyboardButton("📦 Архивировать", callback_data=f"admin_recipe_archive_{recipe_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 К рецептам", callback_data="admin_recipes")
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_recipe_view_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_recipe_activate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активация рецепта."""
    query = update.callback_query
    await query.answer()
    
    recipe_id = int(query.data.split("_")[-1])
    
    db = SessionLocal()
    try:
        recipe = recipe_service.activate_recipe(db, recipe_id)
        
        await query.edit_message_text(
            f"✅ Рецепт активирован!\n\n"
            f"📋 {recipe.name}\n"
            f"Статус: {recipe.status.value}",
            reply_markup=get_back_to_settings_button()
        )
    except Exception as e:
        logger.error(f"Ошибка при активации рецепта: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


async def admin_recipe_archive_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Архивация рецепта."""
    query = update.callback_query
    await query.answer()
    
    recipe_id = int(query.data.split("_")[-1])
    
    db = SessionLocal()
    try:
        recipe = recipe_service.archive_recipe(db, recipe_id)
        
        await query.edit_message_text(
            f"📦 Рецепт архивирован!\n\n"
            f"📋 {recipe.name}\n"
            f"Статус: {recipe.status.value}",
            reply_markup=get_back_to_settings_button()
        )
    except Exception as e:
        logger.error(f"Ошибка при архивации рецепта: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
    finally:
        db.close()


# ============================================================================
# СОЗДАНИЕ РЕЦЕПТА
# ============================================================================

async def admin_recipe_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания рецепта."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📋 *Создание технологической карты*\n\n"
        "Введите название ТК:",
        parse_mode="Markdown"
    )
    
    return RECIPE_NAME


async def admin_recipe_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия рецепта."""
    name = update.message.text.strip()
    context.user_data["recipe_name"] = name
    
    db = SessionLocal()
    try:
        semi_products = semi_product_service.get_semi_products(db)
        
        if not semi_products:
            await update.message.reply_text(
                "❌ Нет полуфабрикатов.\n"
                "Сначала создайте полуфабрикат.",
                reply_markup=get_back_to_settings_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        keyboard = []
        for product in semi_products:
            keyboard.append([
                InlineKeyboardButton(
                    f"{product.category.name} / {product.name}",
                    callback_data=f"admin_recipe_semi_{product.id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="admin_recipes")
        ])
        
        await update.message.reply_text(
            f"📋 *Создание ТК*\n\n"
            f"Название: *{name}*\n\n"
            f"Выберите полуфабрикат:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return RECIPE_SEMI
        
    except Exception as e:
        logger.error(f"Ошибка в admin_recipe_name_entered: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


async def admin_recipe_semi_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор полуфабриката."""
    query = update.callback_query
    await query.answer()
    
    semi_product_id = int(query.data.split("_")[-1])
    context.user_data["recipe_semi_id"] = semi_product_id
    
    await query.edit_message_text(
        f"📋 *Создание ТК*\n\n"
        f"Название: *{context.user_data['recipe_name']}*\n\n"
        f"Введите процент выхода (50-100%):",
        parse_mode="Markdown"
    )
    
    return RECIPE_YIELD


async def admin_recipe_yield_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод процента выхода."""
    try:
        yield_percent = float(update.message.text.strip().replace(",", "."))
        
        if not (50 <= yield_percent <= 100):
            await update.message.reply_text(
                "❌ Процент выхода должен быть от 50 до 100.\n"
                "Попробуйте снова:"
            )
            return RECIPE_YIELD
        
        context.user_data["recipe_yield"] = yield_percent
        
        db = SessionLocal()
        try:
            materials = raw_material_service.get_raw_materials(db)
            
            materials_text = "\n".join([
                f"• {m.category.name} / {m.name}"
                for m in materials
            ])
            
            await update.message.reply_text(
                f"📋 *Создание ТК*\n\n"
                f"Название: *{context.user_data['recipe_name']}*\n"
                f"Выход: *{yield_percent}%*\n\n"
                f"*Доступное сырье:*\n{materials_text}\n\n"
                f"Введите состав в формате:\n"
                f"`Категория / Название: процент`\n\n"
                f"Пример:\n"
                f"`Мука / Пшеничная: 60`\n"
                f"`Вода: 30`\n"
                f"`Соль: 10`\n\n"
                f"⚠️ Сумма процентов должна быть 100%",
                parse_mode="Markdown"
            )
            
            return RECIPE_COMPONENTS
            
        except Exception as e:
            logger.error(f"Ошибка в admin_recipe_yield_entered: {e}", exc_info=True)
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
            "❌ Неверный формат числа.\n"
            "Введите процент (например: 80 или 85.5):"
        )
        return RECIPE_YIELD


async def admin_recipe_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение рецепта."""
    components_text = update.message.text.strip()
    
    db = SessionLocal()
    try:
        # Парсим компоненты
        lines = components_text.split("\n")
        components = []
        percentages = []
        
        for line in lines:
            if ":" not in line:
                continue
            
            material_name, percentage_str = line.split(":", 1)
            material_name = material_name.strip()
            percentage = float(percentage_str.strip().replace(",", "."))
            
            # Ищем материал
            materials = raw_material_service.get_raw_materials(db)
            material = None
            
            for m in materials:
                full_name = f"{m.category.name} / {m.name}"
                if material_name.lower() in full_name.lower() or m.name.lower() == material_name.lower():
                    material = m
                    break
            
            if not material:
                await update.message.reply_text(
                    f"❌ Сырье '{material_name}' не найдено.\n"
                    f"Проверьте название и попробуйте снова.",
                    reply_markup=get_back_to_settings_button()
                )
                return RECIPE_COMPONENTS
            
            components.append({
                "raw_material_id": material.id,
                "percentage": percentage
            })
            percentages.append(percentage)
        
        # Проверяем сумму процентов
        if not validate_percentage_sum(percentages):
            total = sum(percentages)
            await update.message.reply_text(
                f"❌ Сумма процентов = {total:.1f}%, должна быть 100%.\n"
                f"Попробуйте снова:"
            )
            return RECIPE_COMPONENTS
        
        # Создаем рецепт
        recipe = recipe_service.create_recipe(
            db,
            name=context.user_data["recipe_name"],
            semi_product_id=context.user_data["recipe_semi_id"],
            yield_percent=context.user_data["recipe_yield"],
            components=components,
            created_by=update.effective_user.id
        )
        
        await update.message.reply_text(
            f"✅ Технологическая карта создана!\n\n"
            f"📋 {recipe.name}\n"
            f"ID: {recipe.id}\n"
            f"Статус: {recipe.status.value}\n\n"
            f"Для активации используйте просмотр черновиков.",
            reply_markup=get_back_to_settings_button()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании рецепта: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_settings_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


async def admin_recipe_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания рецепта."""
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
