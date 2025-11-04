"""
Обработчик команд отгрузки готовой продукции.

Этот модуль реализует диалоговые сценарии для:
- Создания отгрузок для получателей (контрагентов)
- Добавления позиций готовой продукции
- Резервирования продукции под отгрузку
- Выполнения отгрузки с FIFO-логикой
- Отмены и корректировки отгрузок
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, ShipmentStatus
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


# Состояния диалога
(
    SELECT_ACTION,
    # Создание отгрузки
    SELECT_WAREHOUSE,
    SELECT_RECIPIENT,
    ENTER_SHIPMENT_DATE,
    ENTER_INITIAL_NOTES,
    # Добавление позиций
    SELECT_SKU,
    ENTER_QUANTITY,
    ENTER_PRICE,
    CONFIRM_ADD_ITEM,
    # Завершение и резервирование
    REVIEW_SHIPMENT,
    CONFIRM_RESERVE,
    # Выполнение отгрузки
    CONFIRM_EXECUTION
) = range(13)


# ============================================================================
# НАЧАЛО ДИАЛОГА ОТГРУЗКИ
# ============================================================================

async def start_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс управления отгрузками.
    
    Команда: /shipment или кнопка "Отгрузка"
    """
    query = update.callback_query
    
    # Подтверждение callback
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    # Получение пользователя
    user_id = update.effective_user.id
    user = await session.get(User, user_id)
    
    if not user:
        await message.reply_text(
            "❌ Пользователь не найден. Используйте /start для регистрации."
        )
        return ConversationHandler.END
    
    # Проверка прав доступа
    if not user.can_ship:
        await message.reply_text(
            "❌ У вас нет прав для отгрузки.\n"
            "Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    # Инициализация данных диалога
    context.user_data['shipment'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow(),
        'items': []  # Список позиций отгрузки
    }
    
    # Меню выбора действия
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Создать новую отгрузку", callback_data='ship_create')],
        [InlineKeyboardButton("📋 Мои отгрузки", callback_data='ship_list')],
        [InlineKeyboardButton("❌ Отменить", callback_data='ship_cancel')]
    ])
    
    text = (
        "🚚 <b>Управление отгрузками</b>\n\n"
        "Выберите действие:"
    )
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    return SELECT_ACTION


# ============================================================================
# ВЫБОР ДЕЙСТВИЯ
# ============================================================================

