"""
Главный модуль handlers - соединяет все обработчики и создает приложение.
"""
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

from app.config import TELEGRAM_BOT_TOKEN
from app.logger import get_logger

# Импорты handlers
from .main_handlers import (
    start,
    help_command,
    stock_command,
    main_menu_callback,
    stock_menu_callback,
    admin_settings_callback,
    history_menu_callback
)

from .stock_handlers import (
    stock_raw_callback,
    stock_semi_callback,
    stock_finished_callback,
    history_all_callback,
    history_arrival_callback,
    history_production_callback,
    history_packing_callback,
    history_shipment_callback
)

from .arrival_handlers import (
    arrival_menu_callback,
    arrival_select_material_callback,
    arrival_enter_quantity_callback,
    arrival_save,
    arrival_cancel,
    ARRIVAL_SELECT_CATEGORY,
    ARRIVAL_SELECT_MATERIAL,
    ARRIVAL_ENTER_QUANTITY
)

from .production_handlers import (
    production_menu_callback,
    production_enter_weight_callback,
    production_confirm,
    production_start_callback,
    production_cancel,
    PRODUCTION_SELECT_RECIPE,
    PRODUCTION_ENTER_WEIGHT,
    PRODUCTION_CONFIRM
)

from .packing_handlers import (
    packing_menu_callback,
    packing_select_finished_callback,
    packing_enter_quantity_callback,
    packing_save,
    packing_cancel,
    PACKING_SELECT_SEMI,
    PACKING_SELECT_FINISHED,
    PACKING_ENTER_QUANTITY
)

from .shipment_handlers import (
    shipment_menu_callback,
    shipment_enter_quantity_callback,
    shipment_enter_destination,
    shipment_save_callback,
    shipment_save_text,
    shipment_cancel,
    SHIPMENT_SELECT_PRODUCT,
    SHIPMENT_ENTER_QUANTITY,
    SHIPMENT_ENTER_DESTINATION
)

from .admin_handlers import (
    admin_categories_callback,
    admin_category_add_start,
    admin_category_type_selected,
    admin_category_save,
    admin_raw_materials_callback,
    admin_raw_add_start,
    admin_raw_category_selected,
    admin_raw_name_entered,
    admin_raw_save,
    admin_semi_products_callback,
    admin_semi_add_start,
    admin_semi_category_selected,
    admin_semi_name_entered,
    admin_semi_save,
    admin_finished_products_callback,
    admin_finished_add_start,
    admin_finished_category_selected,
    admin_finished_name_entered,
    admin_finished_package_type_selected,
    admin_finished_package_type_custom,
    admin_finished_save,
    admin_cancel,
    ADMIN_CATEGORY_NAME,
    ADMIN_CATEGORY_TYPE,
    ADMIN_RAW_CATEGORY,
    ADMIN_RAW_NAME,
    ADMIN_RAW_UNIT,
    ADMIN_SEMI_CATEGORY,
    ADMIN_SEMI_NAME,
    ADMIN_SEMI_UNIT,
    ADMIN_FINISHED_CATEGORY,
    ADMIN_FINISHED_NAME,
    ADMIN_FINISHED_PACKAGE_TYPE,
    ADMIN_FINISHED_PACKAGE_WEIGHT
)

from .recipe_admin_handlers import (
    admin_recipes_callback,
    admin_recipe_drafts_callback,
    admin_recipe_view_callback,
    admin_recipe_activate_callback,
    admin_recipe_archive_callback,
    admin_recipe_add_start,
    admin_recipe_name_entered,
    admin_recipe_semi_selected,
    admin_recipe_yield_entered,
    admin_recipe_save,
    admin_recipe_cancel,
    RECIPE_NAME,
    RECIPE_SEMI,
    RECIPE_YIELD,
    RECIPE_COMPONENTS
)

logger = get_logger("handlers")


