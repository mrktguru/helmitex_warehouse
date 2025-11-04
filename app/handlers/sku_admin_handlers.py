"""
Администрирование номенклатуры.

Состояния ConversationHandler для создания SKU:
- SELECT_SKU_TYPE: Выбор типа (сырье/полуфабрикат/готовая продукция)
- SELECT_CATEGORY: Выбор категории (для сырья)
- INPUT_CODE: Ввод кода
- INPUT_NAME: Ввод названия
- SELECT_UNIT: Выбор единицы измерения
- INPUT_MIN_STOCK: Ввод минимального остатка
- CONFIRM_SKU: Подтверждение

Функции:
- admin_sku_menu()
- admin_raw_materials_callback()
- admin_semi_products_callback()
- admin_finished_products_callback()
- admin_add_sku_start()
- [состояния создания SKU]
- admin_edit_sku()
- admin_delete_sku()
"""
