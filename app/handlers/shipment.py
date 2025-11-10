"""
Обработчик команд отгрузки готовой продукции (aiogram 3.x).

Этот модуль реализует диалоговые сценарии для:
- Создания отгрузок для получателей (контрагентов)
- Добавления позиций готовой продукции
- Резервирования продукции под отгрузку
- Выполнения отгрузки с FIFO-логикой
- Отмены и корректировки отгрузок
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, ShipmentStatus, SKUType, ApprovalStatus
from app.services import (
    shipment_service,
    warehouse_service,
    stock_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_recipients_keyboard,
    get_sku_keyboard,
    get_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import (
    validate_positive_decimal,
    validate_text_length,
    validate_date_format,
    parse_decimal_input,
    parse_date_input
)
from app.utils.logger import get_logger

logger = get_logger("shipment_handler")

# Создаём роутер для shipment handlers
shipment_router = Router(name="shipment")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class ShipmentStates(StatesGroup):
    """Состояния диалога отгрузки."""
    select_action = State()
    # Создание отгрузки
    select_recipient = State()
    enter_shipment_date = State()
    enter_initial_notes = State()
    # Добавление позиций
    select_sku = State()
    enter_quantity = State()
    enter_price = State()
    # Завершение и резервирование
    review_shipment = State()
    confirm_reserve = State()
    # Выполнение отгрузки
    confirm_execution = State()


# ============================================================================
# НАЧАЛО ДИАЛОГА ОТГРУЗКИ
# ============================================================================

@shipment_router.message(Command("shipment"))
@shipment_router.callback_query(F.data == "shipment_start")
async def start_shipment(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс управления отгрузками.
    
    Команда: /shipment или кнопка "Отгрузка"
    """
    # Определяем тип update
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
        user = update.from_user
    else:
        message = update
        user = update.from_user
    
    # Получение пользователя из БД по telegram_id
    from sqlalchemy import select
    stmt = select(User).where(User.telegram_id == user.id)
    db_user = await session.scalar(stmt)

    if not db_user:
        await message.answer(
            "❌ Пользователь не найден. Используйте /start для регистрации."
        )
        return

    # Проверка статуса утверждения
    if db_user.approval_status != ApprovalStatus.approved:
        await message.answer(
            "❌ Ваша регистрация еще не утверждена администратором.\n"
            "Пожалуйста, ожидайте утверждения."
        )
        return

    # Проверка прав доступа
    if not db_user.can_ship:
        await message.answer(
            "❌ У вас нет прав для отгрузки.\n"
            "Обратитесь к администратору."
        )
        return
    
    # Инициализация данных
    from datetime import timezone
    await state.update_data(
        user_id=user.id,
        started_at=datetime.now(timezone.utc).isoformat(),
        items=[]  # Список позиций отгрузки
    )
    
    # Меню выбора действия
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать новую отгрузку", callback_data='ship_create')],
        [InlineKeyboardButton(text="📋 Мои отгрузки", callback_data='ship_list')],
        [InlineKeyboardButton(text="❌ Отменить", callback_data='ship_cancel')]
    ])
    
    text = (
        "🚚 <b>Управление отгрузками</b>\n\n"
        "Выберите действие:"
    )
    
    if isinstance(update, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)
    
    await state.set_state(ShipmentStates.select_action)


