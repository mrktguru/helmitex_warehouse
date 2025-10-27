"""
Обработчики команд Telegram бота.
Временный файл - будет разделен на модули.
"""
from typing import Dict, Tuple
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    ConversationHandler, 
    MessageHandler, 
    filters
)

from app.config import TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID
from app.database.db import SessionLocal
from app.database.models import SKUType, RecipeStatus, BarrelStatus
from app.services import _original_services as services
from app.utils.helpers import (
    parse_key_value_lines,
    format_sku_list,
    format_recipe_list,
    format_category_list,
    format_barrel_list
)
from app.logger import get_logger

logger = get_logger("handlers")

# Состояния для ConversationHandler
(
    SKU_ADD_TYPE, SKU_ADD_CODE, SKU_ADD_NAME, SKU_ADD_UNIT, 
    SKU_ADD_PACKAGE_WEIGHT, SKU_ADD_CATEGORY,
    CATEGORY_ADD_NAME,
    RECIPE_NEW_SEMI, RECIPE_NEW_YIELD, RECIPE_NEW_COMPONENTS,
    PRODUCE_RECIPE, PRODUCE_BARREL, PRODUCE_TARGET_WEIGHT, PRODUCE_ACTUAL_WEIGHT, PRODUCE_RAW
) = range(15)


# ============================================================================
# КОМАНДА /start
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    await update.message.reply_text(
        "👋 Добро пожаловать в Helmitex Warehouse!\n\n"
        "📦 **Номенклатура:**\n"
        "/sku_add - Добавить номенклатуру\n"
        "/sku_list - Список номенклатуры\n\n"
        "📁 **Категории:**\n"
        "/category_add - Добавить категорию\n"
        "/category_list - Список категорий\n\n"
        "📋 **Рецепты:**\n"
        "/recipe_new - Создать рецепт\n"
        "/recipe_list - Список рецептов\n\n"
        "⚙️ **Производство:**\n"
        "/produce - Начать производство\n\n"
        "🛢️ **Бочки:**\n"
        "/barrel_add - Добавить бочку\n"
        "/barrel_list - Список бочек\n\n"
        "🔐 **Админские команды:**\n"
        "/tk_drafts - Черновики рецептов\n"
        "/tk_activate <id> - Активировать рецепт",
        parse_mode="Markdown"
    )


# ============================================================================
# КАТЕГОРИИ
# ============================================================================

