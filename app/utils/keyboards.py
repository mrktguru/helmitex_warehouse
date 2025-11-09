from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Optional
from app.models import Warehouse, SKU, Barrel, PackingVariant


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Создает главное меню бота.
    
    Args:
        is_admin: Флаг администратора для отображения дополнительных кнопок
        
    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    builder = ReplyKeyboardBuilder()
    
    # Основные кнопки для всех пользователей
    builder.row(
        KeyboardButton(text="📊 Остатки"),
        KeyboardButton(text="📦 Движения")
    )
    builder.row(
        KeyboardButton(text="🏭 Производство"),
        KeyboardButton(text="📋 Заказы")
    )
    builder.row(
        KeyboardButton(text="🚚 Отгрузки"),
        KeyboardButton(text="📦 Фасовка")
    )
    
    # Дополнительные кнопки для администраторов
    if is_admin:
        builder.row(
            KeyboardButton(text="⚙️ Управление"),
            KeyboardButton(text="📈 Отчеты")
        )
    
    return builder.as_markup(resize_keyboard=True)


def get_warehouses_keyboard(warehouses: List[Warehouse]) -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру со списком складов.
    
    Args:
        warehouses: Список объектов Warehouse
        
    Returns:
        InlineKeyboardMarkup: Клавиатура со складами
    """
    builder = InlineKeyboardBuilder()
    
    for warehouse in warehouses:
        builder.row(
            InlineKeyboardButton(
                text=f"📍 {warehouse.name}",
                callback_data=f"warehouse_{warehouse.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_sku_keyboard(skus: List[SKU], prefix: str = "sku") -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру со списком SKU.
    
    Args:
        skus: Список объектов SKU
        prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с SKU
    """
    builder = InlineKeyboardBuilder()
    
    for sku in skus:
        builder.row(
            InlineKeyboardButton(
                text=f"{sku.name} ({sku.unit})",
                callback_data=f"{prefix}_{sku.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру подтверждения действия.
    
    Args:
        action: Действие для подтверждения
        item_id: ID объекта
        
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_{action}_{item_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"cancel_{action}_{item_id}"
        )
    )
    
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены.
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой "Отмена"
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_movement_type_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора типа движения.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с типами движений
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📥 Приход", callback_data="movement_type_receipt"),
        InlineKeyboardButton(text="📤 Расход", callback_data="movement_type_issue")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Перемещение", callback_data="movement_type_transfer")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_production_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню производства.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура меню производства
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📝 Создать партию",
            callback_data="production_create_batch"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Список партий",
            callback_data="production_list_batches"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Техкарты",
            callback_data="production_tech_cards"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_orders_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню заказов.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура меню заказов
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="➕ Создать заказ",
            callback_data="order_create"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Активные заказы",
            callback_data="order_list_active"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Завершенные заказы",
            callback_data="order_list_completed"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_shipment_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню отгрузок.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура меню отгрузок
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🚚 Создать отгрузку",
            callback_data="shipment_create"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Список отгрузок",
            callback_data="shipment_list"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📦 Получатели",
            callback_data="shipment_recipients"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_management_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру меню управления (для администраторов).
    
    Returns:
        InlineKeyboardMarkup: Клавиатура меню управления
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🏢 Склады",
            callback_data="manage_warehouses"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📦 Номенклатура",
            callback_data="manage_sku"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Пользователи",
            callback_data="manage_users"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🛢️ Бочки",
            callback_data="manage_barrels"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру пагинации.
    
    Args:
        current_page: Текущая страница (начинается с 1)
        total_pages: Общее количество страниц
        prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура пагинации
    """
    builder = InlineKeyboardBuilder()
    
    buttons = []
    
    # Кнопка "Назад"
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"{prefix}_page_{current_page - 1}"
            )
        )
    
    # Информация о текущей странице
    buttons.append(
        InlineKeyboardButton(
            text=f"📄 {current_page}/{total_pages}",
            callback_data="page_info"
        )
    )
    
    # Кнопка "Вперед"
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="Вперед ▶️",
                callback_data=f"{prefix}_page_{current_page + 1}"
            )
        )
    
    builder.row(*buttons)
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


def get_packing_variants_keyboard(
    variants: List[PackingVariant],
    prefix: str = "packing_variant"
) -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру со списком вариантов фасовки.
    
    Args:
        variants: Список объектов PackingVariant
        prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами фасовки
    """
    builder = InlineKeyboardBuilder()
    
    for variant in variants:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {variant.name} ({variant.volume_kg} кг)",
                callback_data=f"{prefix}_{variant.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_packing_menu")
    )
    
    return builder.as_markup()


def get_barrels_keyboard(
    barrels: List[Barrel],
    page: int = 1,
    per_page: int = 5,
    prefix: str = "barrel"
) -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру со списком бочек с пагинацией.
    
    Args:
        barrels: Список объектов Barrel
        page: Текущая страница (начинается с 1)
        per_page: Количество элементов на странице
        prefix: Префикс для callback_data
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с бочками и пагинацией
    """
    builder = InlineKeyboardBuilder()
    
    # Вычисляем общее количество страниц
    total_pages = (len(barrels) + per_page - 1) // per_page
    
    # Вычисляем индексы для текущей страницы
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, len(barrels))
    
    # Добавляем кнопки для бочек на текущей странице
    for barrel in barrels[start_idx:end_idx]:
        # Формируем текст кнопки с информацией о бочке
        button_text = f"🛢️ {barrel.number}"
        
        # Добавляем информацию о SKU, если есть
        if hasattr(barrel, 'sku') and barrel.sku:
            button_text += f" - {barrel.sku.name}"
        
        # Добавляем информацию о весе, если есть
        if barrel.current_weight_kg:
            button_text += f" ({barrel.current_weight_kg} кг)"
        
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"{prefix}_{barrel.id}"
            )
        )
    
    # Добавляем кнопки пагинации, если страниц больше одной
    if total_pages > 1:
        pagination_buttons = []
        
        # Кнопка "Назад"
        if page > 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"{prefix}_page_{page - 1}"
                )
            )
        
        # Информация о текущей странице
        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page}/{total_pages}",
                callback_data="page_info"
            )
        )
        
        # Кнопка "Вперед"
        if page < total_pages:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ▶️",
                    callback_data=f"{prefix}_page_{page + 1}"
                )
            )
        
        builder.row(*pagination_buttons)
    
    # Кнопка "Назад в меню"
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    )
    
    return builder.as_markup()


__all__ = [
    'get_main_menu_keyboard',
    'get_warehouses_keyboard',
    'get_sku_keyboard',
    'get_confirmation_keyboard',
    'get_cancel_keyboard',
    'get_movement_type_keyboard',
    'get_production_keyboard',
    'get_orders_keyboard',
    'get_shipment_keyboard',
    'get_management_keyboard',
    'get_pagination_keyboard',
    'get_packing_variants_keyboard',
    'get_barrels_keyboard',
]
