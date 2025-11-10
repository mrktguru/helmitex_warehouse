"""
Административный обработчик управления складами и номенклатурой.

Этот модуль реализует функциональность для:
- Управления складами (создание, редактирование, активация)
- Управления номенклатурой (SKU всех типов)
- Управления технологическими картами (рецептами)
- Управления вариантами упаковки

Конвертировано на aiogram 3.x с использованием FSM (StatesGroup).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from app.database.models import User, SKUType, WasteType
from app.services import (
    warehouse_service,
    stock_service,
    recipe_service,
    packing_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_sku_keyboard,
    get_recipes_keyboard,
    get_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import (
    validate_positive_decimal,
    validate_positive_integer,
    validate_text_length,
    parse_decimal_input,
    parse_integer_input
)


# ============================================================================
# FSM СОСТОЯНИЯ
# ============================================================================

class AdminWarehouseStates(StatesGroup):
    """Состояния FSM для административной панели складов."""
    # Главное меню
    admin_menu = State()
    
    # Управление складами
    warehouse_menu = State()
    create_warehouse_name = State()
    create_warehouse_address = State()
    create_warehouse_desc = State()
    confirm_create_warehouse = State()
    select_warehouse_edit = State()
    edit_warehouse_menu = State()
    
    # Управление SKU
    sku_menu = State()
    select_sku_type_create = State()
    create_sku_name = State()
    create_sku_unit = State()
    create_sku_desc = State()
    confirm_create_sku = State()
    select_sku_type_list = State()
    select_sku_edit = State()
    edit_sku_menu = State()
    
    # Управление рецептами
    recipe_menu = State()
    create_recipe_name = State()
    create_recipe_semi_sku = State()
    create_recipe_output = State()
    create_recipe_batch_size = State()
    create_recipe_desc = State()
    add_component_select_raw = State()
    add_component_percentage = State()
    review_recipe_components = State()
    confirm_create_recipe = State()
    select_recipe_edit = State()
    
    # Управление вариантами упаковки
    packing_variant_menu = State()
    create_variant_semi = State()
    create_variant_finished = State()
    create_variant_weight = State()
    confirm_create_variant = State()


# ============================================================================
# РОУТЕР
# ============================================================================

router = Router(name='admin_warehouse')


# ============================================================================
# ГЛАВНОЕ АДМИНИСТРАТИВНОЕ МЕНЮ
# ============================================================================

@router.message(Command('admin'))
@router.callback_query(F.data == 'admin_start')
async def start_admin(
    event: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает административную сессию.
    
    Команда: /admin
    """
    # Определение типа события
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        user_id = event.from_user.id
    else:
        message = event
        user_id = event.from_user.id
    
    # Получение пользователя
    user = await session.get(User, user_id)
    
    if not user:
        await message.answer(
            "❌ Пользователь не найден. Используйте /start для регистрации."
        )
        await state.clear()
        return
    
    # Проверка административных прав
    if not user.is_admin:
        await message.answer(
            "❌ У вас нет административных прав.\n"
            "Обратитесь к администратору системы."
        )
        await state.clear()
        return
    
    # Инициализация данных
    await state.update_data(
        user_id=user_id,
        started_at=datetime.utcnow().isoformat()
    )
    
    # Главное меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏭 Склады", callback_data='admin_warehouses')],
        [InlineKeyboardButton(text="📋 Номенклатура (SKU)", callback_data='admin_sku')],
        [InlineKeyboardButton(text="🧪 Технологические карты", callback_data='admin_recipes')],
        [InlineKeyboardButton(text="📦 Варианты упаковки", callback_data='admin_packing_variants')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "👨‍💼 <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:"
    )
    
    if isinstance(event, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    
    await state.set_state(AdminWarehouseStates.admin_menu)


# ============================================================================
# УПРАВЛЕНИЕ СКЛАДАМИ
# ============================================================================

@router.callback_query(AdminWarehouseStates.admin_menu, F.data == 'admin_warehouses')
async def warehouse_menu(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню управления складами.
    """
    await query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать склад", callback_data='wh_create')],
        [InlineKeyboardButton(text="📋 Список складов", callback_data='wh_list')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "🏭 <b>Управление складами</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.warehouse_menu)


@router.callback_query(AdminWarehouseStates.warehouse_menu, F.data == 'wh_create')
async def create_warehouse_start(query: CallbackQuery, state: FSMContext) -> None:
    """
    Начинает процесс создания склада.
    """
    await query.answer()
    
    # Инициализация данных склада
    await state.update_data(warehouse={})
    
    text = (
        "➕ <b>Создание склада</b>\n\n"
        "📝 Введите название склада:\n\n"
        "<i>Примеры: Основной склад, Склад №2, Производственный</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_warehouse_name)


@router.message(AdminWarehouseStates.create_warehouse_name, F.text)
async def create_warehouse_name(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод названия склада.
    """
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение названия
    data = await state.get_data()
    warehouse = data.get('warehouse', {})
    warehouse['name'] = user_input
    await state.update_data(warehouse=warehouse)
    
    text = (
        f"✅ Название: <b>{user_input}</b>\n\n"
        "📍 Введите адрес склада (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_warehouse_address)


@router.message(AdminWarehouseStates.create_warehouse_address, F.text)
async def create_warehouse_address(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод адреса склада.
    """
    user_input = message.text.strip()
    
    # Получение текущих данных
    data = await state.get_data()
    warehouse = data.get('warehouse', {})
    
    # Проверка на пропуск
    if user_input == '-':
        warehouse['address'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=200)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        warehouse['address'] = user_input
    
    await state.update_data(warehouse=warehouse)
    
    text = (
        "📝 Введите описание склада (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_warehouse_desc)


@router.message(AdminWarehouseStates.create_warehouse_desc, F.text)
async def create_warehouse_desc(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод описания и показывает подтверждение.
    """
    user_input = message.text.strip()
    
    # Получение текущих данных
    data = await state.get_data()
    warehouse = data.get('warehouse', {})
    
    # Проверка на пропуск
    if user_input == '-':
        warehouse['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        warehouse['description'] = user_input
    
    await state.update_data(warehouse=warehouse)
    
    # Формирование сводки
    summary = (
        "📋 <b>Подтверждение создания склада</b>\n\n"
        f"🏭 <b>Название:</b> {warehouse['name']}\n"
    )
    
    if warehouse.get('address'):
        summary += f"📍 <b>Адрес:</b> {warehouse['address']}\n"
    
    if warehouse.get('description'):
        summary += f"📝 <b>Описание:</b> {warehouse['description']}\n"
    
    summary += "\n❓ Создать склад?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='wh_confirm_create',
            cancel_callback='wh_cancel'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.confirm_create_warehouse)


@router.callback_query(AdminWarehouseStates.confirm_create_warehouse, F.data == 'wh_confirm_create')
async def confirm_create_warehouse(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Создает склад в базе данных.
    """
    await query.answer("⏳ Создание склада...")
    
    data = await state.get_data()
    warehouse_data = data.get('warehouse', {})
    
    try:
        # Создание склада через сервис
        warehouse = await warehouse_service.create_warehouse(
            session=session,
            name=warehouse_data['name'],
            address=warehouse_data.get('address'),
            description=warehouse_data.get('description')
        )
        
        text = (
            "✅ <b>Склад успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {warehouse.id}\n"
            f"🏭 <b>Название:</b> {warehouse.name}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных склада
        await state.update_data(warehouse=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать еще", callback_data='wh_create')],
            [InlineKeyboardButton(text="🔙 К складам", callback_data='admin_warehouses')],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.warehouse_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании склада:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К складам", callback_data='admin_warehouses')]
            ]),
            parse_mode='HTML'
        )
        await state.set_state(AdminWarehouseStates.warehouse_menu)


@router.callback_query(AdminWarehouseStates.warehouse_menu, F.data == 'wh_list')
async def list_warehouses(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список всех складов.
    """
    await query.answer("⏳ Загрузка складов...")
    
    try:
        # Получение всех складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=False)
        
        if not warehouses:
            text = (
                "📋 <b>Список складов</b>\n\n"
                "❌ Нет созданных складов."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать склад", callback_data='wh_create')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_warehouses')]
            ])
        else:
            text = f"📋 <b>Список складов ({len(warehouses)})</b>\n\n"
            
            for wh in warehouses:
                status = "✅ Активен" if wh.is_active else "🔒 Неактивен"
                text += f"🏭 <b>{wh.name}</b> - {status}\n"
                if wh.address:
                    text += f"   📍 {wh.address}\n"
                text += f"   🆔 ID: {wh.id}\n\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Редактировать склад", callback_data='wh_edit_select')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_warehouses')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.warehouse_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_warehouses')]
            ])
        )
        await state.set_state(AdminWarehouseStates.warehouse_menu)