async def select_action_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает создание новой отгрузки.
    """
    query = update.callback_query
    await query.answer()
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение списка складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await query.message.reply_text(
                "❌ Нет доступных складов.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='ship_wh')
        
        text = (
            "🚚 <b>Создание отгрузки</b>\n\n"
            "Выберите склад отгрузки:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_WAREHOUSE
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР СКЛАДА
# ============================================================================

async def select_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор склада.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID склада
    warehouse_id = int(query.data.split('_')[-1])
    context.user_data['shipment']['warehouse_id'] = warehouse_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        context.user_data['shipment']['warehouse_name'] = warehouse.name
        
        # Получение списка получателей
        recipients = await shipment_service.get_recipients(
            session,
            active_only=True,
            limit=50
        )
        
        if not recipients:
            await query.message.reply_text(
                "❌ В системе нет получателей.\n"
                "Обратитесь к администратору для добавления контрагентов.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора получателя
        keyboard = get_recipients_keyboard(
            recipients,
            callback_prefix='ship_rec',
            show_contact=True
        )
        
        text = (
            f"🚚 <b>Склад:</b> {warehouse.name}\n\n"
            "👤 Выберите получателя (контрагента):"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_RECIPIENT
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР ПОЛУЧАТЕЛЯ
# ============================================================================

async def select_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор получателя.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID получателя
    recipient_id = int(query.data.split('_')[-1])
    context.user_data['shipment']['recipient_id'] = recipient_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о получателе
        recipient = await session.get(
            shipment_service.Recipient,
            recipient_id
        )
        context.user_data['shipment']['recipient_name'] = recipient.name
        
        # Запрос даты отгрузки
        today = date.today()
        
        text = (
            f"🚚 <b>Склад:</b> {context.user_data['shipment']['warehouse_name']}\n"
            f"👤 <b>Получатель:</b> {recipient.name}\n\n"
            "📅 Введите дату отгрузки (ДД.ММ.ГГГГ):\n\n"
            f"<i>Сегодня: {today.strftime('%d.%m.%Y')}</i>\n"
            "<i>Или отправьте '-' для использования сегодняшней даты</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return ENTER_SHIPMENT_DATE
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВВОД ДАТЫ ОТГРУЗКИ
# ============================================================================

async def enter_shipment_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод даты отгрузки.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на использование сегодняшней даты
    if user_input == '-':
        shipment_date = date.today()
    else:
        # Парсинг даты
        shipment_date = parse_date_input(user_input)
        
        if shipment_date is None:
            await message.reply_text(
                "❌ Некорректный формат даты.\n"
                "Используйте формат ДД.ММ.ГГГГ\n\n"
                "Примеры: <code>15.12.2024</code>, <code>01.01.2025</code>\n\n"
                "Попробуйте снова:",
                parse_mode='HTML',
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_SHIPMENT_DATE
        
        # Проверка: дата не должна быть слишком далеко в прошлом
        if shipment_date < date.today() - timedelta(days=30):
            await message.reply_text(
                "❌ Дата отгрузки не может быть более 30 дней в прошлом.\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_SHIPMENT_DATE
    
    # Сохранение даты
    context.user_data['shipment']['shipment_date'] = shipment_date
    
    # Запрос примечаний
    text = (
        f"✅ Дата отгрузки: <b>{shipment_date.strftime('%d.%m.%Y')}</b>\n\n"
        "📝 Введите примечания к отгрузке (необязательно):\n\n"
        "<i>Номер заказа, условия доставки и т.д.</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_INITIAL_NOTES


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ К ОТГРУЗКЕ
# ============================================================================

async def enter_initial_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод примечаний и создает отгрузку.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['shipment']['initial_notes'] = None
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_INITIAL_NOTES
        
        context.user_data['shipment']['initial_notes'] = user_input
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['shipment']
    
    try:
        # Создание отгрузки через сервис
        shipment = await shipment_service.create_shipment(
            session=session,
            warehouse_id=data['warehouse_id'],
            recipient_id=data['recipient_id'],
            created_by_id=data['user_id'],
            shipment_date=data['shipment_date'],
            notes=data.get('initial_notes')
        )
        
        # Сохранение ID отгрузки
        context.user_data['shipment']['shipment_id'] = shipment.id
        
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
        
        await message.reply_text(
            success_text,
            parse_mode='HTML'
        )
        
        # Автоматический переход к добавлению позиций
        return await show_add_item_menu(update, context)
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при создании отгрузки: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ДОБАВЛЕНИЕ ПОЗИЦИЙ
# ============================================================================

async def show_add_item_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню добавления позиции.
    """
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение готовой продукции со склада
        from app.database.models import SKUType
        
        warehouse_id = context.user_data['shipment']['warehouse_id']
        
        finished_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.FINISHED,
            active_only=True
        )
        
        if not finished_skus:
            message = update.message if update.message else update.callback_query.message
            await message.reply_text(
                "❌ Нет готовой продукции для отгрузки.\n"
                "Сначала необходимо выполнить фасовку.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора SKU
        keyboard = get_sku_keyboard(
            finished_skus,
            callback_prefix='ship_sku',
            show_stock=True,
            warehouse_id=warehouse_id
        )
        
        # Текущие позиции отгрузки
        items = context.user_data['shipment']['items']
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
        
        message = update.message if update.message else update.callback_query.message
        await message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_SKU
        
    except Exception as e:
        message = update.message if update.message else update.callback_query.message
        await message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


async def select_sku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор готовой продукции.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID SKU
    sku_id = int(query.data.split('_')[-1])
    
    # Проверка: не добавлена ли уже эта позиция
    items = context.user_data['shipment']['items']
    if any(item['sku_id'] == sku_id for item in items):
        await query.message.reply_text(
            "⚠️ Эта позиция уже добавлена в отгрузку.\n"
            "Выберите другую продукцию.",
            reply_markup=get_cancel_keyboard()
        )
        return SELECT_SKU
    
    # Сохранение выбора
    context.user_data['shipment']['current_sku_id'] = sku_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о SKU
        sku = await stock_service.get_sku(session, sku_id)
        context.user_data['shipment']['current_sku_name'] = sku.name
        context.user_data['shipment']['current_sku_unit'] = sku.unit
        
        # Проверка остатков на складе
        warehouse_id = context.user_data['shipment']['warehouse_id']
        availability = await stock_service.calculate_stock_availability(
            session,
            warehouse_id=warehouse_id,
            sku_id=sku_id
        )
        
        context.user_data['shipment']['current_available'] = availability['available']
        
        text = (
            f"📦 <b>Продукция:</b> {sku.name}\n"
            f"📊 <b>Доступно на складе:</b> {availability['available']} {sku.unit}\n\n"
            f"📝 Введите количество для отгрузки ({sku.unit}):\n\n"
            f"<i>Максимум: {availability['available']}</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return ENTER_QUANTITY
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВВОД КОЛИЧЕСТВА
# ============================================================================

async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод количества продукции.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг количества
    quantity = parse_decimal_input(user_input)
    
    if quantity is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_QUANTITY
    
    # Валидация положительности
    validation = validate_positive_decimal(quantity, min_value=Decimal('0.001'))
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_QUANTITY
    
    # Проверка доступности
    available = context.user_data['shipment']['current_available']
    
    if quantity > available:
        await message.reply_text(
            f"❌ Количество ({quantity}) превышает доступный остаток ({available}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_QUANTITY
    
    # Сохранение количества
    context.user_data['shipment']['current_quantity'] = quantity
    
    # Запрос цены
    unit = context.user_data['shipment']['current_sku_unit']
    text = (
        f"✅ Количество: <b>{quantity} {unit}</b>\n\n"
        f"💰 Введите цену за {unit} (необязательно):\n\n"
        "<i>Примеры: 150, 250.50</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_PRICE


# ============================================================================
# ВВОД ЦЕНЫ
# ============================================================================

async def enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод цены и добавляет позицию.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        price = None
    else:
        # Парсинг цены
        price = parse_decimal_input(user_input)
        
        if price is None:
            await message.reply_text(
                "❌ Некорректный формат числа.\n\n"
                "Попробуйте снова или отправьте '-' для пропуска:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_PRICE
        
        # Проверка неотрицательности
        if price < 0:
            await message.reply_text(
                "❌ Цена не может быть отрицательной.\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_PRICE
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['shipment']
    
    try:
        # Добавление позиции через сервис
        item = await shipment_service.add_shipment_item(
            session=session,
            shipment_id=data['shipment_id'],
            sku_id=data['current_sku_id'],
            quantity=data['current_quantity'],
            price_per_unit=price
        )
        
        # Сохранение информации о позиции
        data['items'].append({
            'item_id': item.id,
            'sku_id': data['current_sku_id'],
            'sku_name': data['current_sku_name'],
            'unit': data['current_sku_unit'],
            'quantity': data['current_quantity'],
            'price': price
        })
        
        # Очистка текущих данных позиции
        for key in ['current_sku_id', 'current_sku_name', 'current_sku_unit', 
                    'current_quantity', 'current_available']:
            data.pop(key, None)
        
        # Меню: добавить еще или завершить
        total_value = sum(
            (item['quantity'] * item['price']) if item['price'] else 0
            for item in data['items']
        )
        
        summary = (
            "✅ <b>Позиция добавлена!</b>\n\n"
            f"<b>Добавленные позиции ({len(data['items'])}):</b>\n"
        )
        
        for i, it in enumerate(data['items'], 1):
            summary += f"  {i}. {it['sku_name']}: {it['quantity']} {it['unit']}"
            if it['price']:
                summary += f" × {it['price']} ₽"
            summary += "\n"
        
        if total_value > 0:
            summary += f"\n💵 <b>Общая сумма:</b> {total_value} ₽\n"
        
        summary += "\n❓ Что дальше?"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить еще позицию", callback_data='ship_add_more')],
            [InlineKeyboardButton("✅ Завершить и зарезервировать", callback_data='ship_review')],
            [InlineKeyboardButton("❌ Отменить отгрузку", callback_data='ship_cancel')]
        ])
        
        await message.reply_text(
            summary,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return REVIEW_SHIPMENT
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при добавлении позиции: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ДОБАВЛЕНИЕ ЕЩЕ ПОЗИЦИЙ
# ============================================================================

async def add_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает запрос на добавление еще позиций.
    """
    query = update.callback_query
    await query.answer()
    
    return await show_add_item_menu(update, context)


# ============================================================================
# ПРОСМОТР И РЕЗЕРВИРОВАНИЕ
# ============================================================================

async def review_and_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает сводку отгрузки и предлагает зарезервировать.
    """
    query = update.callback_query
    await query.answer()
    
    data = context.user_data['shipment']
    
    # Формирование сводки
    total_value = sum(
        (item['quantity'] * item['price']) if item['price'] else 0
        for item in data['items']
    )
    
    summary = (
        "📋 <b>Сводка отгрузки</b>\n\n"
        f"🆔 <b>ID:</b> {data['shipment_id']}\n"
        f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
        f"👤 <b>Получатель:</b> {data['recipient_name']}\n"
        f"📅 <b>Дата:</b> {data['shipment_date'].strftime('%d.%m.%Y')}\n\n"
        f"<b>Позиции ({len(data['items'])}):</b>\n"
    )
    
    for i, item in enumerate(data['items'], 1):
        summary += f"  {i}. {item['sku_name']}: {item['quantity']} {item['unit']}"
        if item['price']:
            item_sum = item['quantity'] * item['price']
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
    
    await query.message.edit_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='ship_reserve',
            cancel_callback='ship_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_RESERVE


# ============================================================================
# ПОДТВЕРЖДЕНИЕ РЕЗЕРВИРОВАНИЯ
# ============================================================================

async def confirm_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет резервирование продукции под отгрузку.
    """
    query = update.callback_query
    await query.answer("⏳ Резервирование...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['shipment']
    
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Выполнить отгрузку", callback_data='ship_execute')],
            [InlineKeyboardButton("⏸ Выполнить позже", callback_data='ship_later')],
            [InlineKeyboardButton("❌ Отменить резерв", callback_data='ship_cancel_reserve')]
        ])
        
        await query.message.edit_text(
            success_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return CONFIRM_EXECUTION
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при резервировании:</b>\n\n"
            f"{str(e)}\n\n"
            "Отгрузка осталась в статусе DRAFT.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        context.user_data.pop('shipment', None)
        return ConversationHandler.END


# ============================================================================
# ВЫПОЛНЕНИЕ ОТГРУЗКИ
# ============================================================================

async def execute_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет отгрузку: списывает продукцию со склада.
    """
    query = update.callback_query
    await query.answer("⏳ Выполнение отгрузки...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['shipment']
    
    try:
        # Выполнение отгрузки через сервис
        shipment, movements = await shipment_service.execute_shipment(
            session=session,
            shipment_id=data['shipment_id'],
            user_id=data['user_id'],
            actual_shipment_date=date.today()
        )
        
        # Формирование отчета
        total_value = sum(
            (item['quantity'] * item['price']) if item['price'] else 0
            for item in data['items']
        )
        
        report = (
            "✅ <b>Отгрузка успешно выполнена!</b>\n\n"
            f"🆔 <b>ID:</b> {shipment.id}\n"
            f"🚚 <b>Склад:</b> {data['warehouse_name']}\n"
            f"👤 <b>Получатель:</b> {data['recipient_name']}\n"
            f"📅 <b>Дата:</b> {shipment.shipment_date.strftime('%d.%m.%Y')}\n\n"
            f"📦 <b>Отгружено позиций:</b> {len(data['items'])}\n"
        )
        
        for i, item in enumerate(data['items'], 1):
            report += f"  {i}. {item['sku_name']}: {item['quantity']} {item['unit']}\n"
        
        if total_value > 0:
            report += f"\n💵 <b>Общая сумма:</b> {total_value} ₽\n"
        
        report += (
            f"\n📋 <b>Создано движений:</b> {len(movements)}\n"
            f"📊 <b>Статус:</b> {shipment.status.value}"
        )
        
        await query.message.edit_text(
            report,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистка данных
        context.user_data.pop('shipment', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при выполнении отгрузки:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        context.user_data.pop('shipment', None)
        return ConversationHandler.END


# ============================================================================
# ВЫПОЛНИТЬ ПОЗЖЕ
# ============================================================================

async def execute_later(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет отгрузку для выполнения позже.
    """
    query = update.callback_query
    await query.answer()
    
    data = context.user_data['shipment']
    
    text = (
        "✅ <b>Отгрузка сохранена!</b>\n\n"
        f"🆔 <b>ID:</b> {data['shipment_id']}\n"
        f"📊 <b>Статус:</b> RESERVED\n\n"
        "Продукция зарезервирована.\n"
        "Вы можете выполнить отгрузку позже через меню 'Мои отгрузки'."
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='HTML'
    )
    
    # Очистка данных
    context.user_data.pop('shipment', None)
    
    return ConversationHandler.END


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет процесс отгрузки.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('shipment', None)
    
    await message.reply_text(
        "❌ Отгрузка отменена.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_shipment_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для отгрузки.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('shipment', start_shipment),
            CallbackQueryHandler(start_shipment, pattern='^shipment_start$')
        ],
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(select_action_create, pattern='^ship_create$'),
                CallbackQueryHandler(cancel_shipment, pattern='^ship_cancel$')
            ],
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse, pattern='^ship_wh_\\d+$')
            ],
            SELECT_RECIPIENT: [
                CallbackQueryHandler(select_recipient, pattern='^ship_rec_\\d+$')
            ],
            ENTER_SHIPMENT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_shipment_date)
            ],
            ENTER_INITIAL_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_initial_notes)
            ],
            SELECT_SKU: [
                CallbackQueryHandler(select_sku, pattern='^ship_sku_\\d+$')
            ],
            ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)
            ],
            ENTER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_price)
            ],
            REVIEW_SHIPMENT: [
                CallbackQueryHandler(add_more_items, pattern='^ship_add_more$'),
                CallbackQueryHandler(review_and_reserve, pattern='^ship_review$'),
                CallbackQueryHandler(cancel_shipment, pattern='^ship_cancel$')
            ],
            CONFIRM_RESERVE: [
                CallbackQueryHandler(confirm_reserve, pattern='^ship_reserve$'),
                CallbackQueryHandler(cancel_shipment, pattern='^ship_cancel$')
            ],
            CONFIRM_EXECUTION: [
                CallbackQueryHandler(execute_shipment, pattern='^ship_execute$'),
                CallbackQueryHandler(execute_later, pattern='^ship_later$'),
                CallbackQueryHandler(cancel_shipment, pattern='^ship_cancel_reserve$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_shipment),
            CallbackQueryHandler(cancel_shipment, pattern='^cancel$')
        ],
        name='shipment_conversation',
        persistent=False
    )
