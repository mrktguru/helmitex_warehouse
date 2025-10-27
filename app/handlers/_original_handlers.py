"""
Обработчики команд Telegram бота с inline кнопками.
"""
from typing import Dict, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    ConversationHandler, 
    MessageHandler,
    CallbackQueryHandler,
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
# ГЛАВНОЕ МЕНЮ С INLINE КНОПКАМИ
# ============================================================================

def get_main_menu_keyboard():
    """Создает главное меню с inline кнопками."""
    keyboard = [
        [
            InlineKeyboardButton("📦 Номенклатура", callback_data="menu_sku"),
            InlineKeyboardButton("📁 Категории", callback_data="menu_category")
        ],
        [
            InlineKeyboardButton("📋 Рецепты", callback_data="menu_recipe"),
            InlineKeyboardButton("🛢️ Бочки", callback_data="menu_barrel")
        ],
        [
            InlineKeyboardButton("⚙️ Производство", callback_data="menu_production"),
            InlineKeyboardButton("📊 Отчеты", callback_data="menu_reports")
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_sku_menu_keyboard():
    """Меню номенклатуры."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить SKU", callback_data="sku_add")],
        [InlineKeyboardButton("📋 Список SKU", callback_data="sku_list")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_menu_keyboard():
    """Меню категорий."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить категорию", callback_data="category_add")],
        [InlineKeyboardButton("📋 Список категорий", callback_data="category_list")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_recipe_menu_keyboard():
    """Меню рецептов."""
    keyboard = [
        [InlineKeyboardButton("➕ Создать рецепт", callback_data="recipe_new")],
        [InlineKeyboardButton("📋 Список рецептов", callback_data="recipe_list")],
        [InlineKeyboardButton("📝 Черновики", callback_data="recipe_drafts")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_barrel_menu_keyboard():
    """Меню бочек."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить бочку", callback_data="barrel_add")],
        [InlineKeyboardButton("📋 Список бочек", callback_data="barrel_list")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_sku_type_keyboard():
    """Клавиатура выбора типа SKU."""
    keyboard = [
        [InlineKeyboardButton("🌾 Сырье", callback_data="sku_type_raw")],
        [InlineKeyboardButton("⚙️ Полуфабрикат", callback_data="sku_type_semi")],
        [InlineKeyboardButton("✅ Готовая продукция", callback_data="sku_type_finished")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# КОМАНДА /start
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с главным меню."""
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    
    await update.message.reply_text(
        "👋 *Добро пожаловать в Helmitex Warehouse!*\n\n"
        "Система управления складом и производством.\n"
        "Выберите раздел:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


# ============================================================================
# ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ (INLINE КНОПКИ)
# ============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"Пользователь {update.effective_user.id} нажал кнопку: {data}")
    
    # Главное меню
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 *Главное меню*\n\nВыберите раздел:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Меню номенклатуры
    elif data == "menu_sku":
        await query.edit_message_text(
            "📦 *Номенклатура*\n\nУправление товарами и материалами:",
            reply_markup=get_sku_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Меню категорий
    elif data == "menu_category":
        await query.edit_message_text(
            "📁 *Категории*\n\nУправление категориями сырья:",
            reply_markup=get_category_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Меню рецептов
    elif data == "menu_recipe":
        await query.edit_message_text(
            "📋 *Рецепты*\n\nУправление технологическими картами:",
            reply_markup=get_recipe_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Меню бочек
    elif data == "menu_barrel":
        await query.edit_message_text(
            "🛢️ *Бочки*\n\nУправление производственными емкостями:",
            reply_markup=get_barrel_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Список SKU
    elif data == "sku_list":
        try:
            db = SessionLocal()
            skus = services.list_skus(db)
            text = format_sku_list(skus)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_sku")
                ]])
            )
        except Exception as e:
            logger.error(f"Ошибка при получении списка SKU: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
        finally:
            db.close()
    
    # Список категорий
    elif data == "category_list":
        try:
            db = SessionLocal()
            categories = services.list_categories(db)
            text = format_category_list(categories)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_category")
                ]])
            )
        except Exception as e:
            logger.error(f"Ошибка при получении списка категорий: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
        finally:
            db.close()
    
    # Список рецептов
    elif data == "recipe_list":
        try:
            db = SessionLocal()
            recipes = services.list_recipes(db, status=RecipeStatus.active)
            text = format_recipe_list(recipes)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_recipe")
                ]])
            )
        except Exception as e:
            logger.error(f"Ошибка при получении списка рецептов: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
        finally:
            db.close()
    
    # Список бочек
    elif data == "barrel_list":
        try:
            db = SessionLocal()
            barrels = services.list_barrels(db)
            text = format_barrel_list(barrels)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_barrel")
                ]])
            )
        except Exception as e:
            logger.error(f"Ошибка при получении списка бочек: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
        finally:
            db.close()
    
    # Черновики рецептов (только для владельца)
    elif data == "recipe_drafts":
        if update.effective_user.id != OWNER_TELEGRAM_ID:
            await query.answer("❌ У вас нет прав для этой команды", show_alert=True)
            return
        
        try:
            db = SessionLocal()
            recipes = services.list_recipes(db, status=RecipeStatus.draft)
            text = format_recipe_list(recipes)
            await query.edit_message_text(
                f"📝 *Черновики рецептов:*\n\n{text}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="menu_recipe")
                ]]),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при получении черновиков: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
        finally:
            db.close()
    
    # Помощь
    elif data == "menu_help":
        help_text = (
            "ℹ️ *Справка по боту*\n\n"
            "*Основные функции:*\n"
            "• Управление номенклатурой (SKU)\n"
            "• Категории сырья\n"
            "• Технологические карты (рецепты)\n"
            "• Учет бочек\n"
            "• Производственный процесс\n\n"
            "*Команды:*\n"
            "/start - Главное меню\n"
            "/help - Эта справка\n\n"
            "*Поддержка:* @your_support"
        )
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")
            ]]),
            parse_mode="Markdown"
        )


# ============================================================================
# СТАРЫЕ ОБРАБОТЧИКИ (для совместимости с командами)
# ============================================================================

async def sku_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список номенклатуры (команда)."""
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


async def category_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список категорий (команда)."""
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи."""
    await update.message.reply_text(
        "ℹ️ *Справка по боту*\n\n"
        "Используйте /start для открытия главного меню с кнопками.",
        parse_mode="Markdown"
    )


# ============================================================================
# ПОСТРОЕНИЕ ПРИЛОЖЕНИЯ
# ============================================================================

def build_application():
    """Создает и настраивает приложение бота."""
    logger.info("Создание Telegram приложения...")
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Обработчик inline кнопок (ВАЖНО: добавить первым!)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("sku_list", sku_list_command))
    application.add_handler(CommandHandler("category_list", category_list_command))
    
    logger.info("✅ Обработчики команд добавлены")
    return application