# ============================================================================
# УПРАВЛЕНИЕ НОМЕНКЛАТУРОЙ (SKU)
# ============================================================================

@router.callback_query(AdminWarehouseStates.admin_menu, F.data == 'admin_sku')
async def sku_menu(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню управления номенклатурой.
    """
    await query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить SKU", callback_data='sku_create')],
        [InlineKeyboardButton(text="📋 Список SKU", callback_data='sku_list')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "📋 <b>Управление номенклатурой</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.sku_menu)


@router.callback_query(AdminWarehouseStates.sku_menu, F.data == 'sku_create')
async def create_sku_select_type(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню выбора типа SKU.
    """
    await query.answer()
    
    # Инициализация данных SKU
    await state.update_data(sku={})
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 Сырье", callback_data='sku_type_raw')],
        [InlineKeyboardButton(text="🛢 Полуфабрикат", callback_data='sku_type_semi')],
        [InlineKeyboardButton(text="📦 Готовая продукция", callback_data='sku_type_finished')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_sku')],
        [InlineKeyboardButton(text="❌ Отменить", callback_data='admin_exit')]
    ])
    
    text = (
        "➕ <b>Добавление SKU</b>\n\n"
        "Выберите тип номенклатуры:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.select_sku_type_create)


@router.callback_query(AdminWarehouseStates.select_sku_type_create, F.data.startswith('sku_type_'))
async def create_sku_type_selected(query: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает выбор типа SKU и запрашивает название.
    """
    await query.answer()
    
    # Определение типа
    if query.data == 'sku_type_raw':
        sku_type = SKUType.raw
        type_name = "Сырье"
        type_emoji = "🌾"
    elif query.data == 'sku_type_semi':
        sku_type = SKUType.semi
        type_name = "Полуфабрикат"
        type_emoji = "🛢"
    else:  # finished
        sku_type = SKUType.finished
        type_name = "Готовая продукция"
        type_emoji = "📦"
    
    # Сохранение типа
    data = await state.get_data()
    sku = data.get('sku', {})
    sku['sku_type'] = sku_type.value  # Сохраняем value для FSM
    sku['type_name'] = type_name
    sku['type_emoji'] = type_emoji
    await state.update_data(sku=sku)
    
    text = (
        f"{type_emoji} <b>Добавление: {type_name}</b>\n\n"
        "📝 Введите название:\n\n"
        "<i>Примеры: Титановые белила, Краска белая, Ведро 10кг</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_sku_name)


@router.message(AdminWarehouseStates.create_sku_name, F.text)
async def create_sku_name(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод названия SKU.
    """
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение названия
    data = await state.get_data()
    sku = data.get('sku', {})
    sku['name'] = user_input
    await state.update_data(sku=sku)
    
    text = (
        f"✅ Название: <b>{user_input}</b>\n\n"
        "📏 Введите единицу измерения:\n\n"
        "<i>Примеры: кг, литр, шт, ведро, мешок</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_sku_unit)


@router.message(AdminWarehouseStates.create_sku_unit, F.text)
async def create_sku_unit(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод единицы измерения.
    """
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=1, max_length=20)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение единицы
    data = await state.get_data()
    sku = data.get('sku', {})
    sku['unit'] = user_input
    await state.update_data(sku=sku)
    
    text = (
        f"✅ Единица: <b>{user_input}</b>\n\n"
        "📝 Введите описание (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_sku_desc)


@router.message(AdminWarehouseStates.create_sku_desc, F.text)
async def create_sku_desc(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод описания и показывает подтверждение.
    """
    user_input = message.text.strip()
    
    # Получение текущих данных
    data = await state.get_data()
    sku = data.get('sku', {})
    
    # Проверка на пропуск
    if user_input == '-':
        sku['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        sku['description'] = user_input
    
    await state.update_data(sku=sku)
    
    # Формирование сводки
    summary = (
        "📋 <b>Подтверждение создания SKU</b>\n\n"
        f"{sku['type_emoji']} <b>Тип:</b> {sku['type_name']}\n"
        f"📝 <b>Название:</b> {sku['name']}\n"
        f"📏 <b>Единица:</b> {sku['unit']}\n"
    )
    
    if sku.get('description'):
        summary += f"📝 <b>Описание:</b> {sku['description']}\n"
    
    summary += "\n❓ Создать SKU?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='sku_confirm_create',
            cancel_callback='sku_cancel'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.confirm_create_sku)


@router.callback_query(AdminWarehouseStates.confirm_create_sku, F.data == 'sku_confirm_create')
async def confirm_create_sku(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Создает SKU в базе данных.
    """
    await query.answer("⏳ Создание SKU...")
    
    data = await state.get_data()
    sku_data = data.get('sku', {})
    
    try:
        # Восстановление Enum из value
        sku_type = SKUType(sku_data['sku_type'])
        
        # Создание SKU через сервис
        sku = await stock_service.create_sku(
            session=session,
            name=sku_data['name'],
            sku_type=sku_type,
            unit=sku_data['unit'],
            description=sku_data.get('description')
        )
        
        text = (
            "✅ <b>SKU успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {sku.id}\n"
            f"{sku_data['type_emoji']} <b>Тип:</b> {sku_data['type_name']}\n"
            f"📝 <b>Название:</b> {sku.name}\n"
            f"📏 <b>Единица:</b> {sku.unit}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных SKU
        await state.update_data(sku=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить еще", callback_data='sku_create')],
            [InlineKeyboardButton(text="🔙 К номенклатуре", callback_data='admin_sku')],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.sku_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании SKU:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К номенклатуре", callback_data='admin_sku')]
            ]),
            parse_mode='HTML'
        )
        await state.set_state(AdminWarehouseStates.sku_menu)


@router.callback_query(AdminWarehouseStates.sku_menu, F.data == 'sku_list')
async def list_sku_select_type(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню выбора типа для просмотра списка SKU.
    """
    await query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌾 Сырье", callback_data='sku_list_raw')],
        [InlineKeyboardButton(text="🛢 Полуфабрикаты", callback_data='sku_list_semi')],
        [InlineKeyboardButton(text="📦 Готовая продукция", callback_data='sku_list_finished')],
        [InlineKeyboardButton(text="📋 Все категории", callback_data='sku_list_all')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_sku')]
    ])
    
    text = (
        "📋 <b>Список номенклатуры</b>\n\n"
        "Выберите категорию:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.select_sku_type_list)


@router.callback_query(AdminWarehouseStates.select_sku_type_list, F.data.startswith('sku_list_'))
async def list_sku_by_type(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список SKU по выбранному типу.
    """
    await query.answer("⏳ Загрузка...")
    
    # Определение типа
    if query.data == 'sku_list_raw':
        sku_type = SKUType.raw
        type_name = "Сырье"
        type_emoji = "🌾"
    elif query.data == 'sku_list_semi':
        sku_type = SKUType.semi
        type_name = "Полуфабрикаты"
        type_emoji = "🛢"
    elif query.data == 'sku_list_finished':
        sku_type = SKUType.finished
        type_name = "Готовая продукция"
        type_emoji = "📦"
    else:  # all
        sku_type = None
        type_name = "Вся номенклатура"
        type_emoji = "📋"
    
    try:
        # Получение SKU
        if sku_type:
            skus = await stock_service.get_skus_by_type(
                session,
                sku_type=sku_type,
                active_only=False
            )
        else:
            skus = await stock_service.get_all_skus(session, active_only=False)
        
        if not skus:
            text = (
                f"{type_emoji} <b>{type_name}</b>\n\n"
                "❌ Нет номенклатуры в этой категории."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить SKU", callback_data='sku_create')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='sku_list')]
            ])
        else:
            text = f"{type_emoji} <b>{type_name} ({len(skus)})</b>\n\n"
            
            for sku in sorted(skus, key=lambda s: s.name):
                status = "✅" if sku.is_active else "🔒"
                text += f"{status} <b>{sku.name}</b> ({sku.unit})\n"
                text += f"   🆔 ID: {sku.id}\n"
                if sku.description:
                    desc_short = sku.description[:50] + "..." if len(sku.description) > 50 else sku.description
                    text += f"   <i>{desc_short}</i>\n"
                text += "\n"
            
            # Разбивка если слишком длинное
            if len(text) > 4000:
                text = text[:3900] + "\n\n<i>... список слишком длинный</i>"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='sku_list')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.select_sku_type_list)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_sku')]
            ])
        )
        await state.set_state(AdminWarehouseStates.sku_menu)
# ============================================================================
# УПРАВЛЕНИЕ ТЕХНОЛОГИЧЕСКИМИ КАРТАМИ (РЕЦЕПТАМИ)
# ============================================================================

@router.callback_query(AdminWarehouseStates.admin_menu, F.data == 'admin_recipes')
async def recipe_menu(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню управления рецептами.
    """
    await query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать рецепт", callback_data='recipe_create')],
        [InlineKeyboardButton(text="📋 Список рецептов", callback_data='recipe_list')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "🧪 <b>Технологические карты</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.recipe_menu)


@router.callback_query(AdminWarehouseStates.recipe_menu, F.data == 'recipe_create')
async def create_recipe_start(query: CallbackQuery, state: FSMContext) -> None:
    """
    Начинает процесс создания рецепта.
    """
    await query.answer()
    
    # Инициализация данных рецепта
    await state.update_data(recipe={'components': []})
    
    text = (
        "➕ <b>Создание технологической карты</b>\n\n"
        "📝 Введите название рецепта:\n\n"
        "<i>Примеры: Краска белая эконом, Шпатлевка финишная</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_recipe_name)


@router.message(AdminWarehouseStates.create_recipe_name, F.text)
async def create_recipe_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает ввод названия рецепта.
    """
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение названия
    data = await state.get_data()
    recipe = data.get('recipe', {})
    recipe['name'] = user_input
    await state.update_data(recipe=recipe)
    
    try:
        # Получение полуфабрикатов
        semi_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.semi,
            active_only=True
        )

        if not semi_skus:
            await message.answer(
                "❌ Нет полуфабрикатов в системе.\n"
                "Сначала создайте полуфабрикат через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
                ])
            )
            await state.set_state(AdminWarehouseStates.recipe_menu)
            return
        
        # Клавиатура выбора полуфабриката
        keyboard = get_sku_keyboard(
            semi_skus,
            callback_prefix='recipe_semi',
            show_stock=False
        )
        
        text = (
            f"✅ Название: <b>{user_input}</b>\n\n"
            "🛢 Выберите полуфабрикат (результат производства):"
        )
        
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.create_recipe_semi_sku)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)


@router.callback_query(AdminWarehouseStates.create_recipe_semi_sku, F.data.startswith('recipe_semi_'))
async def create_recipe_semi_sku(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает выбор полуфабриката.
    """
    await query.answer()
    
    # Извлечение ID полуфабриката
    semi_sku_id = int(query.data.split('_')[-1])
    
    try:
        # Загрузка информации о SKU
        sku = await stock_service.get_sku(session, semi_sku_id)
        
        data = await state.get_data()
        recipe = data.get('recipe', {})
        recipe['semi_sku_id'] = semi_sku_id
        recipe['semi_sku_name'] = sku.name
        await state.update_data(recipe=recipe)
        
        text = (
            f"✅ Полуфабрикат: <b>{sku.name}</b>\n\n"
            "📊 Введите процент выхода (50-100%):\n\n"
            "<i>Процент готового полуфабриката от массы сырья</i>\n"
            "<i>Примеры: 95, 98, 100</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        await state.set_state(AdminWarehouseStates.create_recipe_output)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)


@router.message(AdminWarehouseStates.create_recipe_output, F.text)
async def create_recipe_output(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод процента выхода.
    """
    user_input = message.text.strip()
    
    # Парсинг числа
    output_percentage = parse_decimal_input(user_input)
    
    if output_percentage is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация диапазона
    if output_percentage < 50 or output_percentage > 100:
        await message.answer(
            "❌ Процент выхода должен быть от 50 до 100.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение процента (как строку для FSM)
    data = await state.get_data()
    recipe = data.get('recipe', {})
    recipe['output_percentage'] = str(output_percentage)
    await state.update_data(recipe=recipe)
    
    text = (
        f"✅ Процент выхода: <b>{output_percentage}%</b>\n\n"
        "⚖️ Введите базовый размер замеса (кг):\n\n"
        "<i>Рекомендуемое количество сырья для одного замеса</i>\n"
        "<i>Примеры: 100, 500, 1000</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_recipe_batch_size)


@router.message(AdminWarehouseStates.create_recipe_batch_size, F.text)
async def create_recipe_batch_size(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод размера замеса.
    """
    user_input = message.text.strip()
    
    # Парсинг числа
    batch_size = parse_decimal_input(user_input)
    
    if batch_size is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация положительности
    validation = validate_positive_decimal(batch_size, min_value=Decimal('1'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение размера (как строку для FSM)
    data = await state.get_data()
    recipe = data.get('recipe', {})
    recipe['batch_size'] = str(batch_size)
    await state.update_data(recipe=recipe)
    
    text = (
        f"✅ Размер замеса: <b>{batch_size} кг</b>\n\n"
        "📝 Введите описание рецепта (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.create_recipe_desc)


@router.message(AdminWarehouseStates.create_recipe_desc, F.text)
async def create_recipe_desc(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает ввод описания и переходит к добавлению компонентов.
    """
    user_input = message.text.strip()
    
    # Получение текущих данных
    data = await state.get_data()
    recipe = data.get('recipe', {})
    
    # Проверка на пропуск
    if user_input == '-':
        recipe['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        recipe['description'] = user_input
    
    await state.update_data(recipe=recipe)
    
    # Переход к добавлению компонентов
    await show_add_component_menu(message, state, session)


async def show_add_component_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает меню добавления компонента сырья.
    """
    try:
        # Получение сырья
        raw_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.raw,
            active_only=True
        )
        
        if not raw_skus:
            await message.answer(
                "❌ Нет сырья в системе.\n"
                "Сначала создайте сырье через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
                ])
            )
            await state.set_state(AdminWarehouseStates.recipe_menu)
            return
        
        # Текущие компоненты
        data = await state.get_data()
        recipe = data.get('recipe', {})
        components = recipe.get('components', [])
        
        components_text = ""
        total_percentage = Decimal('0')
        
        if components:
            components_text = "\n<b>Добавленные компоненты:</b>\n"
            for i, comp in enumerate(components, 1):
                comp_percentage = Decimal(comp['percentage'])
                components_text += f"  {i}. {comp['name']}: {comp_percentage}%\n"
                total_percentage += comp_percentage
            components_text += f"\n<b>Итого:</b> {total_percentage}%\n"
            
            if total_percentage == 100:
                components_text += "✅ Сумма компонентов = 100%\n"
            else:
                components_text += f"⚠️ Осталось: {100 - total_percentage}%\n"
            
            components_text += "\n"
        
        # Клавиатура выбора сырья
        keyboard_buttons = []
        
        for sku in raw_skus:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{sku.name} ({sku.unit})",
                    callback_data=f'recipe_comp_{sku.id}'
                )
            ])
        
        # Кнопки управления
        if components and total_percentage == 100:
            keyboard_buttons.append([
                InlineKeyboardButton(text="✅ Завершить добавление", callback_data='recipe_comp_done')
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Отменить", callback_data='recipe_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = (
            "🌾 <b>Добавление компонентов</b>\n"
            f"{components_text}"
            "Выберите сырье для добавления:"
        )
        
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.add_component_select_raw)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)


@router.callback_query(AdminWarehouseStates.add_component_select_raw, F.data.startswith('recipe_comp_'))
async def add_component_select_raw(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает выбор сырья для компонента.
    """
    await query.answer()
    
    # Проверка на завершение
    if query.data == 'recipe_comp_done':
        await review_recipe_components(query, state, session)
        return
    
    # Извлечение ID сырья
    raw_sku_id = int(query.data.split('_')[-1])
    
    # Проверка: не добавлено ли уже это сырье
    data = await state.get_data()
    recipe = data.get('recipe', {})
    components = recipe.get('components', [])
    
    if any(comp['raw_sku_id'] == raw_sku_id for comp in components):
        await query.answer("⚠️ Это сырье уже добавлено!", show_alert=True)
        return
    
    try:
        # Загрузка информации о сырье
        sku = await stock_service.get_sku(session, raw_sku_id)
        
        # Сохранение текущего компонента
        await state.update_data(current_component={
            'raw_sku_id': raw_sku_id,
            'name': sku.name
        })
        
        # Расчет оставшегося процента
        total_percentage = sum(Decimal(comp['percentage']) for comp in components)
        remaining = 100 - total_percentage
        
        text = (
            f"✅ Сырье: <b>{sku.name}</b>\n\n"
            f"📊 Осталось распределить: <b>{remaining}%</b>\n\n"
            "Введите процент для этого компонента:\n\n"
            "<i>Примеры: 25, 30.5, 45</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        await state.set_state(AdminWarehouseStates.add_component_percentage)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)


@router.message(AdminWarehouseStates.add_component_percentage, F.text)
async def add_component_percentage(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает ввод процента для компонента.
    """
    user_input = message.text.strip()
    
    # Парсинг числа
    percentage = parse_decimal_input(user_input)
    
    if percentage is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация диапазона
    if percentage <= 0 or percentage > 100:
        await message.answer(
            "❌ Процент должен быть от 0.01 до 100.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверка суммы
    data = await state.get_data()
    recipe = data.get('recipe', {})
    components = recipe.get('components', [])
    
    total_percentage = sum(Decimal(comp['percentage']) for comp in components)
    
    if total_percentage + percentage > 100:
        remaining = 100 - total_percentage
        await message.answer(
            f"❌ Превышен лимит!\n\n"
            f"Осталось распределить: <b>{remaining}%</b>\n"
            f"Вы пытаетесь добавить: <b>{percentage}%</b>\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        return
    
    # Добавление компонента
    current_component = data.get('current_component', {})
    components.append({
        'raw_sku_id': current_component['raw_sku_id'],
        'name': current_component['name'],
        'percentage': str(percentage)  # Сохраняем как строку для FSM
    })
    
    recipe['components'] = components
    await state.update_data(recipe=recipe, current_component=None)
    
    # Проверка завершенности
    new_total = total_percentage + percentage
    
    if new_total == 100:
        await message.answer(
            f"✅ Компонент добавлен: <b>{current_component['name']}</b> - {percentage}%\n\n"
            "✅ Сумма компонентов = 100%\n"
            "Рецепт готов к созданию!"
        )
        await review_recipe_components_from_message(message, state, session)
    else:
        await message.answer(
            f"✅ Компонент добавлен: <b>{current_component['name']}</b> - {percentage}%\n\n"
            f"📊 Итого: {new_total}% (осталось: {100 - new_total}%)"
        )
        await show_add_component_menu(message, state, session)


async def review_recipe_components(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает итоговую сводку рецепта для подтверждения (из callback).
    """
    await query.answer()
    
    data = await state.get_data()
    recipe = data.get('recipe', {})
    
    # Формирование сводки
    summary = (
        "📋 <b>Подтверждение создания рецепта</b>\n\n"
        f"🧪 <b>Название:</b> {recipe['name']}\n"
        f"🛢 <b>Полуфабрикат:</b> {recipe['semi_sku_name']}\n"
        f"📊 <b>Выход:</b> {recipe['output_percentage']}%\n"
        f"⚖️ <b>Размер замеса:</b> {recipe['batch_size']} кг\n"
    )
    
    if recipe.get('description'):
        summary += f"📝 <b>Описание:</b> {recipe['description']}\n"
    
    summary += "\n<b>Компоненты:</b>\n"
    
    for i, comp in enumerate(recipe['components'], 1):
        summary += f"  {i}. {comp['name']}: {comp['percentage']}%\n"
    
    total = sum(Decimal(comp['percentage']) for comp in recipe['components'])
    summary += f"\n<b>Итого:</b> {total}%\n\n❓ Создать рецепт?"
    
    await query.message.edit_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='recipe_confirm_create',
            cancel_callback='recipe_cancel'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.confirm_create_recipe)


async def review_recipe_components_from_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает итоговую сводку рецепта для подтверждения (из message).
    """
    data = await state.get_data()
    recipe = data.get('recipe', {})
    
    # Формирование сводки
    summary = (
        "📋 <b>Подтверждение создания рецепта</b>\n\n"
        f"🧪 <b>Название:</b> {recipe['name']}\n"
        f"🛢 <b>Полуфабрикат:</b> {recipe['semi_sku_name']}\n"
        f"📊 <b>Выход:</b> {recipe['output_percentage']}%\n"
        f"⚖️ <b>Размер замеса:</b> {recipe['batch_size']} кг\n"
    )
    
    if recipe.get('description'):
        summary += f"📝 <b>Описание:</b> {recipe['description']}\n"
    
    summary += "\n<b>Компоненты:</b>\n"
    
    for i, comp in enumerate(recipe['components'], 1):
        summary += f"  {i}. {comp['name']}: {comp['percentage']}%\n"
    
    total = sum(Decimal(comp['percentage']) for comp in recipe['components'])
    summary += f"\n<b>Итого:</b> {total}%\n\n❓ Создать рецепт?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='recipe_confirm_create',
            cancel_callback='recipe_cancel'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.confirm_create_recipe)


@router.callback_query(AdminWarehouseStates.confirm_create_recipe, F.data == 'recipe_confirm_create')
async def confirm_create_recipe(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Создает рецепт в базе данных.
    """
    await query.answer("⏳ Создание рецепта...")
    
    data = await state.get_data()
    recipe_data = data.get('recipe', {})
    
    try:
        # Подготовка компонентов (конвертация строк обратно в Decimal)
        components = [
            {
                'raw_sku_id': comp['raw_sku_id'],
                'percentage': Decimal(comp['percentage'])
            }
            for comp in recipe_data['components']
        ]
        
        # Создание рецепта через сервис
        recipe = await recipe_service.create_recipe(
            session=session,
            name=recipe_data['name'],
            semi_finished_sku_id=recipe_data['semi_sku_id'],
            output_percentage=Decimal(recipe_data['output_percentage']),
            batch_size=Decimal(recipe_data['batch_size']),
            description=recipe_data.get('description'),
            components=components
        )
        
        text = (
            "✅ <b>Рецепт успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {recipe.id}\n"
            f"🧪 <b>Название:</b> {recipe.name}\n"
            f"🛢 <b>Полуфабрикат:</b> {recipe_data['semi_sku_name']}\n"
            f"📊 <b>Компонентов:</b> {len(components)}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных рецепта
        await state.update_data(recipe=None, current_component=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать еще", callback_data='recipe_create')],
            [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.recipe_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании рецепта:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К рецептам", callback_data='admin_recipes')]
            ]),
            parse_mode='HTML'
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)


@router.callback_query(AdminWarehouseStates.recipe_menu, F.data == 'recipe_list')
async def list_recipes(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список всех рецептов.
    """
    await query.answer("⏳ Загрузка рецептов...")
    
    try:
        # Получение всех рецептов
        recipes = await recipe_service.get_recipes(session, active_only=False)
        
        if not recipes:
            text = (
                "📋 <b>Список рецептов</b>\n\n"
                "❌ Нет созданных рецептов."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать рецепт", callback_data='recipe_create')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_recipes')]
            ])
        else:
            text = f"📋 <b>Список рецептов ({len(recipes)})</b>\n\n"
            
            for recipe in recipes:
                status = "✅ Активен" if recipe.is_active else "🔒 Неактивен"
                text += f"🧪 <b>{recipe.name}</b> - {status}\n"
                text += f"   🛢 Полуфабрикат: {recipe.semi_product.name}\n"
                text += f"   📊 Выход: {recipe.yield_percent}%\n"
                text += f"   🌾 Компонентов: {len(recipe.components)}\n"
                text += f"   🆔 ID: {recipe.id}\n\n"
            
            # Разбивка если слишком длинное
            if len(text) > 4000:
                text = text[:3900] + "\n\n<i>... список слишком длинный</i>"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_recipes')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.recipe_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_recipes')]
            ])
        )
        await state.set_state(AdminWarehouseStates.recipe_menu)
# ============================================================================
# УПРАВЛЕНИЕ ВАРИАНТАМИ УПАКОВКИ
# ============================================================================

@router.callback_query(AdminWarehouseStates.admin_menu, F.data == 'admin_packing_variants')
async def packing_variant_menu(query: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает меню управления вариантами упаковки.
    """
    await query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать вариант", callback_data='pv_create')],
        [InlineKeyboardButton(text="📋 Список вариантов", callback_data='pv_list')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "📦 <b>Варианты упаковки</b>\n\n"
        "Управление связями полуфабрикат → готовая продукция\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminWarehouseStates.packing_variant_menu)


@router.callback_query(AdminWarehouseStates.packing_variant_menu, F.data == 'pv_create')
async def create_variant_start(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Начинает процесс создания варианта упаковки.
    """
    await query.answer()
    
    # Инициализация данных варианта
    await state.update_data(packing_variant={})
    
    try:
        # Получение полуфабрикатов
        semi_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.semi,
            active_only=True
        )

        if not semi_skus:
            await query.message.edit_text(
                "❌ Нет полуфабрикатов в системе.\n"
                "Сначала создайте полуфабрикат через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
                ])
            )
            await state.set_state(AdminWarehouseStates.packing_variant_menu)
            return
        
        # Клавиатура выбора полуфабриката
        keyboard = get_sku_keyboard(
            semi_skus,
            callback_prefix='pv_semi',
            show_stock=False
        )
        
        text = (
            "➕ <b>Создание варианта упаковки</b>\n\n"
            "🛢 Выберите полуфабрикат:"
        )
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.create_variant_semi)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
            ])
        )
        await state.set_state(AdminWarehouseStates.packing_variant_menu)


