"""
Клавиатуры для Telegram бота Helmitex Warehouse.

Все инлайн-клавиатуры для навигации и выбора опций.
Централизованное управление UI элементами.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional
from app.config import OWNER_TELEGRAM_ID


# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Главное меню с учетом прав пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    keyboard = [
        [
            InlineKeyboardButton("📥 Приход сырья", callback_data="arrival_menu"),
            InlineKeyboardButton("⚙️ Производство", callback_data="production_menu")
        ],
        [
            InlineKeyboardButton("📦 Фасовка", callback_data="packing_menu"),
            InlineKeyboardButton("🚚 Отгрузка", callback_data="shipment_menu")
        ],
        [
            InlineKeyboardButton("📊 Остатки", callback_data="stock_menu"),
            InlineKeyboardButton("📈 История", callback_data="history_menu")
        ]
    ]
    
    # Кнопка администрирования только для владельца
    if user_id == OWNER_TELEGRAM_ID:
        keyboard.append([
            InlineKeyboardButton("⚙️ АДМИНИСТРИРОВАНИЕ", callback_data="admin_menu")
        ])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ПРИХОД СЫРЬЯ
# ============================================================================

def get_arrival_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела прихода сырья."""
    keyboard = [
        [InlineKeyboardButton("➕ Оформить приход", callback_data="arrival_start")],
        [InlineKeyboardButton("📋 История прихода", callback_data="history_arrival")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора категории сырья.
    """
    keyboard = [
        [InlineKeyboardButton("🌾 Загустители", callback_data="category_thickeners")],
        [InlineKeyboardButton("🎨 Красители", callback_data="category_colorants")],
        [InlineKeyboardButton("🌸 Отдушки", callback_data="category_fragrances")],
        [InlineKeyboardButton("🧪 Основы", callback_data="category_bases")],
        [InlineKeyboardButton("➕ Добавки", callback_data="category_additives")],
        [InlineKeyboardButton("📦 Упаковка", callback_data="category_packaging")],
        [InlineKeyboardButton("❌ Отмена", callback_data="arrival_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_raw_materials_keyboard(raw_materials: List, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора сырья с пагинацией.
    
    Args:
        raw_materials: Список объектов SKU (сырье)
        page: Номер страницы (начиная с 0)
        page_size: Количество элементов на странице
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с сырьем
    """
    keyboard = []
    
    # Вычисляем границы страницы
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_items = raw_materials[start_idx:end_idx]
    
    # Кнопки с сырьем
    for material in page_items:
        button_text = f"{material.name}"
        if hasattr(material, 'stock') and material.stock:
            # Если есть информация об остатке
            stock_qty = material.stock[0].quantity if material.stock else 0
            button_text += f" ({stock_qty} {material.unit.value})"
        
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"raw_material_{material.id}")
        ])
    
    # Кнопки пагинации
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"raw_page_{page-1}"))
    if end_idx < len(raw_materials):
        pagination_row.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"raw_page_{page+1}"))
    
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Кнопки управления
    keyboard.append([InlineKeyboardButton("➕ Добавить новое сырье", callback_data="admin_add_raw_material")])
    keyboard.append([InlineKeyboardButton("🔙 К категориям", callback_data="arrival_select_category")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="arrival_menu")])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ПРОИЗВОДСТВО
# ============================================================================

