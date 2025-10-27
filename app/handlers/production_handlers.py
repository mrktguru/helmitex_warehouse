"""
Обработчики для производства полуфабрикатов по технологическим картам.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services import recipe_service, stock_service
from app.database.models import RecipeStatus
from app.utils.formatters import format_recipe_list, format_materials_check
from app.logger import get_logger

logger = get_logger("production_handlers")

# Состояния для ConversationHandler
PRODUCTION_SELECT_RECIPE, PRODUCTION_ENTER_WEIGHT, PRODUCTION_CONFIRM = range(3)


def get_back_to_main_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
    ]])


# ============================================================================
# ПРОИЗВОДСТВО - НАЧАЛО
# ============================================================================

async def production_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню производства."""
    query = update.callback_query
    await query.answer()
    
    db = SessionLocal()
    try:
        # Получаем активные рецепты
        recipes = recipe_service.get_recipes(db, status=RecipeStatus.active)
        
        if not recipes:
            await query.edit_message_text(
                "❌ Нет активных технологических карт.\n\n"
                "Администратор должен сначала создать и активировать ТК в настройках.",
                reply_markup=get_back_to_main_button()
            )
            return ConversationHandler.END
        
        # Создаем кнопки с рецептами
        keyboard = []
        for recipe in recipes:
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {recipe.name} (выход: {recipe.yield_percent}%)",
                    callback_data=f"prod_recipe_{recipe.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
        ])
        
        await query.edit_message_text(
            "⚙️ *Производство*\n\n"
            "Выберите технологическую карту:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return PRODUCTION_SELECT_RECIPE
        
    except Exception as e:
        logger.error(f"Ошибка в production_menu_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ВВОД ЦЕЛЕВОГО ВЕСА
# ============================================================================

async def production_enter_weight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос целевого веса полуфабриката."""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID рецепта
    recipe_id = int(query.data.split("_")[-1])
    context.user_data["production_recipe_id"] = recipe_id
    
    db = SessionLocal()
    try:
        recipe = recipe_service.get_recipe_by_id(db, recipe_id)
        
        # Формируем информацию о рецепте
        components_text = ""
        for component in recipe.components:
            components_text += (
                f"• {component.raw_material.category.name} / "
                f"{component.raw_material.name}: {component.percentage:.1f}%\n"
            )
        
        await query.edit_message_text(
            f"⚙️ *Производство*\n\n"
            f"📋 *ТК: {recipe.name}*\n"
            f"Продукт: *{recipe.semi_product.category.name} / {recipe.semi_product.name}*\n"
            f"Выход: *{recipe.yield_percent}%*\n\n"
            f"*Состав:*\n{components_text}\n"
            f"Введите целевой вес полуфабриката ({recipe.semi_product.unit.value}):",
            parse_mode="Markdown"
        )
        
        return PRODUCTION_ENTER_WEIGHT
        
    except Exception as e:
        logger.error(f"Ошибка в production_enter_weight_callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_to_main_button()
        )
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ПОДТВЕРЖДЕНИЕ ПРОИЗВОДСТВА
# ============================================================================

async def production_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка наличия сырья и подтверждение."""
    try:
        target_weight = float(update.message.text.strip().replace(",", "."))
        
        if target_weight <= 0:
            await update.message.reply_text(
                "❌ Вес должен быть больше 0.\n"
                "Попробуйте снова:"
            )
            return PRODUCTION_ENTER_WEIGHT
        
        recipe_id = context.user_data["production_recipe_id"]
        context.user_data["production_target_weight"] = target_weight
        
        db = SessionLocal()
        try:
            # Проверяем наличие сырья
            check_result = recipe_service.check_materials_availability(
                db, recipe_id, target_weight
            )
            
            recipe = recipe_service.get_recipe_by_id(db, recipe_id)
            
            # Формируем текст с проверкой
            text = (
                f"⚙️ *Производство*\n\n"
                f"📋 *ТК: {recipe.name}*\n"
                f"Целевой вес: *{target_weight:.2f} {recipe.semi_product.unit.value}*\n\n"
            )
            
            text += format_materials_check(check_result)
            
            if check_result["available"]:
                keyboard = [
                    [InlineKeyboardButton("✅ Начать производство", callback_data="prod_start")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ]
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
            if check_result["available"]:
                return PRODUCTION_CONFIRM
            else:
                context.user_data.clear()
                return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Ошибка при проверке сырья: {e}", exc_info=True)
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
            "Введите вес (например: 100 или 100.5):"
        )
        return PRODUCTION_ENTER_WEIGHT


# ============================================================================
# ЗАПУСК ПРОИЗВОДСТВА
# ============================================================================

async def production_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск производства."""
    query = update.callback_query
    await query.answer("⚙️ Запускаем производство...")
    
    recipe_id = context.user_data["production_recipe_id"]
    target_weight = context.user_data["production_target_weight"]
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        # Запускаем производство
        production = stock_service.start_production(
            db,
            recipe_id=recipe_id,
            target_weight=target_weight,
            operator_id=user_id
        )
        
        recipe = recipe_service.get_recipe_by_id(db, recipe_id)
        
        # Формируем отчет о списании
        materials_text = ""
        materials_needed = recipe_service.calculate_materials_needed(db, recipe_id, target_weight)
        
        for material_id, qty in materials_needed.items():
            material = db.query(recipe.components[0].raw_material.__class__).get(material_id)
            materials_text += (
                f"• {material.category.name} / {material.name}: "
                f"-{qty:.2f} {material.unit.value}\n"
            )
        
        await query.edit_message_text(
            f"✅ *Производство завершено!*\n\n"
            f"📋 *ТК: {recipe.name}*\n\n"
            f"*Списано сырья:*\n{materials_text}\n"
            f"*Получено:*\n"
            f"✅ {recipe.semi_product.category.name} / {recipe.semi_product.name}: "
            f"+{target_weight:.2f} {recipe.semi_product.unit.value}\n\n"
            f"📅 Дата: {production.created_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_back_to_main_button(),
            parse_mode="Markdown"
        )
        
        logger.info(
            f"Производство завершено: ТК '{recipe.name}', "
            f"получено {target_weight} {recipe.semi_product.unit.value} "
            f"(пользователь: {user_id})"
        )
        
        # Очищаем данные
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при запуске производства: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Ошибка при производстве: {e}",
            reply_markup=get_back_to_main_button()
        )
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


# ============================================================================
# ОТМЕНА
# ============================================================================

async def production_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции производства."""
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