@router.callback_query(AdminWarehouseStates.create_variant_semi, F.data.startswith('pv_semi_'))
async def create_variant_semi(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает выбор полуфабриката.
    """
    await query.answer()
    
    # Извлечение ID полуфабриката
    semi_sku_id = int(query.data.split('_')[-1])
    
    try:
        # Загрузка информации о полуфабрикате
        semi_sku = await stock_service.get_sku(session, semi_sku_id)
        
        # Сохранение
        data = await state.get_data()
        packing_variant = data.get('packing_variant', {})
        packing_variant['semi_sku_id'] = semi_sku_id
        packing_variant['semi_sku_name'] = semi_sku.name
        await state.update_data(packing_variant=packing_variant)
        
        # Получение готовой продукции
        finished_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.finished,
            active_only=True
        )
        
        if not finished_skus:
            await query.message.edit_text(
                "❌ Нет готовой продукции в системе.\n"
                "Сначала создайте готовую продукцию через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
                ])
            )
            await state.set_state(AdminWarehouseStates.packing_variant_menu)
            return
        
        # Клавиатура выбора готовой продукции
        keyboard = get_sku_keyboard(
            finished_skus,
            callback_prefix='pv_finished',
            show_stock=False
        )
        
        text = (
            f"✅ Полуфабрикат: <b>{semi_sku.name}</b>\n\n"
            "📦 Выберите готовую продукцию:"
        )
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.create_variant_finished)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
            ])
        )
        await state.set_state(AdminWarehouseStates.packing_variant_menu)


@router.callback_query(AdminWarehouseStates.create_variant_finished, F.data.startswith('pv_finished_'))
async def create_variant_finished(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает выбор готовой продукции.
    """
    await query.answer()
    
    # Извлечение ID готовой продукции
    finished_sku_id = int(query.data.split('_')[-1])
    
    try:
        # Загрузка информации о готовой продукции
        finished_sku = await stock_service.get_sku(session, finished_sku_id)
        
        # Сохранение
        data = await state.get_data()
        packing_variant = data.get('packing_variant', {})
        packing_variant['finished_sku_id'] = finished_sku_id
        packing_variant['finished_sku_name'] = finished_sku.name
        packing_variant['finished_sku_unit'] = finished_sku.unit
        await state.update_data(packing_variant=packing_variant)
        
        text = (
            f"✅ Полуфабрикат: <b>{packing_variant['semi_sku_name']}</b>\n"
            f"✅ Готовая продукция: <b>{finished_sku.name}</b>\n\n"
            f"⚖️ Введите вес/объем одной единицы ({finished_sku.unit}):\n\n"
            "<i>Например: 10 (для ведра 10 кг)</i>\n"
            "<i>Или: 0.5 (для баночки 500г)</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        await state.set_state(AdminWarehouseStates.create_variant_weight)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
            ])
        )
        await state.set_state(AdminWarehouseStates.packing_variant_menu)