# ============================================================================
# ВЫБОР ДЕЙСТВИЯ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.select_action),
    F.data == "ship_create"
)
async def select_action_create(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает создание новой отгрузки.
    """
    await callback.answer()

    try:
        # Получение склада по умолчанию
        warehouse = await warehouse_service.get_default_warehouse(session)

        if not warehouse:
            await callback.message.answer(
                "❌ Склад не найден.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return

        # Сохранение склада
        await state.update_data(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name
        )

        # Получение списка получателей
        recipients = await shipment_service.get_recipients(
            session,
            active_only=True,
            limit=50
        )

        if not recipients:
            await callback.message.answer(
                "❌ В системе нет получателей.\n"
                "Обратитесь к администратору для добавления контрагентов.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return

        # Клавиатура выбора получателя
        keyboard = get_recipients_keyboard(
            recipients,
            callback_prefix='ship_rec',
            show_contact=True
        )

        text = (
            "🚚 <b>Создание отгрузки</b>\n\n"
            f"🏭 <b>Склад:</b> {warehouse.name}\n\n"
            "👤 Выберите получателя (контрагента):"
        )

        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(ShipmentStates.select_recipient)

    except Exception as e:
        logger.error(f"Error in select_action_create: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВЫБОР ПОЛУЧАТЕЛЯ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.select_recipient),
    F.data.startswith("ship_rec_")
)
async def select_recipient(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор получателя.
    """
    await callback.answer()
    
    # Извлечение ID получателя
    recipient_id = int(callback.data.split('_')[-1])
    
    try:
        # Загрузка информации о получателе
        recipient = await session.get(
            shipment_service.Recipient,
            recipient_id
        )
        
        # Сохранение выбора
        await state.update_data(
            recipient_id=recipient_id,
            recipient_name=recipient.name
        )
        
        # Запрос даты отгрузки
        data = await state.get_data()
        today = date.today()
        
        text = (
            f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
            f"👤 <b>Получатель:</b> {recipient.name}\n\n"
            "📅 Введите дату отгрузки (ДД.ММ.ГГГГ):\n\n"
            f"<i>Сегодня: {today.strftime('%d.%m.%Y')}</i>\n"
            "<i>Или отправьте '-' для использования сегодняшней даты</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
        await state.set_state(ShipmentStates.enter_shipment_date)
        
    except Exception as e:
        logger.error(f"Error in select_recipient: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВВОД ДАТЫ ОТГРУЗКИ
# ============================================================================

@shipment_router.message(StateFilter(ShipmentStates.enter_shipment_date), F.text)
async def enter_shipment_date(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод даты отгрузки.
    """
    user_input = message.text.strip()
    
    # Проверка на использование сегодняшней даты
    if user_input == '-':
        shipment_date = date.today()
    else:
        # Парсинг даты
        shipment_date = parse_date_input(user_input)
        
        if shipment_date is None:
            await message.answer(
                "❌ Некорректный формат даты.\n"
                "Используйте формат ДД.ММ.ГГГГ\n\n"
                "Примеры: <code>15.12.2024</code>, <code>01.01.2025</code>\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Проверка: дата не должна быть слишком далеко в прошлом
        if shipment_date < date.today() - timedelta(days=30):
            await message.answer(
                "❌ Дата отгрузки не может быть более 30 дней в прошлом.\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
    
    # Сохранение даты
    await state.update_data(shipment_date=shipment_date.isoformat())
    
    # Запрос примечаний
    text = (
        f"✅ Дата отгрузки: <b>{shipment_date.strftime('%d.%m.%Y')}</b>\n\n"
        "📝 Введите примечания к отгрузке (необязательно):\n\n"
        "<i>Номер заказа, условия доставки и т.д.</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ShipmentStates.enter_initial_notes)


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ К ОТГРУЗКЕ
# ============================================================================

@shipment_router.message(StateFilter(ShipmentStates.enter_initial_notes), F.text)
async def enter_initial_notes(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает ввод примечаний и создает отгрузку.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        initial_notes = None
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        initial_notes = user_input
    
    # Получаем данные из FSM
    data = await state.get_data()
    
    try:
        # Создание отгрузки через сервис
        shipment_date = date.fromisoformat(data['shipment_date'])
        
        shipment = await shipment_service.create_shipment(
            session=session,
            warehouse_id=data['warehouse_id'],
            recipient_id=data['recipient_id'],
            created_by_id=data['user_id'],
            shipment_date=shipment_date,
            notes=initial_notes
        )
        
        # Сохранение ID отгрузки
        await state.update_data(shipment_id=shipment.id)
        
        # Успешное создание
        success_text = (
            "✅ <b>Отгрузка создана!</b>\n\n"
            f"🆔 <b>ID:</b> {shipment.id}\n"
            f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
            f"👤 <b>Получатель:</b> {data['recipient_name']}\n"
            f"📅 <b>Дата:</b> {shipment.shipment_date.strftime('%d.%m.%Y')}\n"
            f"📊 <b>Статус:</b> {shipment.status.value}\n\n"
            "➡️ Теперь добавьте позиции готовой продукции."
        )
        
        await message.answer(success_text)
        
        # Автоматический переход к добавлению позиций
        await show_add_item_menu(message, state, session)
        
    except Exception as e:
        logger.error(f"Error in enter_initial_notes: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при создании отгрузки: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ДОБАВЛЕНИЕ ПОЗИЦИЙ
# ============================================================================

async def show_add_item_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает меню добавления позиции.
    """
    try:
        # Получаем данные
        data = await state.get_data()
        warehouse_id = data['warehouse_id']
        
        # Получение готовой продукции со склада
        finished_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.FINISHED,
            active_only=True
        )
        
        if not finished_skus:
            await message.answer(
                "❌ Нет готовой продукции для отгрузки.\n"
                "Сначала необходимо выполнить фасовку.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Клавиатура выбора SKU
        keyboard = get_sku_keyboard(
            finished_skus,
            callback_prefix='ship_sku',
            show_stock=True,
            warehouse_id=warehouse_id
        )
        
        # Текущие позиции отгрузки
        items = data.get('items', [])
        items_text = ""
        
        if items:
            items_text = "\n<b>Добавленные позиции:</b>\n"
            for i, item in enumerate(items, 1):
                items_text += f"  {i}. {item['sku_name']}: {item['quantity']} {item['unit']}\n"
            items_text += "\n"
        
        text = (
            "📦 <b>Добавление позиции в отгрузку</b>\n\n"
            f"{items_text}"
            "Выберите готовую продукцию:"
        )
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(ShipmentStates.select_sku)
        
    except Exception as e:
        logger.error(f"Error in show_add_item_menu: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@shipment_router.callback_query(
    StateFilter(ShipmentStates.select_sku),
    F.data.startswith("ship_sku_")
)
async def select_sku(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор готовой продукции.
    """
    await callback.answer()
    
    # Извлечение ID SKU
    sku_id = int(callback.data.split('_')[-1])
    
    # Получаем данные
    data = await state.get_data()
    items = data.get('items', [])
    
    # Проверка: не добавлена ли уже эта позиция
    if any(item['sku_id'] == sku_id for item in items):
        await callback.message.answer(
            "⚠️ Эта позиция уже добавлена в отгрузку.\n"
            "Выберите другую продукцию.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    try:
        # Загрузка информации о SKU
        sku = await stock_service.get_sku(session, sku_id)
        
        # Проверка остатков на складе
        warehouse_id = data['warehouse_id']
        availability = await stock_service.calculate_stock_availability(
            session,
            warehouse_id=warehouse_id,
            sku_id=sku_id
        )
        
        # Сохранение текущих данных позиции
        await state.update_data(
            current_sku_id=sku_id,
            current_sku_name=sku.name,
            current_sku_unit=sku.unit,
            current_available=str(availability['available'])
        )
        
        text = (
            f"📦 <b>Продукция:</b> {sku.name}\n"
            f"📊 <b>Доступно на складе:</b> {availability['available']} {sku.unit}\n\n"
            f"📝 Введите количество для отгрузки ({sku.unit}):\n\n"
            f"<i>Максимум: {availability['available']}</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
        await state.set_state(ShipmentStates.enter_quantity)
        
    except Exception as e:
        logger.error(f"Error in select_sku: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВВОД КОЛИЧЕСТВА
# ============================================================================

@shipment_router.message(StateFilter(ShipmentStates.enter_quantity), F.text)
async def enter_quantity(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод количества продукции.
    """
    user_input = message.text.strip()
    
    # Парсинг количества
    quantity = parse_decimal_input(user_input)
    
    if quantity is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация положительности
    validation = validate_positive_decimal(quantity, min_value=Decimal('0.001'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные
    data = await state.get_data()
    available = Decimal(data['current_available'])
    
    # Проверка доступности
    if quantity > available:
        await message.answer(
            f"❌ Количество ({quantity}) превышает доступный остаток ({available}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение количества
    await state.update_data(current_quantity=str(quantity))
    
    # Запрос цены
    unit = data['current_sku_unit']
    text = (
        f"✅ Количество: <b>{quantity} {unit}</b>\n\n"
        f"💰 Введите цену за {unit} (необязательно):\n\n"
        "<i>Примеры: 150, 250.50</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ShipmentStates.enter_price)


# ============================================================================
# ВВОД ЦЕНЫ
# ============================================================================

@shipment_router.message(StateFilter(ShipmentStates.enter_price), F.text)
async def enter_price(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает ввод цены и добавляет позицию.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        price = None
    else:
        # Парсинг цены
        price = parse_decimal_input(user_input)
        
        if price is None:
            await message.answer(
                "❌ Некорректный формат числа.\n\n"
                "Попробуйте снова или отправьте '-' для пропуска:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        # Проверка неотрицательности
        if price < 0:
            await message.answer(
                "❌ Цена не может быть отрицательной.\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
    
    # Получаем данные
    data = await state.get_data()
    
    try:
        # Добавление позиции через сервис
        quantity_decimal = Decimal(data['current_quantity'])
        
        item = await shipment_service.add_shipment_item(
            session=session,
            shipment_id=data['shipment_id'],
            sku_id=data['current_sku_id'],
            quantity=quantity_decimal,
            price_per_unit=price
        )
        
        # Добавление информации о позиции в список
        items = data.get('items', [])
        items.append({
            'item_id': item.id,
            'sku_id': data['current_sku_id'],
            'sku_name': data['current_sku_name'],
            'unit': data['current_sku_unit'],
            'quantity': str(quantity_decimal),
            'price': str(price) if price else None
        })
        
        # Обновляем список позиций и очищаем текущие данные
        await state.update_data(
            items=items,
            current_sku_id=None,
            current_sku_name=None,
            current_sku_unit=None,
            current_quantity=None,
            current_available=None
        )
        
        # Меню: добавить еще или завершить
        total_value = sum(
            (Decimal(item['quantity']) * Decimal(item['price'])) if item['price'] else 0
            for item in items
        )
        
        summary = (
            "✅ <b>Позиция добавлена!</b>\n\n"
            f"<b>Добавленные позиции ({len(items)}):</b>\n"
        )
        
        for i, it in enumerate(items, 1):
            summary += f"  {i}. {it['sku_name']}: {it['quantity']} {it['unit']}"
            if it['price']:
                item_sum = Decimal(it['quantity']) * Decimal(it['price'])
                summary += f" × {it['price']} ₽ = {item_sum} ₽"
            summary += "\n"
        
        if total_value > 0:
            summary += f"\n💵 <b>Общая сумма:</b> {total_value} ₽\n"
        
        summary += "\n❓ Что дальше?"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить еще позицию", callback_data='ship_add_more')],
            [InlineKeyboardButton(text="✅ Завершить и зарезервировать", callback_data='ship_review')],
            [InlineKeyboardButton(text="❌ Отменить отгрузку", callback_data='ship_cancel')]
        ])
        
        await message.answer(summary, reply_markup=keyboard)
        await state.set_state(ShipmentStates.review_shipment)
        
    except Exception as e:
        logger.error(f"Error in enter_price: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при добавлении позиции: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
# ============================================================================
# ДОБАВЛЕНИЕ ЕЩЕ ПОЗИЦИЙ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.review_shipment),
    F.data == "ship_add_more"
)
async def add_more_items(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает запрос на добавление еще позиций.
    """
    await callback.answer()
    await show_add_item_menu(callback.message, state, session)


# ============================================================================
# ПРОСМОТР И РЕЗЕРВИРОВАНИЕ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.review_shipment),
    F.data == "ship_review"
)
async def review_and_reserve(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Показывает сводку отгрузки и предлагает зарезервировать.
    """
    await callback.answer()
    
    data = await state.get_data()
    items = data.get('items', [])
    
    # Формирование сводки
    total_value = sum(
        (Decimal(item['quantity']) * Decimal(item['price'])) if item['price'] else 0
        for item in items
    )
    
    shipment_date = date.fromisoformat(data['shipment_date'])
    
    summary = (
        "📋 <b>Сводка отгрузки</b>\n\n"
        f"🆔 <b>ID:</b> {data['shipment_id']}\n"
        f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
        f"👤 <b>Получатель:</b> {data['recipient_name']}\n"
        f"📅 <b>Дата:</b> {shipment_date.strftime('%d.%m.%Y')}\n\n"
        f"<b>Позиции ({len(items)}):</b>\n"
    )
    
    for i, item in enumerate(items, 1):
        summary += f"  {i}. {item['sku_name']}: {item['quantity']} {item['unit']}"
        if item['price']:
            item_sum = Decimal(item['quantity']) * Decimal(item['price'])
            summary += f" × {item['price']} ₽ = {item_sum} ₽"
        summary += "\n"
    
    if total_value > 0:
        summary += f"\n💵 <b>Общая сумма:</b> {total_value} ₽\n"
    
    summary += (
        "\n<b>Резервирование:</b>\n"
        "Продукция будет зарезервирована под эту отгрузку.\n"
        "После резервирования можно будет выполнить отгрузку.\n\n"
        "❓ Зарезервировать продукцию?"
    )
    
    await callback.message.edit_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='ship_reserve',
            cancel_callback='ship_cancel'
        )
    )
    
    await state.set_state(ShipmentStates.confirm_reserve)


# ============================================================================
# ПОДТВЕРЖДЕНИЕ РЕЗЕРВИРОВАНИЯ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.confirm_reserve),
    F.data == "ship_reserve"
)
async def confirm_reserve(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Выполняет резервирование продукции под отгрузку.
    """
    await callback.answer("⏳ Резервирование...")
    
    data = await state.get_data()
    
    try:
        # Резервирование через сервис
        reserves = await shipment_service.reserve_for_shipment(
            session=session,
            shipment_id=data['shipment_id'],
            user_id=data['user_id']
        )
        
        # Успешное резервирование
        success_text = (
            "✅ <b>Продукция зарезервирована!</b>\n\n"
            f"🆔 <b>ID отгрузки:</b> {data['shipment_id']}\n"
            f"📦 <b>Зарезервировано позиций:</b> {len(reserves)}\n"
            f"📊 <b>Статус:</b> RESERVED\n\n"
            "Теперь можно выполнить отгрузку.\n\n"
            "❓ Выполнить отгрузку сейчас?"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнить отгрузку", callback_data='ship_execute')],
            [InlineKeyboardButton(text="⏸ Выполнить позже", callback_data='ship_later')],
            [InlineKeyboardButton(text="❌ Отменить резерв", callback_data='ship_cancel_reserve')]
        ])
        
        await callback.message.edit_text(success_text, reply_markup=keyboard)
        await state.set_state(ShipmentStates.confirm_execution)
        
    except Exception as e:
        logger.error(f"Error in confirm_reserve: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при резервировании:</b>\n\n"
            f"{str(e)}\n\n"
            "Отгрузка осталась в статусе DRAFT.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ВЫПОЛНЕНИЕ ОТГРУЗКИ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.confirm_execution),
    F.data == "ship_execute"
)
async def execute_shipment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Выполняет отгрузку: списывает продукцию со склада.
    """
    await callback.answer("⏳ Выполнение отгрузки...")
    
    data = await state.get_data()
    
    try:
        # Выполнение отгрузки через сервис
        shipment, movements = await shipment_service.execute_shipment(
            session=session,
            shipment_id=data['shipment_id'],
            user_id=data['user_id'],
            actual_shipment_date=date.today()
        )
        
        # Формирование отчета
        items = data.get('items', [])
        total_value = sum(
            (Decimal(item['quantity']) * Decimal(item['price'])) if item['price'] else 0
            for item in items
        )
        
        report = (
            "✅ <b>Отгрузка успешно выполнена!</b>\n\n"
            f"🆔 <b>ID:</b> {shipment.id}\n"
            f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
            f"👤 <b>Получатель:</b> {data['recipient_name']}\n"
            f"📅 <b>Дата:</b> {shipment.shipment_date.strftime('%d.%m.%Y')}\n\n"
            f"📦 <b>Отгружено позиций:</b> {len(items)}\n"
        )
        
        for i, item in enumerate(items, 1):
            report += f"  {i}. {item['sku_name']}: {item['quantity']} {item['unit']}\n"
        
        if total_value > 0:
            report += f"\n💵 <b>Общая сумма:</b> {total_value} ₽\n"
        
        report += (
            f"\n📋 <b>Создано движений:</b> {len(movements)}\n"
            f"📊 <b>Статус:</b> {shipment.status.value}"
        )
        
        await callback.message.edit_text(report, reply_markup=get_main_menu_keyboard())
        
        # Очистка состояния
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in execute_shipment: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при выполнении отгрузки:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ВЫПОЛНИТЬ ПОЗЖЕ
# ============================================================================

@shipment_router.callback_query(
    StateFilter(ShipmentStates.confirm_execution),
    F.data == "ship_later"
)
async def execute_later(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Сохраняет отгрузку для выполнения позже.
    """
    await callback.answer()
    
    data = await state.get_data()
    
    text = (
        "✅ <b>Отгрузка сохранена!</b>\n\n"
        f"🆔 <b>ID:</b> {data['shipment_id']}\n"
        f"📊 <b>Статус:</b> RESERVED\n\n"
        "Продукция зарезервирована.\n"
        "Вы можете выполнить отгрузку позже через меню 'Мои отгрузки'."
    )
    
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    
    # Очистка состояния
    await state.clear()


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@shipment_router.callback_query(F.data.in_(["ship_cancel", "ship_cancel_reserve", "cancel"]))
@shipment_router.message(Command("cancel"), StateFilter('*'))
async def cancel_shipment(update: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Отменяет процесс отгрузки.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
    else:
        message = update
    
    # Очистка состояния
    await state.clear()
    
    await message.answer(
        "❌ Отгрузка отменена.",
        reply_markup=get_main_menu_keyboard()
    )



__all__ = ['shipment_router']