async def category_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления категории."""
    logger.info(f"Пользователь {update.effective_user.id} начал добавление категории")
    await update.message.reply_text("📁 Введите название категории:")
    return CATEGORY_ADD_NAME


async def category_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение категории."""
    name = update.message.text.strip()
    
    try:
        db = SessionLocal()
        category = services.add_category(db, name)
        logger.info(f"Категория '{name}' добавлена (ID: {category.id})")
        await update.message.reply_text(f"✅ Категория '{name}' успешно добавлена!")
    except Exception as e:
        logger.error(f"Ошибка при добавлении категории: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()
    
    return ConversationHandler.END


async def category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список категорий."""
    try:
        db = SessionLocal()
        categories = services.list_categories(db)
        text = format_category_list(categories)
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка категорий: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


# ============================================================================
# НОМЕНКЛАТУРА (SKU)
# ============================================================================

async def sku_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления SKU."""
    logger.info(f"Пользователь {update.effective_user.id} начал добавление SKU")
    await update.message.reply_text(
        "📦 Выберите тип номенклатуры:\n"
        "1 - Сырье (raw)\n"
        "2 - Полуфабрикат (semi)\n"
        "3 - Готовая продукция (finished)"
    )
    return SKU_ADD_TYPE


async def sku_add_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа SKU."""
    type_map = {"1": SKUType.raw, "2": SKUType.semi, "3": SKUType.finished}
    sku_type = type_map.get(update.message.text.strip())
    
    if not sku_type:
        await update.message.reply_text("❌ Неверный выбор. Введите 1, 2 или 3:")
        return SKU_ADD_TYPE
    
    context.user_data["sku_type"] = sku_type
    await update.message.reply_text("📝 Введите код номенклатуры:")
    return SKU_ADD_CODE


async def sku_add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод кода SKU."""
    code = update.message.text.strip().upper()
    context.user_data["sku_code"] = code
    await update.message.reply_text("📝 Введите название:")
    return SKU_ADD_NAME


async def sku_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия SKU."""
    name = update.message.text.strip()
    context.user_data["sku_name"] = name
    await update.message.reply_text("📏 Введите единицу измерения (кг, л, шт):")
    return SKU_ADD_UNIT


async def sku_add_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод единицы измерения."""
    unit = update.message.text.strip()
    context.user_data["sku_unit"] = unit
    await update.message.reply_text(
        "⚖️ Введите вес упаковки (или 0 если не применимо):"
    )
    return SKU_ADD_PACKAGE_WEIGHT


async def sku_add_package_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод веса упаковки."""
    try:
        weight = float(update.message.text.strip())
        context.user_data["package_weight"] = weight if weight > 0 else None
        
        # Если сырье, спрашиваем категорию
        if context.user_data["sku_type"] == SKUType.raw:
            db = SessionLocal()
            categories = services.list_categories(db)
            db.close()
            
            if categories:
                cat_text = "\n".join([f"{i+1} - {cat.name}" for i, cat in enumerate(categories)])
                context.user_data["categories"] = categories
                await update.message.reply_text(
                    f"📁 Выберите категорию:\n{cat_text}\n\n0 - Без категории"
                )
                return SKU_ADD_CATEGORY
        
        # Сохраняем SKU
        return await sku_save(update, context)
        
    except ValueError:
        await update.message.reply_text("❌ Введите число:")
        return SKU_ADD_PACKAGE_WEIGHT


async def sku_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор категории для сырья."""
    try:
        choice = int(update.message.text.strip())
        categories = context.user_data.get("categories", [])
        
        if choice == 0:
            context.user_data["category_id"] = None
        elif 1 <= choice <= len(categories):
            context.user_data["category_id"] = categories[choice - 1].id
        else:
            await update.message.reply_text("❌ Неверный выбор. Попробуйте снова:")
            return SKU_ADD_CATEGORY
        
        return await sku_save(update, context)
        
    except ValueError:
        await update.message.reply_text("❌ Введите число:")
        return SKU_ADD_CATEGORY


async def sku_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение SKU в базу."""
    try:
        db = SessionLocal()
        sku = services.add_sku(
            db,
            code=context.user_data["sku_code"],
            name=context.user_data["sku_name"],
            sku_type=context.user_data["sku_type"],
            unit=context.user_data["sku_unit"],
            package_weight=context.user_data.get("package_weight"),
            category_id=context.user_data.get("category_id")
        )
        logger.info(f"SKU '{sku.code}' добавлен (ID: {sku.id})")
        await update.message.reply_text(
            f"✅ Номенклатура успешно добавлена!\n"
            f"Код: {sku.code}\n"
            f"Название: {sku.name}\n"
            f"Тип: {sku.type.value}"
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении SKU: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()
        context.user_data.clear()
    
    return ConversationHandler.END


async def sku_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список номенклатуры."""
    try:
        db = SessionLocal()
        skus = services.list_skus(db)
        text = format_sku_list(skus)
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка SKU: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


# ============================================================================
# РЕЦЕПТЫ
# ============================================================================

async def recipe_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания рецепта."""
    logger.info(f"Пользователь {update.effective_user.id} начал создание рецепта")
    
    try:
        db = SessionLocal()
        semi_skus = services.list_skus(db, sku_type=SKUType.semi)
        db.close()
        
        if not semi_skus:
            await update.message.reply_text(
                "❌ Нет полуфабрикатов. Сначала добавьте полуфабрикат через /sku_add"
            )
            return ConversationHandler.END
        
        sku_text = "\n".join([f"{i+1} - {sku.code} ({sku.name})" for i, sku in enumerate(semi_skus)])
        context.user_data["semi_skus"] = semi_skus
        
        await update.message.reply_text(
            f"📋 Выберите полуфабрикат:\n{sku_text}"
        )
        return RECIPE_NEW_SEMI
        
    except Exception as e:
        logger.error(f"Ошибка при начале создания рецепта: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END


async def recipe_new_semi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор полуфабриката."""
    try:
        choice = int(update.message.text.strip())
        semi_skus = context.user_data.get("semi_skus", [])
        
        if 1 <= choice <= len(semi_skus):
            context.user_data["semi_sku_id"] = semi_skus[choice - 1].id
            await update.message.reply_text(
                "📊 Введите теоретический выход (% от 50 до 100):"
            )
            return RECIPE_NEW_YIELD
        else:
            await update.message.reply_text("❌ Неверный выбор. Попробуйте снова:")
            return RECIPE_NEW_SEMI
            
    except ValueError:
        await update.message.reply_text("❌ Введите число:")
        return RECIPE_NEW_SEMI


async def recipe_new_yield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод теоретического выхода."""
    try:
        yield_pct = float(update.message.text.strip())
        
        if not (50 <= yield_pct <= 100):
            await update.message.reply_text("❌ Выход должен быть от 50 до 100%:")
            return RECIPE_NEW_YIELD
        
        context.user_data["theoretical_yield"] = yield_pct
        
        db = SessionLocal()
        raw_skus = services.list_skus(db, sku_type=SKUType.raw)
        db.close()
        
        if not raw_skus:
            await update.message.reply_text(
                "❌ Нет сырья. Сначала добавьте сырье через /sku_add"
            )
            return ConversationHandler.END
        
        sku_text = "\n".join([f"{sku.code} - {sku.name}" for sku in raw_skus])
        
        await update.message.reply_text(
            f"🌾 Введите компоненты рецепта в формате:\n"
            f"код_сырья: процент\n\n"
            f"Пример:\n"
            f"RAW001: 50\n"
            f"RAW002: 30\n"
            f"RAW003: 20\n\n"
            f"Доступное сырье:\n{sku_text}\n\n"
            f"⚠️ Сумма процентов должна быть 100%"
        )
        return RECIPE_NEW_COMPONENTS
        
    except ValueError:
        await update.message.reply_text("❌ Введите число:")
        return RECIPE_NEW_YIELD


async def recipe_new_components(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод компонентов рецепта."""
    try:
        components_data = parse_key_value_lines(update.message.text)
        
        db = SessionLocal()
        components = []
        total_pct = 0
        
        for code, pct_str in components_data.items():
            sku = services.find_sku_by_code(db, code.upper())
            if not sku:
                db.close()
                await update.message.reply_text(f"❌ Сырье с кодом '{code}' не найдено")
                return RECIPE_NEW_COMPONENTS
            
            if sku.type != SKUType.raw:
                db.close()
                await update.message.reply_text(f"❌ '{code}' не является сырьем")
                return RECIPE_NEW_COMPONENTS
            
            pct = float(pct_str)
            components.append({"raw_sku_id": sku.id, "percentage": pct})
            total_pct += pct
        
        # Проверка суммы процентов
        if abs(total_pct - 100.0) > 0.01:
            db.close()
            await update.message.reply_text(
                f"❌ Сумма процентов = {total_pct}%, должна быть 100%"
            )
            return RECIPE_NEW_COMPONENTS
        
        # Создаем рецепт
        recipe = services.create_recipe(
            db,
            semi_sku_id=context.user_data["semi_sku_id"],
            theoretical_yield=context.user_data["theoretical_yield"],
            components=components,
            status=RecipeStatus.draft
        )
        
        logger.info(f"Рецепт создан (ID: {recipe.id})")
        await update.message.reply_text(
            f"✅ Рецепт успешно создан!\n"
            f"ID: {recipe.id}\n"
            f"Статус: черновик\n\n"
            f"Для активации обратитесь к администратору"
        )
        
        db.close()
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании рецепта: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END


async def recipe_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список рецептов."""
    try:
        db = SessionLocal()
        recipes = services.list_recipes(db, status=RecipeStatus.active)
        text = format_recipe_list(recipes)
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка рецептов: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


# ============================================================================
# БОЧКИ
# ============================================================================

async def barrel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление бочки."""
    try:
        # Получаем номер бочки из команды
        args = context.args
        if not args:
            await update.message.reply_text("❌ Использование: /barrel_add <номер>")
            return
        
        number = " ".join(args)
        
        db = SessionLocal()
        barrel = services.add_barrel(db, number)
        logger.info(f"Бочка '{number}' добавлена (ID: {barrel.id})")
        await update.message.reply_text(f"✅ Бочка '{number}' успешно добавлена!")
        db.close()
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении бочки: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def barrel_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список бочек."""
    try:
        db = SessionLocal()
        barrels = services.list_barrels(db)
        text = format_barrel_list(barrels)
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка бочек: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


# ============================================================================
# АДМИНСКИЕ КОМАНДЫ
# ============================================================================

async def tk_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список черновиков рецептов (только для владельца)."""
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    try:
        db = SessionLocal()
        recipes = services.list_recipes(db, status=RecipeStatus.draft)
        text = format_recipe_list(recipes)
        await update.message.reply_text(f"📝 Черновики:\n\n{text}")
    except Exception as e:
        logger.error(f"Ошибка при получении черновиков: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


async def tk_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активация рецепта (только для владельца)."""
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text("❌ Использование: /tk_activate <id>")
            return
        
        recipe_id = int(args[0])
        
        db = SessionLocal()
        recipe = services.activate_recipe(db, recipe_id)
        
        if recipe:
            logger.info(f"Рецепт {recipe_id} активирован")
            await update.message.reply_text(f"✅ Рецепт {recipe_id} активирован!")
        else:
            await update.message.reply_text(f"❌ Рецепт {recipe_id} не найден")
        
        db.close()
        
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка при активации рецепта: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ============================================================================
# ОТМЕНА ОПЕРАЦИЙ
# ============================================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции."""
    context.user_data.clear()
    await update.message.reply_text("❌ Операция отменена")
    return ConversationHandler.END


# ============================================================================
# ПОСТРОЕНИЕ ПРИЛОЖЕНИЯ
# ============================================================================

def build_application():
    """Создает и настраивает приложение бота."""
    logger.info("Создание Telegram приложения...")
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Простые команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sku_list", sku_list))
    application.add_handler(CommandHandler("category_list", category_list))
    application.add_handler(CommandHandler("recipe_list", recipe_list))
    application.add_handler(CommandHandler("barrel_add", barrel_add))
    application.add_handler(CommandHandler("barrel_list", barrel_list))
    application.add_handler(CommandHandler("tk_drafts", tk_drafts))
    application.add_handler(CommandHandler("tk_activate", tk_activate))
    
    # ConversationHandler для добавления категории
    category_conv = ConversationHandler(
        entry_points=[CommandHandler("category_add", category_add_start)],
        states={
            CATEGORY_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_add_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(category_conv)
    
    # ConversationHandler для добавления SKU
    sku_conv = ConversationHandler(
        entry_points=[CommandHandler("sku_add", sku_add_start)],
        states={
            SKU_ADD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_type)],
            SKU_ADD_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_code)],
            SKU_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_name)],
            SKU_ADD_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_unit)],
            SKU_ADD_PACKAGE_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_package_weight)],
            SKU_ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_category)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(sku_conv)
    
    # ConversationHandler для создания рецепта
    recipe_conv = ConversationHandler(
        entry_points=[CommandHandler("recipe_new", recipe_new_start)],
        states={
            RECIPE_NEW_SEMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_new_semi)],
            RECIPE_NEW_YIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_new_yield)],
            RECIPE_NEW_COMPONENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_new_components)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(recipe_conv)
    
    logger.info("✅ Обработчики команд добавлены")
    return application