def build_application():
    """
    Создает и настраивает приложение бота со всеми handlers.
    
    Returns:
        Application: Настроенное приложение бота
    """
    logger.info("Создание Telegram приложения...")
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ========================================================================
    # ПРОСТЫЕ КОМАНДЫ
    # ========================================================================
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stock", stock_command))
    
    # ========================================================================
    # CALLBACK HANDLERS (НАВИГАЦИЯ)
    # ========================================================================
    
    # Главное меню и навигация
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(stock_menu_callback, pattern="^stock_menu$"))
    application.add_handler(CallbackQueryHandler(admin_settings_callback, pattern="^admin_settings$"))
    application.add_handler(CallbackQueryHandler(history_menu_callback, pattern="^history_menu$"))
    
    # Остатки
    application.add_handler(CallbackQueryHandler(stock_raw_callback, pattern="^stock_raw$"))
    application.add_handler(CallbackQueryHandler(stock_semi_callback, pattern="^stock_semi$"))
    application.add_handler(CallbackQueryHandler(stock_finished_callback, pattern="^stock_finished$"))
    
    # История
    application.add_handler(CallbackQueryHandler(history_all_callback, pattern="^history_all$"))
    application.add_handler(CallbackQueryHandler(history_arrival_callback, pattern="^history_arrival$"))
    application.add_handler(CallbackQueryHandler(history_production_callback, pattern="^history_production$"))
    application.add_handler(CallbackQueryHandler(history_packing_callback, pattern="^history_packing$"))
    application.add_handler(CallbackQueryHandler(history_shipment_callback, pattern="^history_shipment$"))
    
    # Админ-панель (навигация)
    application.add_handler(CallbackQueryHandler(admin_categories_callback, pattern="^admin_categories$"))
    application.add_handler(CallbackQueryHandler(admin_raw_materials_callback, pattern="^admin_raw_materials$"))
    application.add_handler(CallbackQueryHandler(admin_semi_products_callback, pattern="^admin_semi_products$"))
    application.add_handler(CallbackQueryHandler(admin_finished_products_callback, pattern="^admin_finished_products$"))
    application.add_handler(CallbackQueryHandler(admin_recipes_callback, pattern="^admin_recipes$"))
    application.add_handler(CallbackQueryHandler(admin_recipe_drafts_callback, pattern="^admin_recipe_drafts$"))
    application.add_handler(CallbackQueryHandler(admin_recipe_view_callback, pattern="^admin_recipe_view_"))
    application.add_handler(CallbackQueryHandler(admin_recipe_activate_callback, pattern="^admin_recipe_activate_"))
    application.add_handler(CallbackQueryHandler(admin_recipe_archive_callback, pattern="^admin_recipe_archive_"))
    
    # ========================================================================
    # CONVERSATION HANDLERS (ОПЕРАЦИИ)
    # ========================================================================
    
    # ПРИХОД СЫРЬЯ
    arrival_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(arrival_menu_callback, pattern="^arrival_menu$")],
        states={
            ARRIVAL_SELECT_CATEGORY: [
                CallbackQueryHandler(arrival_select_material_callback, pattern="^arrival_cat_")
            ],
            ARRIVAL_SELECT_MATERIAL: [
                CallbackQueryHandler(arrival_enter_quantity_callback, pattern="^arrival_mat_")
            ],
            ARRIVAL_ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, arrival_save)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(arrival_cancel, pattern="^main_menu$"),
            CommandHandler("cancel", arrival_cancel)
        ],
        name="arrival_conversation",
        persistent=False
    )
    application.add_handler(arrival_conv)
    
    # ПРОИЗВОДСТВО
    production_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(production_menu_callback, pattern="^production_menu$")],
        states={
            PRODUCTION_SELECT_RECIPE: [
                CallbackQueryHandler(production_enter_weight_callback, pattern="^prod_recipe_")
            ],
            PRODUCTION_ENTER_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, production_confirm)
            ],
            PRODUCTION_CONFIRM: [
                CallbackQueryHandler(production_start_callback, pattern="^prod_start$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(production_cancel, pattern="^main_menu$"),
            CommandHandler("cancel", production_cancel)
        ],
        name="production_conversation",
        persistent=False
    )
    application.add_handler(production_conv)
    
    # ФАСОВКА
    packing_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(packing_menu_callback, pattern="^packing_menu$")],
        states={
            PACKING_SELECT_SEMI: [
                CallbackQueryHandler(packing_select_finished_callback, pattern="^pack_semi_")
            ],
            PACKING_SELECT_FINISHED: [
                CallbackQueryHandler(packing_enter_quantity_callback, pattern="^pack_fin_")
            ],
            PACKING_ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, packing_save)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(packing_cancel, pattern="^main_menu$"),
            CallbackQueryHandler(packing_menu_callback, pattern="^packing_menu$"),
            CommandHandler("cancel", packing_cancel)
        ],
        name="packing_conversation",
        persistent=False
    )
    application.add_handler(packing_conv)
    
    # ОТГРУЗКА
    shipment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(shipment_menu_callback, pattern="^shipment_menu$")],
        states={
            SHIPMENT_SELECT_PRODUCT: [
                CallbackQueryHandler(shipment_enter_quantity_callback, pattern="^ship_prod_")
            ],
            SHIPMENT_ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_enter_destination)
            ],
            SHIPMENT_ENTER_DESTINATION: [
                CallbackQueryHandler(shipment_save_callback, pattern="^ship_dest_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, shipment_save_text)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(shipment_cancel, pattern="^main_menu$"),
            CommandHandler("cancel", shipment_cancel)
        ],
        name="shipment_conversation",
        persistent=False
    )
    application.add_handler(shipment_conv)
    
    # ========================================================================
    # ADMIN CONVERSATION HANDLERS
    # ========================================================================
    
    # ДОБАВЛЕНИЕ КАТЕГОРИИ
    admin_category_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_category_add_start, pattern="^admin_cat_add$")],
        states={
            ADMIN_CATEGORY_TYPE: [
                CallbackQueryHandler(admin_category_type_selected, pattern="^admin_cat_type_")
            ],
            ADMIN_CATEGORY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_category_save)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern="^admin_categories$"),
            CommandHandler("cancel", admin_cancel)
        ],
        name="admin_category_conversation",
        persistent=False
    )
    application.add_handler(admin_category_conv)
    
    # ДОБАВЛЕНИЕ СЫРЬЯ
    admin_raw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_raw_add_start, pattern="^admin_raw_add$")],
        states={
            ADMIN_RAW_CATEGORY: [
                CallbackQueryHandler(admin_raw_category_selected, pattern="^admin_raw_cat_")
            ],
            ADMIN_RAW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_raw_name_entered)
            ],
            ADMIN_RAW_UNIT: [
                CallbackQueryHandler(admin_raw_save, pattern="^admin_raw_unit_")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern="^admin_raw_materials$"),
            CommandHandler("cancel", admin_cancel)
        ],
        name="admin_raw_conversation",
        persistent=False
    )
    application.add_handler(admin_raw_conv)
    
    # ДОБАВЛЕНИЕ ПОЛУФАБРИКАТА
    admin_semi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_semi_add_start, pattern="^admin_semi_add$")],
        states={
            ADMIN_SEMI_CATEGORY: [
                CallbackQueryHandler(admin_semi_category_selected, pattern="^admin_semi_cat_")
            ],
            ADMIN_SEMI_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_semi_name_entered)
            ],
            ADMIN_SEMI_UNIT: [
                CallbackQueryHandler(admin_semi_save, pattern="^admin_semi_unit_")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern="^admin_semi_products$"),
            CommandHandler("cancel", admin_cancel)
        ],
        name="admin_semi_conversation",
        persistent=False
    )
    application.add_handler(admin_semi_conv)
    
    # ДОБАВЛЕНИЕ ГОТОВОЙ ПРОДУКЦИИ
    admin_finished_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_finished_add_start, pattern="^admin_finished_add$")],
        states={
            ADMIN_FINISHED_CATEGORY: [
                CallbackQueryHandler(admin_finished_category_selected, pattern="^admin_fin_cat_")
            ],
            ADMIN_FINISHED_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_finished_name_entered)
            ],
            ADMIN_FINISHED_PACKAGE_TYPE: [
                CallbackQueryHandler(admin_finished_package_type_selected, pattern="^admin_fin_pkg_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_finished_package_type_custom)
            ],
            ADMIN_FINISHED_PACKAGE_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_finished_save)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern="^admin_finished_products$"),
            CommandHandler("cancel", admin_cancel)
        ],
        name="admin_finished_conversation",
        persistent=False
    )
    application.add_handler(admin_finished_conv)
    
    # СОЗДАНИЕ РЕЦЕПТА
    admin_recipe_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_recipe_add_start, pattern="^admin_recipe_add$")],
        states={
            RECIPE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recipe_name_entered)
            ],
            RECIPE_SEMI: [
                CallbackQueryHandler(admin_recipe_semi_selected, pattern="^admin_recipe_semi_")
            ],
            RECIPE_YIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recipe_yield_entered)
            ],
            RECIPE_COMPONENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_recipe_save)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_recipe_cancel, pattern="^admin_recipes$"),
            CommandHandler("cancel", admin_recipe_cancel)
        ],
        name="admin_recipe_conversation",
        persistent=False
    )
    application.add_handler(admin_recipe_conv)
    
    logger.info("✅ Все обработчики добавлены")
    logger.info(f"Всего handlers: {len(application.handlers[0])}")
    
    return application


__all__ = ["build_application"]