def get_production_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела производства."""
    keyboard = [
        [InlineKeyboardButton("⚙️ Начать замес", callback_data="production_start")],
        [InlineKeyboardButton("📋 История производства", callback_data="history_production")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_recipes_keyboard(recipes: List, show_status: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора технологической карты.
    
    Args:
        recipes: Список объектов TechnologicalCard
        show_status: Показывать ли статус рецепта
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с рецептами
    """
    keyboard = []
    
    for recipe in recipes:
        button_text = f"📋 {recipe.name}"
        if show_status:
            status_emoji = {
                'draft': '📝',
                'active': '✅',
                'archived': '📦'
            }
            button_text += f" {status_emoji.get(recipe.status.value, '')}"
        else:
            button_text += f" (выход: {recipe.yield_percent}%)"
        
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"recipe_{recipe.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="production_menu")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_production_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения производства."""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и начать", callback_data="production_confirm")],
        [InlineKeyboardButton("✏️ Изменить вес", callback_data="production_change_weight")],
        [InlineKeyboardButton("🔄 Пересчитать", callback_data="production_recalculate")],
        [InlineKeyboardButton("❌ Отмена", callback_data="production_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ФАСОВКА
# ============================================================================

def get_packing_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела фасовки."""
    keyboard = [
        [InlineKeyboardButton("📦 Начать фасовку", callback_data="packing_start")],
        [InlineKeyboardButton("📋 История фасовки", callback_data="history_packing")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_semi_products_keyboard(semi_products: List) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора полуфабриката для фасовки.
    
    Args:
        semi_products: Список объектов SKU (type='semi')
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с полуфабрикатами
    """
    keyboard = []
    
    for semi in semi_products:
        # Получаем общий остаток полуфабриката
        total_weight = 0
        if hasattr(semi, 'stock') and semi.stock:
            total_weight = semi.stock[0].quantity if semi.stock else 0
        
        button_text = f"⚙️ {semi.name} ({total_weight} {semi.unit.value})"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"semi_product_{semi.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="packing_menu")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_finished_products_keyboard(finished_products: List, semi_product_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора готовой продукции для фасовки.
    
    Args:
        finished_products: Список объектов SKU (type='finished')
        semi_product_id: ID выбранного полуфабриката
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с готовой продукцией
    """
    keyboard = []
    
    for product in finished_products:
        button_text = f"📦 {product.name}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"finished_product_{product.id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Создать новую упаковку", callback_data=f"create_packing_variant_{semi_product_id}")
    ])
    keyboard.append([InlineKeyboardButton("🔙 К выбору полуфабриката", callback_data="packing_start")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="packing_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_packing_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения фасовки."""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить фасовку", callback_data="packing_confirm")],
        [InlineKeyboardButton("✏️ Изменить количество", callback_data="packing_change_quantity")],
        [InlineKeyboardButton("❌ Отмена", callback_data="packing_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ОТГРУЗКА
# ============================================================================

def get_shipment_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела отгрузки."""
    keyboard = [
        [InlineKeyboardButton("🚚 Оформить отгрузку", callback_data="shipment_start")],
        [InlineKeyboardButton("📋 История отгрузок", callback_data="history_shipment")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_finished_products_for_shipment_keyboard(finished_products: List) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора готовой продукции для отгрузки.
    
    Args:
        finished_products: Список объектов SKU с остатками
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с готовой продукцией
    """
    keyboard = []
    
    for product in finished_products:
        stock_qty = 0
        if hasattr(product, 'stock') and product.stock:
            stock_qty = product.stock[0].quantity if product.stock else 0
        
        button_text = f"📦 {product.name} ({stock_qty} {product.unit.value})"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"shipment_product_{product.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="shipment_menu")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_shipment_recipient_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора получателя (опционально)."""
    keyboard = [
        [InlineKeyboardButton("✏️ Ввести получателя", callback_data="shipment_enter_recipient")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="shipment_skip_recipient")],
        [InlineKeyboardButton("❌ Отмена", callback_data="shipment_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_shipment_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отгрузки."""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить отгрузку", callback_data="shipment_confirm")],
        [InlineKeyboardButton("✏️ Изменить количество", callback_data="shipment_change_quantity")],
        [InlineKeyboardButton("👤 Изменить получателя", callback_data="shipment_change_recipient")],
        [InlineKeyboardButton("❌ Отмена", callback_data="shipment_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ОСТАТКИ
# ============================================================================

def get_stock_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню просмотра остатков."""
    keyboard = [
        [InlineKeyboardButton("🌾 Сырье", callback_data="stock_raw")],
        [InlineKeyboardButton("⚙️ Полуфабрикаты", callback_data="stock_semi")],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data="stock_finished")],
        [
            InlineKeyboardButton("⚠️ Низкие остатки", callback_data="stock_low"),
            InlineKeyboardButton("📊 Все товары", callback_data="stock_all")
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_stock_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура фильтра по категориям сырья."""
    keyboard = [
        [InlineKeyboardButton("🌾 Загустители", callback_data="stock_category_thickeners")],
        [InlineKeyboardButton("🎨 Красители", callback_data="stock_category_colorants")],
        [InlineKeyboardButton("🌸 Отдушки", callback_data="stock_category_fragrances")],
        [InlineKeyboardButton("🧪 Основы", callback_data="stock_category_bases")],
        [InlineKeyboardButton("➕ Добавки", callback_data="stock_category_additives")],
        [InlineKeyboardButton("📦 Упаковка", callback_data="stock_category_packaging")],
        [InlineKeyboardButton("📊 Все сырье", callback_data="stock_raw")],
        [InlineKeyboardButton("🔙 К остаткам", callback_data="stock_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ИСТОРИЯ
# ============================================================================

def get_history_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню истории операций."""
    keyboard = [
        [InlineKeyboardButton("📥 Приход сырья", callback_data="history_arrival")],
        [InlineKeyboardButton("⚙️ Производство", callback_data="history_production")],
        [InlineKeyboardButton("📦 Фасовка", callback_data="history_packing")],
        [InlineKeyboardButton("🚚 Отгрузка", callback_data="history_shipment")],
        [InlineKeyboardButton("📊 Все операции", callback_data="history_all")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_history_detail_keyboard(movement_id: int, back_type: str = "all") -> InlineKeyboardMarkup:
    """
    Клавиатура детального просмотра операции.
    
    Args:
        movement_id: ID движения
        back_type: Тип истории для кнопки "Назад"
        
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    keyboard = [
        [InlineKeyboardButton("🔙 К списку", callback_data=f"history_{back_type}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# АДМИНИСТРИРОВАНИЕ
# ============================================================================

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню администратора."""
    keyboard = [
        [
            InlineKeyboardButton("📦 Номенклатура", callback_data="admin_sku_menu"),
            InlineKeyboardButton("📋 Технологические карты", callback_data="admin_recipes_menu")
        ],
        [
            InlineKeyboardButton("🏢 Склады", callback_data="admin_warehouses_menu"),
            InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_menu")
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_sku_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления номенклатурой."""
    keyboard = [
        [InlineKeyboardButton("🌾 Сырье", callback_data="admin_raw_materials")],
        [InlineKeyboardButton("⚙️ Полуфабрикаты", callback_data="admin_semi_products")],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data="admin_finished_products")],
        [InlineKeyboardButton("➕ Добавить SKU", callback_data="admin_add_sku_start")],
        [InlineKeyboardButton("🔙 К администрированию", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_recipes_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления технологическими картами."""
    keyboard = [
        [InlineKeyboardButton("✅ Активные ТК", callback_data="admin_recipes_active")],
        [InlineKeyboardButton("📝 Черновики", callback_data="admin_recipes_drafts")],
        [InlineKeyboardButton("📦 Архив", callback_data="admin_recipes_archived")],
        [InlineKeyboardButton("➕ Создать ТК", callback_data="admin_recipe_create_start")],
        [InlineKeyboardButton("🔙 К администрированию", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_recipe_actions_keyboard(recipe_id: int, status: str) -> InlineKeyboardMarkup:
    """
    Клавиатура действий с технологической картой.
    
    Args:
        recipe_id: ID рецепта
        status: Статус рецепта ('draft', 'active', 'archived')
        
    Returns:
        InlineKeyboardMarkup: Клавиатура действий
    """
    keyboard = []
    
    if status == 'draft':
        keyboard.append([InlineKeyboardButton("✅ Активировать", callback_data=f"admin_recipe_activate_{recipe_id}")])
    elif status == 'active':
        keyboard.append([InlineKeyboardButton("📦 Архивировать", callback_data=f"admin_recipe_archive_{recipe_id}")])
    elif status == 'archived':
        keyboard.append([InlineKeyboardButton("🔄 Восстановить", callback_data=f"admin_recipe_activate_{recipe_id}")])
    
    keyboard.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"admin_recipe_edit_{recipe_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К списку ТК", callback_data="admin_recipes_menu")])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ОБЩИЕ КЛАВИАТУРЫ
# ============================================================================

def get_confirmation_keyboard(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура подтверждения.
    
    Args:
        confirm_data: callback_data для кнопки подтверждения
        cancel_data: callback_data для кнопки отмены
        
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton("❌ Отмена", callback_data=cancel_data)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_button(callback_data: str = "main_menu", text: str = "🔙 Назад") -> InlineKeyboardMarkup:
    """
    Универсальная кнопка "Назад".
    
    Args:
        callback_data: callback_data для кнопки
        text: Текст кнопки
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой назад
    """
    keyboard = [[InlineKeyboardButton(text, callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_button(callback_data: str = "cancel") -> InlineKeyboardMarkup:
    """
    Универсальная кнопка "Отмена".
    
    Args:
        callback_data: callback_data для кнопки
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой отмены
    """
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def get_back_and_cancel_keyboard(back_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопками "Назад" и "Отмена".
    
    Args:
        back_data: callback_data для кнопки "Назад"
        cancel_data: callback_data для кнопки "Отмена"
        
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    keyboard = [
        [
            InlineKeyboardButton("🔙 Назад", callback_data=back_data),
            InlineKeyboardButton("❌ Отмена", callback_data=cancel_data)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_unit_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора единицы измерения."""
    keyboard = [
        [InlineKeyboardButton("кг (килограммы)", callback_data="unit_kg")],
        [InlineKeyboardButton("л (литры)", callback_data="unit_liters")],
        [InlineKeyboardButton("г (граммы)", callback_data="unit_grams")],
        [InlineKeyboardButton("шт (штуки)", callback_data="unit_pieces")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_sku_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_container_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа тары."""
    keyboard = [
        [InlineKeyboardButton("🪣 Ведро", callback_data="container_bucket")],
        [InlineKeyboardButton("🥫 Банка", callback_data="container_can")],
        [InlineKeyboardButton("👜 Мешок", callback_data="container_bag")],
        [InlineKeyboardButton("🍾 Бутылка", callback_data="container_bottle")],
        [InlineKeyboardButton("📦 Другое", callback_data="container_other")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)
