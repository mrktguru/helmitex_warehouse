"""
Клавиатуры для Telegram бота Helmitex Warehouse (aiogram 3.x).

Все инлайн-клавиатуры для навигации и выбора опций.
Централизованное управление UI элементами.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

def get_main_menu_keyboard(user=None) -> InlineKeyboardMarkup:
    """
    Главное меню с учетом прав пользователя.
    
    Args:
        user: Объект User из БД (с правами доступа)
        
    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    buttons = []
    
    if user:
        # Операционные кнопки
        if user.can_receive_materials:
            buttons.append([InlineKeyboardButton(
                text="📥 Приемка сырья",
                callback_data="arrival_start"
            )])
        
        if user.can_produce:
            buttons.append([InlineKeyboardButton(
                text="🏭 Производство",
                callback_data="production_start"
            )])
        
        if user.can_pack:
            buttons.append([InlineKeyboardButton(
                text="📦 Фасовка",
                callback_data="packing_start"
            )])
        
        if user.can_ship:
            buttons.append([InlineKeyboardButton(
                text="🚚 Отгрузка",
                callback_data="shipment_start"
            )])
        
        # Информационные кнопки (доступны всем)
        buttons.append([InlineKeyboardButton(
            text="📊 Остатки",
            callback_data="stock_start"
        )])
        
        buttons.append([InlineKeyboardButton(
            text="📜 История",
            callback_data="history_start"
        )])
        
        # Административная кнопка
        if user.is_admin:
            buttons.append([InlineKeyboardButton(
                text="👨‍💼 Администрирование",
                callback_data="admin_start"
            )])
        
        # Справка
        buttons.append([InlineKeyboardButton(
            text="❓ Справка",
            callback_data="help"
        )])
    else:
        # Меню для незарегистрированного пользователя
        buttons.append([InlineKeyboardButton(
            text="📖 Справка",
            callback_data="help"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ОБЩИЕ КЛАВИАТУРЫ
# ============================================================================

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Универсальная кнопка "Отмена"."""
    keyboard = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(
    confirm_callback: str = "confirm",
    cancel_callback: str = "cancel"
) -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура подтверждения.
    
    Args:
        confirm_callback: callback_data для кнопки подтверждения
        cancel_callback: callback_data для кнопки отмены
        
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_callback),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_keyboard(
    callback_data: str = "main_menu",
    text: str = "🔙 Назад"
) -> InlineKeyboardMarkup:
    """
    Универсальная кнопка "Назад".
    
    Args:
        callback_data: callback_data для кнопки
        text: Текст кнопки
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой назад
    """
    keyboard = [
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================================
# СКЛАДЫ
# ============================================================================

def get_warehouses_keyboard(
    warehouses: List,
    callback_prefix: str = "warehouse",
    show_status: bool = True
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора склада.
    
    Args:
        warehouses: Список объектов Warehouse
        callback_prefix: Префикс для callback_data
        show_status: Показывать ли статус склада
        
    Returns:
        InlineKeyboardMarkup: Клавиатура со складами
    """
    buttons = []
    
    for warehouse in warehouses:
        text = warehouse.name
        if show_status:
            status = "✅" if warehouse.is_active else "🔒"
            text = f"{status} {text}"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{warehouse.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# НОМЕНКЛАТУРА (SKU)
# ============================================================================

def get_sku_keyboard(
    skus: List,
    callback_prefix: str = "sku",
    show_stock: bool = False,
    warehouse_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора SKU.
    
    Args:
        skus: Список объектов SKU
        callback_prefix: Префикс для callback_data
        show_stock: Показывать ли остатки
        warehouse_id: ID склада для показа остатков
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с SKU
    """
    buttons = []
    
    for sku in skus:
        text = sku.name
        
        if show_stock and hasattr(sku, 'stock') and sku.stock:
            # Если есть информация об остатках
            stock_qty = 0
            if warehouse_id:
                # Фильтруем по складу
                for stock in sku.stock:
                    if stock.warehouse_id == warehouse_id:
                        stock_qty = stock.quantity
                        break
            else:
                # Общий остаток
                stock_qty = sum(s.quantity for s in sku.stock)
            
            text += f" ({stock_qty} {sku.unit})"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{sku.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# РЕЦЕПТЫ
# ============================================================================

def get_recipes_keyboard(
    recipes: List,
    callback_prefix: str = "recipe",
    show_status: bool = False
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора технологической карты.
    
    Args:
        recipes: Список объектов TechnologicalCard
        callback_prefix: Префикс для callback_data
        show_status: Показывать ли статус рецепта
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с рецептами
    """
    buttons = []
    
    for recipe in recipes:
        text = f"📋 {recipe.name}"
        
        if show_status:
            status_emoji = {
                'draft': '📝',
                'active': '✅',
                'archived': '📦'
            }
            text += f" {status_emoji.get(recipe.status.value, '')}"
        else:
            text += f" (выход: {recipe.yield_percent}%)"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{recipe.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ПОЛУЧАТЕЛИ
# ============================================================================

def get_recipients_keyboard(
    recipients: List,
    callback_prefix: str = "recipient",
    show_contact: bool = False
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора получателя (клиента).
    
    Args:
        recipients: Список объектов Recipient
        callback_prefix: Префикс для callback_data
        show_contact: Показывать ли контактную информацию
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с получателями
    """
    buttons = []
    
    for recipient in recipients:
        text = f"👤 {recipient.name}"
        
        if show_contact and recipient.contact_info:
            # Обрезаем длинный контакт
            contact = recipient.contact_info[:20] + "..." if len(recipient.contact_info) > 20 else recipient.contact_info
            text += f" ({contact})"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{recipient.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ВАРИАНТЫ УПАКОВКИ
# ============================================================================

def get_packing_variants_keyboard(
    variants: List,
    callback_prefix: str = "packing_variant"
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора варианта упаковки.
    
    Args:
        variants: Список объектов PackingVariant
        callback_prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами упаковки
    """
    buttons = []
    
    for variant in variants:
        container_emoji = {
            'bucket': '🪣',
            'can': '🥫',
            'bag': '👜',
            'bottle': '🍾',
            'other': '📦'
        }
        
        emoji = container_emoji.get(variant.container_type.value, '📦')
        text = f"{emoji} {variant.finished_product.name} ({variant.weight_per_unit} кг)"
        
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{variant.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# КАТЕГОРИИ СЫРЬЯ
# ============================================================================

def get_category_keyboard(callback_prefix: str = "category") -> InlineKeyboardMarkup:
    """
    Клавиатура выбора категории сырья.
    
    Args:
        callback_prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с категориями
    """
    buttons = [
        [InlineKeyboardButton(text="🌾 Загустители", callback_data=f"{callback_prefix}_thickeners")],
        [InlineKeyboardButton(text="🎨 Красители", callback_data=f"{callback_prefix}_colorants")],
        [InlineKeyboardButton(text="🌸 Отдушки", callback_data=f"{callback_prefix}_fragrances")],
        [InlineKeyboardButton(text="🧪 Основы", callback_data=f"{callback_prefix}_bases")],
        [InlineKeyboardButton(text="➕ Добавки", callback_data=f"{callback_prefix}_additives")],
        [InlineKeyboardButton(text="📦 Упаковка", callback_data=f"{callback_prefix}_packaging")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ЕДИНИЦЫ ИЗМЕРЕНИЯ
# ============================================================================

def get_unit_keyboard(callback_prefix: str = "unit") -> InlineKeyboardMarkup:
    """
    Клавиатура выбора единицы измерения.
    
    Args:
        callback_prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с единицами измерения
    """
    buttons = [
        [InlineKeyboardButton(text="кг (килограммы)", callback_data=f"{callback_prefix}_kg")],
        [InlineKeyboardButton(text="л (литры)", callback_data=f"{callback_prefix}_liters")],
        [InlineKeyboardButton(text="г (граммы)", callback_data=f"{callback_prefix}_grams")],
        [InlineKeyboardButton(text="шт (штуки)", callback_data=f"{callback_prefix}_pieces")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ТИПЫ ТАРЫ
# ============================================================================

def get_container_type_keyboard(callback_prefix: str = "container") -> InlineKeyboardMarkup:
    """
    Клавиатура выбора типа тары.
    
    Args:
        callback_prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с типами тары
    """
    buttons = [
        [InlineKeyboardButton(text="🪣 Ведро", callback_data=f"{callback_prefix}_bucket")],
        [InlineKeyboardButton(text="🥫 Банка", callback_data=f"{callback_prefix}_can")],
        [InlineKeyboardButton(text="👜 Мешок", callback_data=f"{callback_prefix}_bag")],
        [InlineKeyboardButton(text="🍾 Бутылка", callback_data=f"{callback_prefix}_bottle")],
        [InlineKeyboardButton(text="📦 Другое", callback_data=f"{callback_prefix}_other")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ЭКСПОРТ
# ============================================================================

__all__ = [
    'get_main_menu_keyboard',
    'get_cancel_keyboard',
    'get_confirmation_keyboard',
    'get_back_keyboard',
    'get_warehouses_keyboard',
    'get_sku_keyboard',
    'get_recipes_keyboard',
    'get_recipients_keyboard',
    'get_packing_variants_keyboard',
    'get_category_keyboard',
    'get_unit_keyboard',
    'get_container_type_keyboard',
]
