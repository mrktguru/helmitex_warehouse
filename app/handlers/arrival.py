"""
Обработчик команд приемки сырья на склад.

Этот модуль реализует диалоговые сценарии для:
- Выбора склада и сырья
- Ввода количества и цены
- Указания поставщика и документов
- Подтверждения и выполнения приемки
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal, InvalidOperation
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SKUType, User
from app.services import warehouse_service, stock_service
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_sku_keyboard,
    get_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import (
    validate_positive_decimal,
    validate_text_length,
    parse_decimal_input
)


# Состояния диалога
(
    SELECT_WAREHOUSE,
    SELECT_SKU,
    ENTER_QUANTITY,
    ENTER_PRICE,
    ENTER_SUPPLIER,
    ENTER_DOCUMENT,
    ENTER_NOTES,
    CONFIRM_ARRIVAL
) = range(8)


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРИЕМКИ
# ============================================================================

async def start_arrival(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс приемки сырья.
    
    Команда: /arrival или кнопка "Приемка сырья"
    """
    query = update.callback_query
    
    # Подтверждение callback если это callback_query
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
    if not user.can_receive_materials:
        await message.reply_text(
            "❌ У вас нет прав для приемки сырья.\n"
            "Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    # Инициализация данных диалога
    context.user_data['arrival'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow()
    }
    
    # Получение списка складов
    try:
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await message.reply_text(
                "❌ Нет доступных складов.\n"
                "Обратитесь к администратору для создания склада.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='arrival_wh')
        
        text = (
            "📦 <b>Приемка сырья на склад</b>\n\n"
            "Выберите склад для приемки:"
        )
        
        await message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_WAREHOUSE
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при загрузке складов: {str(e)}",
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
    
    # Извлечение ID склада из callback_data
    callback_data = query.data
    warehouse_id = int(callback_data.split('_')[-1])
    
    # Сохранение выбора
    context.user_data['arrival']['warehouse_id'] = warehouse_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    # Загрузка информации о складе
    try:
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        context.user_data['arrival']['warehouse_name'] = warehouse.name
        
        # Получение списка сырья
        skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.RAW,
            active_only=True
        )
        
        if not skus:
            await query.message.reply_text(
                "❌ В системе нет сырья для приемки.\n"
                "Обратитесь к администратору для добавления номенклатуры.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора сырья
        keyboard = get_sku_keyboard(
            skus,
            callback_prefix='arrival_sku',
            show_stock=False
        )
        
        text = (
            f"📦 <b>Склад:</b> {warehouse.name}\n\n"
            "📋 Выберите принимаемое сырье:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_SKU
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР СЫРЬЯ
# ============================================================================

async def select_sku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор сырья.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID SKU
    callback_data = query.data
    sku_id = int(callback_data.split('_')[-1])
    
    # Сохранение выбора
    context.user_data['arrival']['sku_id'] = sku_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    # Загрузка информации о SKU
    try:
        sku = await stock_service.get_sku(session, sku_id)
        context.user_data['arrival']['sku_name'] = sku.name
        context.user_data['arrival']['sku_unit'] = sku.unit
        
        # Текущий остаток на складе
        warehouse_id = context.user_data['arrival']['warehouse_id']
        current_stock = await stock_service.get_stock_quantity(
            session,
            warehouse_id=warehouse_id,
            sku_id=sku_id
        )
        
        text = (
            f"📦 <b>Склад:</b> {context.user_data['arrival']['warehouse_name']}\n"
            f"📋 <b>Сырье:</b> {sku.name}\n"
            f"📊 <b>Текущий остаток:</b> {current_stock} {sku.unit}\n\n"
            f"📝 Введите количество для приемки ({sku.unit}):\n\n"
            "<i>Примеры: 100, 50.5, 1000</i>"
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
    Обрабатывает ввод количества.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг и валидация числа
    quantity = parse_decimal_input(user_input)
    
    if quantity is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n"
            "Используйте точку или запятую в качестве разделителя.\n\n"
            "Примеры: <code>100</code>, <code>50.5</code>, <code>1000</code>\n\n"
            "Попробуйте снова:",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_QUANTITY
    
    # Проверка положительности
    validation = validate_positive_decimal(quantity, min_value=Decimal('0.001'))
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_QUANTITY
    
    # Сохранение количества
    context.user_data['arrival']['quantity'] = quantity
    
    # Запрос цены
    sku_unit = context.user_data['arrival']['sku_unit']
    text = (
        f"✅ Количество: <b>{quantity} {sku_unit}</b>\n\n"
        f"💰 Введите цену за {sku_unit} (необязательно):\n\n"
        "<i>Примеры: 1500, 2450.50</i>\n"
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
    Обрабатывает ввод цены.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['arrival']['price_per_unit'] = None
    else:
        # Парсинг цены
        price = parse_decimal_input(user_input)
        
        if price is None:
            await message.reply_text(
                "❌ Некорректный формат числа.\n\n"
                "Примеры: <code>1500</code>, <code>2450.50</code>\n"
                "Или отправьте <code>-</code> для пропуска\n\n"
                "Попробуйте снова:",
                parse_mode='HTML',
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
        
        context.user_data['arrival']['price_per_unit'] = price
    
    # Запрос поставщика
    text = (
        "🏢 Введите название поставщика (необязательно):\n\n"
        "<i>Например: ООО \"Химпром\", ИП Иванов</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_SUPPLIER


# ============================================================================
# ВВОД ПОСТАВЩИКА
# ============================================================================

async def enter_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод поставщика.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['arrival']['supplier'] = None
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=200)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_SUPPLIER
        
        context.user_data['arrival']['supplier'] = user_input
    
    # Запрос номера документа
    text = (
        "📄 Введите номер документа (необязательно):\n\n"
        "<i>Например: ТТН-12345, Накладная №567</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_DOCUMENT


# ============================================================================
# ВВОД НОМЕРА ДОКУМЕНТА
# ============================================================================

async def enter_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод номера документа.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['arrival']['document_number'] = None
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=100)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_DOCUMENT
        
        context.user_data['arrival']['document_number'] = user_input
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания (необязательно):\n\n"
        "<i>Любая дополнительная информация о приемке</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_NOTES


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ
# ============================================================================

async def enter_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод примечаний и показывает подтверждение.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['arrival']['notes'] = None
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return ENTER_NOTES
        
        context.user_data['arrival']['notes'] = user_input
    
    # Формирование сводки для подтверждения
    data = context.user_data['arrival']
    
    summary = (
        "📋 <b>Подтверждение приемки</b>\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📋 <b>Сырье:</b> {data['sku_name']}\n"
        f"📊 <b>Количество:</b> {data['quantity']} {data['sku_unit']}\n"
    )
    
    if data.get('price_per_unit'):
        total_cost = data['quantity'] * data['price_per_unit']
        summary += (
            f"💰 <b>Цена за {data['sku_unit']}:</b> {data['price_per_unit']} ₽\n"
            f"💵 <b>Общая стоимость:</b> {total_cost} ₽\n"
        )
    
    if data.get('supplier'):
        summary += f"🏢 <b>Поставщик:</b> {data['supplier']}\n"
    
    if data.get('document_number'):
        summary += f"📄 <b>Документ:</b> {data['document_number']}\n"
    
    if data.get('notes'):
        summary += f"📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить приемку?"
    
    await message.reply_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='arrival_confirm',
            cancel_callback='arrival_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_ARRIVAL


# ============================================================================
# ПОДТВЕРЖДЕНИЕ И ВЫПОЛНЕНИЕ
# ============================================================================

async def confirm_arrival(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет приемку сырья после подтверждения.
    """
    query = update.callback_query
    await query.answer()
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    # Данные приемки
    data = context.user_data['arrival']
    
    try:
        # Выполнение приемки через сервис
        stock, movement = await stock_service.receive_materials(
            session=session,
            warehouse_id=data['warehouse_id'],
            sku_id=data['sku_id'],
            quantity=data['quantity'],
            price_per_unit=data.get('price_per_unit'),
            supplier=data.get('supplier'),
            document_number=data.get('document_number'),
            received_by_id=data['user_id'],
            notes=data.get('notes')
        )
        
        # Успешное завершение
        success_text = (
            "✅ <b>Приемка успешно выполнена!</b>\n\n"
            f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
            f"📋 <b>Сырье:</b> {data['sku_name']}\n"
            f"📊 <b>Принято:</b> {data['quantity']} {data['sku_unit']}\n"
            f"📈 <b>Новый остаток:</b> {stock.quantity} {data['sku_unit']}\n\n"
            f"🆔 <b>ID движения:</b> {movement.id}"
        )
        
        await query.message.edit_text(
            success_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистка данных диалога
        context.user_data.pop('arrival', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при выполнении приемки:</b>\n\n"
            f"{str(e)}\n\n"
            "Приемка отменена.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистка данных
        context.user_data.pop('arrival', None)
        
        return ConversationHandler.END


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_arrival(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет процесс приемки.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('arrival', None)
    
    await message.reply_text(
        "❌ Приемка отменена.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_arrival_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для приемки сырья.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('arrival', start_arrival),
            CallbackQueryHandler(start_arrival, pattern='^arrival_start$')
        ],
        states={
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse, pattern='^arrival_wh_\\d+$')
            ],
            SELECT_SKU: [
                CallbackQueryHandler(select_sku, pattern='^arrival_sku_\\d+$')
            ],
            ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)
            ],
            ENTER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_price)
            ],
            ENTER_SUPPLIER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_supplier)
            ],
            ENTER_DOCUMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_document)
            ],
            ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_notes)
            ],
            CONFIRM_ARRIVAL: [
                CallbackQueryHandler(confirm_arrival, pattern='^arrival_confirm$'),
                CallbackQueryHandler(cancel_arrival, pattern='^arrival_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_arrival),
            CallbackQueryHandler(cancel_arrival, pattern='^cancel$')
        ],
        name='arrival_conversation',
        persistent=False
    )