@router.message(AdminWarehouseStates.create_variant_weight, F.text)
async def create_variant_weight(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод веса/объема единицы.
    """
    user_input = message.text.strip()
    
    # Парсинг числа
    weight = parse_decimal_input(user_input)
    
    if weight is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация положительности
    validation = validate_positive_decimal(weight, min_value=Decimal('0.001'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение веса
    data = await state.get_data()
    packing_variant = data.get('packing_variant', {})
    packing_variant['weight_per_unit'] = str(weight)  # Сохраняем как строку для FSM
    await state.update_data(packing_variant=packing_variant)
    
    # Формирование сводки
    summary = (
        "📋 <b>Подтверждение создания варианта упаковки</b>\n\n"
        f"🛢 <b>Полуфабрикат:</b> {packing_variant['semi_sku_name']}\n"
        f"📦 <b>Готовая продукция:</b> {packing_variant['finished_sku_name']}\n"
        f"⚖️ <b>Вес единицы:</b> {weight} {packing_variant['finished_sku_unit']}\n\n"
        "❓ Создать вариант упаковки?"
    )
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='pv_confirm_create',
            cancel_callback='pv_cancel'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminWarehouseStates.confirm_create_variant)


@router.callback_query(AdminWarehouseStates.confirm_create_variant, F.data == 'pv_confirm_create')
async def confirm_create_variant(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Создает вариант упаковки в базе данных.
    """
    await query.answer("⏳ Создание варианта упаковки...")
    
    data = await state.get_data()
    variant_data = data.get('packing_variant', {})
    
    try:
        # Создание варианта упаковки через сервис
        variant = await packing_service.create_packing_variant(
            session=session,
            semi_finished_sku_id=variant_data['semi_sku_id'],
            finished_sku_id=variant_data['finished_sku_id'],
            weight_per_unit=Decimal(variant_data['weight_per_unit'])
        )
        
        text = (
            "✅ <b>Вариант упаковки успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {variant.id}\n"
            f"🛢 <b>Полуфабрикат:</b> {variant_data['semi_sku_name']}\n"
            f"📦 <b>Готовая продукция:</b> {variant_data['finished_sku_name']}\n"
            f"⚖️ <b>Вес единицы:</b> {variant_data['weight_per_unit']} {variant_data['finished_sku_unit']}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных варианта
        await state.update_data(packing_variant=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать еще", callback_data='pv_create')],
            [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.packing_variant_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании варианта:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К вариантам", callback_data='admin_packing_variants')]
            ]),
            parse_mode='HTML'
        )
        await state.set_state(AdminWarehouseStates.packing_variant_menu)


@router.callback_query(AdminWarehouseStates.packing_variant_menu, F.data == 'pv_list')
async def list_packing_variants(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список всех вариантов упаковки.
    """
    await query.answer("⏳ Загрузка вариантов...")
    
    try:
        # Получение всех вариантов упаковки
        variants = await packing_service.get_packing_variants(session, active_only=False)
        
        if not variants:
            text = (
                "📋 <b>Список вариантов упаковки</b>\n\n"
                "❌ Нет созданных вариантов."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать вариант", callback_data='pv_create')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_packing_variants')]
            ])
        else:
            text = f"📋 <b>Список вариантов упаковки ({len(variants)})</b>\n\n"
            
            for variant in variants:
                status = "✅ Активен" if variant.is_active else "🔒 Неактивен"
                text += f"📦 <b>{variant.finished_product.name}</b> - {status}\n"
                text += f"   🛢 Из: {variant.semi_product.name}\n"
                text += f"   ⚖️ Вес: {variant.weight_per_unit} {variant.finished_product.unit}\n"
                text += f"   🆔 ID: {variant.id}\n\n"
            
            # Разбивка если слишком длинное
            if len(text) > 4000:
                text = text[:3900] + "\n\n<i>... список слишком длинный</i>"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_packing_variants')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminWarehouseStates.packing_variant_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_packing_variants')]
            ])
        )
        await state.set_state(AdminWarehouseStates.packing_variant_menu)


# ============================================================================
# НАВИГАЦИЯ И ВОЗВРАТ
# ============================================================================

@router.callback_query(F.data == 'wh_cancel')
async def cancel_warehouse_creation(query: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания склада."""
    await query.answer()
    await state.update_data(warehouse=None)
    await warehouse_menu(query, state)


@router.callback_query(F.data == 'sku_cancel')
async def cancel_sku_creation(query: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания SKU."""
    await query.answer()
    await state.update_data(sku=None)
    await sku_menu(query, state)


@router.callback_query(F.data == 'recipe_cancel')
async def cancel_recipe_creation(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Отмена создания рецепта."""
    await query.answer()
    await state.update_data(recipe=None, current_component=None)
    await recipe_menu(query, state)


@router.callback_query(F.data == 'pv_cancel')
async def cancel_packing_variant_creation(query: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания варианта упаковки."""
    await query.answer()
    await state.update_data(packing_variant=None)
    await packing_variant_menu(query, state)


# ============================================================================
# ОБРАБОТЧИКИ ВОЗВРАТА ИЗ ПОДМЕНЮ В ГЛАВНОЕ МЕНЮ
# ============================================================================

@router.callback_query(AdminWarehouseStates.warehouse_menu, F.data == 'admin_start')
async def back_to_admin_from_warehouse(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат из меню складов в главное админ-меню."""
    await start_admin(query, state, session)


@router.callback_query(AdminWarehouseStates.sku_menu, F.data == 'admin_start')
async def back_to_admin_from_sku(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат из меню SKU в главное админ-меню."""
    await start_admin(query, state, session)


@router.callback_query(AdminWarehouseStates.recipe_menu, F.data == 'admin_start')
async def back_to_admin_from_recipe(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат из меню рецептов в главное админ-меню."""
    await start_admin(query, state, session)


@router.callback_query(AdminWarehouseStates.packing_variant_menu, F.data == 'admin_start')
async def back_to_admin_from_packing(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат из меню вариантов упаковки в главное админ-меню."""
    await start_admin(query, state, session)


@router.callback_query(AdminWarehouseStates.select_sku_type_list, F.data == 'admin_sku')
async def back_to_sku_menu_from_list(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат из списка SKU в меню SKU."""
    await sku_menu(query, state)


# ============================================================================
# ВЫХОД ИЗ АДМИНИСТРАТИВНОЙ ПАНЕЛИ
# ============================================================================

@router.callback_query(F.data == 'admin_exit')
@router.message(Command('cancel'), StateFilter(AdminWarehouseStates))
async def exit_admin(event: Union[Message, CallbackQuery], state: FSMContext) -> None:
    """
    Завершает административную сессию.
    """
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event
    
    # Очистка всех данных FSM
    await state.clear()
    
    text = (
        "✅ <b>Административная сессия завершена</b>\n\n"
        "Используйте /admin для повторного входа."
    )
    
    if isinstance(event, CallbackQuery):
        await message.edit_text(text, parse_mode='HTML')
    else:
        await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode='HTML')


# ============================================================================
# ОБРАБОТЧИКИ ДЛЯ ОТМЕНЫ ИЗ ЛЮБОГО СОСТОЯНИЯ
# ============================================================================

@router.callback_query(StateFilter(AdminWarehouseStates), F.data == 'cancel')
async def cancel_from_any_state(query: CallbackQuery, state: FSMContext) -> None:
    """Отмена из любого состояния административной панели."""
    await query.answer()
    
    current_state = await state.get_state()
    
    # Очистка временных данных
    await state.update_data(
        warehouse=None,
        sku=None,
        recipe=None,
        current_component=None,
        packing_variant=None
    )
    
    # Определение куда вернуться в зависимости от текущего состояния
    if current_state and 'warehouse' in current_state:
        await warehouse_menu(query, state)
    elif current_state and 'sku' in current_state:
        await sku_menu(query, state)
    elif current_state and 'recipe' in current_state:
        await recipe_menu(query, state)
    elif current_state and 'packing_variant' in current_state:
        await packing_variant_menu(query, state)
    else:
        # По умолчанию - главное меню
        session = None  # Нужно получить session через middleware
        await start_admin(query, state, session)



# Export router with expected name
admin_warehouse_router = router

__all__ = ['admin_warehouse_router']
