"""
Административный обработчик управления складами и номенклатурой.

Этот модуль реализует функциональность для:
- Управления складами (создание, редактирование, активация)
- Управления номенклатурой (SKU всех типов)
- Управления технологическими картами (рецептами)
- Управления вариантами упаковки
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

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


# Состояния диалога
(
    ADMIN_MENU,
    # Управление складами
    WAREHOUSE_MENU,
    CREATE_WAREHOUSE_NAME,
    CREATE_WAREHOUSE_ADDRESS,
    CREATE_WAREHOUSE_DESC,
    CONFIRM_CREATE_WAREHOUSE,
    SELECT_WAREHOUSE_EDIT,
    EDIT_WAREHOUSE_MENU,
    # Управление SKU
    SKU_MENU,
    SELECT_SKU_TYPE_CREATE,
    CREATE_SKU_NAME,
    CREATE_SKU_UNIT,
    CREATE_SKU_DESC,
    CONFIRM_CREATE_SKU,
    SELECT_SKU_TYPE_LIST,
    SELECT_SKU_EDIT,
    EDIT_SKU_MENU,
    # Управление рецептами
    RECIPE_MENU,
    CREATE_RECIPE_NAME,
    CREATE_RECIPE_SEMI_SKU,
    CREATE_RECIPE_OUTPUT,
    CREATE_RECIPE_BATCH_SIZE,
    CREATE_RECIPE_DESC,
    ADD_COMPONENT_SELECT_RAW,
    ADD_COMPONENT_PERCENTAGE,
    REVIEW_RECIPE_COMPONENTS,
    CONFIRM_CREATE_RECIPE,
    SELECT_RECIPE_EDIT,
    # Управление вариантами упаковки
    PACKING_VARIANT_MENU,
    CREATE_VARIANT_SEMI,
    CREATE_VARIANT_FINISHED,
    CREATE_VARIANT_WEIGHT,
    CONFIRM_CREATE_VARIANT
) = range(34)


# ============================================================================
# ГЛАВНОЕ АДМИНИСТРАТИВНОЕ МЕНЮ
# ============================================================================

async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает административную сессию.
    
    Команда: /admin
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
    
    # Проверка административных прав
    if not user.is_admin:
        await message.reply_text(
            "❌ У вас нет административных прав.\n"
            "Обратитесь к администратору системы."
        )
        return ConversationHandler.END
    
    # Инициализация данных
    context.user_data['admin'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow()
    }
    
    # Главное меню
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 Склады", callback_data='admin_warehouses')],
        [InlineKeyboardButton("📋 Номенклатура (SKU)", callback_data='admin_sku')],
        [InlineKeyboardButton("🧪 Технологические карты", callback_data='admin_recipes')],
        [InlineKeyboardButton("📦 Варианты упаковки", callback_data='admin_packing_variants')],
        [InlineKeyboardButton("❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "👨‍💼 <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:"
    )
    
    if query:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return ADMIN_MENU


# ============================================================================
# УПРАВЛЕНИЕ СКЛАДАМИ
# ============================================================================

async def warehouse_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню управления складами.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать склад", callback_data='wh_create')],
        [InlineKeyboardButton("📋 Список складов", callback_data='wh_list')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton("❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "🏭 <b>Управление складами</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return WAREHOUSE_MENU


async def create_warehouse_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс создания склада.
    """
    query = update.callback_query
    await query.answer()
    
    # Инициализация данных склада
    context.user_data['admin']['warehouse'] = {}
    
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
    
    return CREATE_WAREHOUSE_NAME


async def create_warehouse_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод названия склада.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_WAREHOUSE_NAME
    
    # Сохранение названия
    context.user_data['admin']['warehouse']['name'] = user_input
    
    text = (
        f"✅ Название: <b>{user_input}</b>\n\n"
        "📍 Введите адрес склада (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_WAREHOUSE_ADDRESS


async def create_warehouse_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод адреса склада.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['admin']['warehouse']['address'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=200)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return CREATE_WAREHOUSE_ADDRESS
        
        context.user_data['admin']['warehouse']['address'] = user_input
    
    text = (
        "📝 Введите описание склада (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_WAREHOUSE_DESC


async def create_warehouse_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод описания и показывает подтверждение.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['admin']['warehouse']['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return CREATE_WAREHOUSE_DESC
        
        context.user_data['admin']['warehouse']['description'] = user_input
    
    # Формирование сводки
    data = context.user_data['admin']['warehouse']
    
    summary = (
        "📋 <b>Подтверждение создания склада</b>\n\n"
        f"🏭 <b>Название:</b> {data['name']}\n"
    )
    
    if data.get('address'):
        summary += f"📍 <b>Адрес:</b> {data['address']}\n"
    
    if data.get('description'):
        summary += f"📝 <b>Описание:</b> {data['description']}\n"
    
    summary += "\n❓ Создать склад?"
    
    await message.reply_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='wh_confirm_create',
            cancel_callback='wh_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_CREATE_WAREHOUSE


async def confirm_create_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Создает склад в базе данных.
    """
    query = update.callback_query
    await query.answer("⏳ Создание склада...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['admin']['warehouse']
    
    try:
        # Создание склада через сервис
        warehouse = await warehouse_service.create_warehouse(
            session=session,
            name=data['name'],
            address=data.get('address'),
            description=data.get('description')
        )
        
        text = (
            "✅ <b>Склад успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {warehouse.id}\n"
            f"🏭 <b>Название:</b> {warehouse.name}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных
        context.user_data['admin'].pop('warehouse', None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать еще", callback_data='wh_create')],
            [InlineKeyboardButton("🔙 К складам", callback_data='admin_warehouses')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return WAREHOUSE_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании склада:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К складам", callback_data='admin_warehouses')]
            ]),
            parse_mode='HTML'
        )
        
        return WAREHOUSE_MENU


async def list_warehouses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список всех складов.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка складов...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение всех складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=False)
        
        if not warehouses:
            text = (
                "📋 <b>Список складов</b>\n\n"
                "❌ Нет созданных складов."
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать склад", callback_data='wh_create')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_warehouses')]
            ])
        else:
            text = (
                f"📋 <b>Список складов ({len(warehouses)})</b>\n\n"
            )
            
            for wh in warehouses:
                status = "✅ Активен" if wh.is_active else "🔒 Неактивен"
                text += f"🏭 <b>{wh.name}</b> - {status}\n"
                if wh.address:
                    text += f"   📍 {wh.address}\n"
                text += f"   🆔 ID: {wh.id}\n\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Редактировать склад", callback_data='wh_edit_select')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_warehouses')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return WAREHOUSE_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_warehouses')]
            ])
        )
        return WAREHOUSE_MENU


# ============================================================================
# УПРАВЛЕНИЕ НОМЕНКЛАТУРОЙ (SKU)
# ============================================================================

async def sku_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню управления номенклатурой.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить SKU", callback_data='sku_create')],
        [InlineKeyboardButton("📋 Список SKU", callback_data='sku_list')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton("❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "📋 <b>Управление номенклатурой</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return SKU_MENU


async def create_sku_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню выбора типа SKU.
    """
    query = update.callback_query
    await query.answer()
    
    # Инициализация данных SKU
    context.user_data['admin']['sku'] = {}
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌾 Сырье", callback_data='sku_type_raw')],
        [InlineKeyboardButton("🛢 Полуфабрикат", callback_data='sku_type_semi')],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data='sku_type_finished')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_sku')],
        [InlineKeyboardButton("❌ Отменить", callback_data='admin_exit')]
    ])
    
    text = (
        "➕ <b>Добавление SKU</b>\n\n"
        "Выберите тип номенклатуры:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return SELECT_SKU_TYPE_CREATE


async def create_sku_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор типа SKU и запрашивает название.
    """
    query = update.callback_query
    await query.answer()
    
    # Определение типа
    callback_data = query.data
    
    if callback_data == 'sku_type_raw':
        sku_type = SKUType.RAW
        type_name = "Сырье"
        type_emoji = "🌾"
    elif callback_data == 'sku_type_semi':
        sku_type = SKUType.SEMI_FINISHED
        type_name = "Полуфабрикат"
        type_emoji = "🛢"
    else:  # finished
        sku_type = SKUType.FINISHED
        type_name = "Готовая продукция"
        type_emoji = "📦"
    
    # Сохранение типа
    context.user_data['admin']['sku']['sku_type'] = sku_type
    context.user_data['admin']['sku']['type_name'] = type_name
    context.user_data['admin']['sku']['type_emoji'] = type_emoji
    
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
    
    return CREATE_SKU_NAME


async def create_sku_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод названия SKU.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_SKU_NAME
    
    # Сохранение названия
    context.user_data['admin']['sku']['name'] = user_input
    
    text = (
        f"✅ Название: <b>{user_input}</b>\n\n"
        "📏 Введите единицу измерения:\n\n"
        "<i>Примеры: кг, литр, шт, ведро, мешок</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_SKU_UNIT


async def create_sku_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод единицы измерения.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=1, max_length=20)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_SKU_UNIT
    
    # Сохранение единицы
    context.user_data['admin']['sku']['unit'] = user_input
    
    text = (
        f"✅ Единица: <b>{user_input}</b>\n\n"
        "📝 Введите описание (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_SKU_DESC


async def create_sku_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод описания и показывает подтверждение.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['admin']['sku']['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return CREATE_SKU_DESC
        
        context.user_data['admin']['sku']['description'] = user_input
    
    # Формирование сводки
    data = context.user_data['admin']['sku']
    
    summary = (
        "📋 <b>Подтверждение создания SKU</b>\n\n"
        f"{data['type_emoji']} <b>Тип:</b> {data['type_name']}\n"
        f"📝 <b>Название:</b> {data['name']}\n"
        f"📏 <b>Единица:</b> {data['unit']}\n"
    )
    
    if data.get('description'):
        summary += f"📝 <b>Описание:</b> {data['description']}\n"
    
    summary += "\n❓ Создать SKU?"
    
    await message.reply_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='sku_confirm_create',
            cancel_callback='sku_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_CREATE_SKU


async def confirm_create_sku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Создает SKU в базе данных.
    """
    query = update.callback_query
    await query.answer("⏳ Создание SKU...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['admin']['sku']
    
    try:
        # Создание SKU через сервис
        sku = await stock_service.create_sku(
            session=session,
            name=data['name'],
            sku_type=data['sku_type'],
            unit=data['unit'],
            description=data.get('description')
        )
        
        text = (
            "✅ <b>SKU успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {sku.id}\n"
            f"{data['type_emoji']} <b>Тип:</b> {data['type_name']}\n"
            f"📝 <b>Название:</b> {sku.name}\n"
            f"📏 <b>Единица:</b> {sku.unit}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных
        context.user_data['admin'].pop('sku', None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить еще", callback_data='sku_create')],
            [InlineKeyboardButton("🔙 К номенклатуре", callback_data='admin_sku')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return SKU_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании SKU:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К номенклатуре", callback_data='admin_sku')]
            ]),
            parse_mode='HTML'
        )
        
        return SKU_MENU


async def list_sku_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню выбора типа для просмотра списка SKU.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌾 Сырье", callback_data='sku_list_raw')],
        [InlineKeyboardButton("🛢 Полуфабрикаты", callback_data='sku_list_semi')],
        [InlineKeyboardButton("📦 Готовая продукция", callback_data='sku_list_finished')],
        [InlineKeyboardButton("📋 Все категории", callback_data='sku_list_all')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_sku')]
    ])
    
    text = (
        "📋 <b>Список номенклатуры</b>\n\n"
        "Выберите категорию:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return SELECT_SKU_TYPE_LIST


async def list_sku_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список SKU по выбранному типу.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка...")
    
    # Определение типа
    callback_data = query.data
    
    if callback_data == 'sku_list_raw':
        sku_type = SKUType.RAW
        type_name = "Сырье"
        type_emoji = "🌾"
    elif callback_data == 'sku_list_semi':
        sku_type = SKUType.SEMI_FINISHED
        type_name = "Полуфабрикаты"
        type_emoji = "🛢"
    elif callback_data == 'sku_list_finished':
        sku_type = SKUType.FINISHED
        type_name = "Готовая продукция"
        type_emoji = "📦"
    else:  # all
        sku_type = None
        type_name = "Вся номенклатура"
        type_emoji = "📋"
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить SKU", callback_data='sku_create')],
                [InlineKeyboardButton("🔙 Назад", callback_data='sku_list')]
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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='sku_list')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return SELECT_SKU_TYPE_LIST
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_sku')]
            ])
        )
        return SKU_MENU


# ============================================================================
# УПРАВЛЕНИЕ ТЕХНОЛОГИЧЕСКИМИ КАРТАМИ
# ============================================================================

async def recipe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню управления рецептами.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать рецепт", callback_data='recipe_create')],
        [InlineKeyboardButton("📋 Список рецептов", callback_data='recipe_list')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_start')],
        [InlineKeyboardButton("❌ Выход", callback_data='admin_exit')]
    ])
    
    text = (
        "🧪 <b>Технологические карты</b>\n\n"
        "Выберите действие:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return RECIPE_MENU


async def create_recipe_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс создания рецепта.
    """
    query = update.callback_query
    await query.answer()
    
    # Инициализация данных рецепта
    context.user_data['admin']['recipe'] = {
        'components': []  # Список компонентов
    }
    
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
    
    return CREATE_RECIPE_NAME


async def create_recipe_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод названия рецепта.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=100)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_RECIPE_NAME
    
    # Сохранение названия
    context.user_data['admin']['recipe']['name'] = user_input
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение полуфабрикатов
        semi_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.SEMI_FINISHED,
            active_only=True
        )
        
        if not semi_skus:
            await message.reply_text(
                "❌ Нет полуфабрикатов в системе.\n"
                "Сначала создайте полуфабрикат через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
                ])
            )
            return RECIPE_MENU
        
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
        
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return CREATE_RECIPE_SEMI_SKU
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        return RECIPE_MENU


async def create_recipe_semi_sku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор полуфабриката.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID полуфабриката
    semi_sku_id = int(query.data.split('_')[-1])
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о SKU
        sku = await stock_service.get_sku(session, semi_sku_id)
        
        context.user_data['admin']['recipe']['semi_sku_id'] = semi_sku_id
        context.user_data['admin']['recipe']['semi_sku_name'] = sku.name
        
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
        
        return CREATE_RECIPE_OUTPUT
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        return RECIPE_MENU


async def create_recipe_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод процента выхода.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг числа
    output_percentage = parse_decimal_input(user_input)
    
    if output_percentage is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_RECIPE_OUTPUT
    
    # Валидация диапазона
    if output_percentage < 50 or output_percentage > 100:
        await message.reply_text(
            "❌ Процент выхода должен быть от 50 до 100.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_RECIPE_OUTPUT
    
    # Сохранение процента
    context.user_data['admin']['recipe']['output_percentage'] = output_percentage
    
    text = (
        f"✅ Процент выхода: <b>{output_percentage}%</b>\n\n"
        "⚖️ Введите базовый размер замеса (кг):\n\n"
        "<i>Рекомендуемое количество сырья для одного замеса</i>\n"
        "<i>Примеры: 100, 500, 1000</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_RECIPE_BATCH_SIZE


async def create_recipe_batch_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод размера замеса.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг числа
    batch_size = parse_decimal_input(user_input)
    
    if batch_size is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_RECIPE_BATCH_SIZE
    
    # Валидация положительности
    validation = validate_positive_decimal(batch_size, min_value=Decimal('1'))
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return CREATE_RECIPE_BATCH_SIZE
    
    # Сохранение размера
    context.user_data['admin']['recipe']['batch_size'] = batch_size
    
    text = (
        f"✅ Размер замеса: <b>{batch_size} кг</b>\n\n"
        "📝 Введите описание рецепта (необязательно):\n\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return CREATE_RECIPE_DESC


async def create_recipe_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод описания и переходит к добавлению компонентов.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        context.user_data['admin']['recipe']['description'] = None
    else:
        # Валидация
        validation = validate_text_length(user_input, max_length=500)
        
        if not validation['valid']:
            await message.reply_text(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return CREATE_RECIPE_DESC
        
        context.user_data['admin']['recipe']['description'] = user_input
    
    # Переход к добавлению компонентов
    return await show_add_component_menu(update, context)


async def show_add_component_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню добавления компонента сырья.
    """
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение сырья
        raw_skus = await stock_service.get_skus_by_type(
            session,
            sku_type=SKUType.RAW,
            active_only=True
        )
        
        if not raw_skus:
            message = update.message if update.message else update.callback_query.message
            await message.reply_text(
                "❌ Нет сырья в системе.\n"
                "Сначала создайте сырье через меню 'Номенклатура'.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
                ])
            )
            return RECIPE_MENU
        
        # Текущие компоненты
        components = context.user_data['admin']['recipe']['components']
        
        components_text = ""
        total_percentage = Decimal('0')
        
        if components:
            components_text = "\n<b>Добавленные компоненты:</b>\n"
            for i, comp in enumerate(components, 1):
                components_text += f"  {i}. {comp['name']}: {comp['percentage']}%\n"
                total_percentage += comp['percentage']
            components_text += f"\n<b>Итого:</b> {total_percentage}%\n"
            
            if total_percentage == 100:
                components_text += "✅ Сумма компонентов = 100%\n"
            else:
                components_text += f"⚠️ Осталось: {100 - total_percentage}%\n"
            
            components_text += "\n"
        
        # Клавиатура выбора сырья
        keyboard = get_sku_keyboard(
            raw_skus,
            callback_prefix='recipe_comp',
            show_stock=False
        )
        
        text = (
            "🌾 <b>Добавление компонентов</b>\n"
            f"{components_text}"
            "Выберите сырье для добавления:"
        )
        
        message = update.message if update.message else update.callback_query.message
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return ADD_COMPONENT_SELECT_RAW
        
    except Exception as e:
        message = update.message if update.message else update.callback_query.message
        await message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        return RECIPE_MENU


async def add_component_select_raw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор сырья для компонента.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID сырья
    raw_sku_id = int(query.data.split('_')[-1])
    
    # Проверка: не добавлено ли уже это сырье
    components = context.user_data['admin']['recipe']['components']
    if any(comp['raw_sku_id'] == raw_sku_id for comp in components):
        await query.message.reply_text(
            "⚠️ Это сырье уже добавлено в рецепт.\n"
            "Выберите другое.",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_COMPONENT_SELECT_RAW
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о сырье
        sku = await stock_service.get_sku(session, raw_sku_id)
        
        context.user_data['admin']['recipe']['current_component'] = {
            'raw_sku_id': raw_sku_id,
            'name': sku.name
        }
        
        # Расчет оставшегося процента
        total_percentage = sum(comp['percentage'] for comp in components)
        remaining = 100 - total_percentage
        
        text = (
            f"✅ Сырье: <b>{sku.name}</b>\n\n"
            f"📊 Осталось: <b>{remaining}%</b>\n\n"
            "Введите процент этого компонента:\n\n"
            f"<i>Максимум: {remaining}</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return ADD_COMPONENT_PERCENTAGE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
            ])
        )
        return RECIPE_MENU


async def add_component_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод процента компонента.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг числа
    percentage = parse_decimal_input(user_input)
    
    if percentage is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_COMPONENT_PERCENTAGE
    
    # Валидация диапазона
    if percentage <= 0 or percentage > 100:
        await message.reply_text(
            "❌ Процент должен быть от 0.01 до 100.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_COMPONENT_PERCENTAGE
    
    # Проверка суммы
    components = context.user_data['admin']['recipe']['components']
    total_percentage = sum(comp['percentage'] for comp in components) + percentage
    
    if total_percentage > 100:
        remaining = 100 - sum(comp['percentage'] for comp in components)
        await message.reply_text(
            f"❌ Сумма компонентов превысит 100%.\n"
            f"Осталось: {remaining}%\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ADD_COMPONENT_PERCENTAGE
    
    # Добавление компонента
    current_component = context.user_data['admin']['recipe']['current_component']
    current_component['percentage'] = percentage
    
    components.append(current_component)
    
    # Очистка текущего компонента
    context.user_data['admin']['recipe'].pop('current_component', None)
    
    # Проверка: достигли ли 100%
    if total_percentage == 100:
        return await review_recipe_components(update, context)
    else:
        # Меню: добавить еще или завершить
        remaining = 100 - total_percentage
        
        summary = (
            "✅ <b>Компонент добавлен!</b>\n\n"
            f"<b>Компоненты ({len(components)}):</b>\n"
        )
        
        for i, comp in enumerate(components, 1):
            summary += f"  {i}. {comp['name']}: {comp['percentage']}%\n"
        
        summary += f"\n<b>Итого:</b> {total_percentage}%\n"
        summary += f"<b>Осталось:</b> {remaining}%\n\n"
        summary += "❓ Что дальше?"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить еще компонент", callback_data='recipe_add_more_comp')],
            [InlineKeyboardButton("✅ Завершить (недостает до 100%)", callback_data='recipe_review_comp')],
            [InlineKeyboardButton("❌ Отменить", callback_data='recipe_cancel')]
        ])
        
        await message.reply_text(summary, reply_markup=keyboard, parse_mode='HTML')
        
        return REVIEW_RECIPE_COMPONENTS


async def add_more_components(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Продолжает добавление компонентов.
    """
    query = update.callback_query
    await query.answer()
    
    return await show_add_component_menu(update, context)


async def review_recipe_components(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает финальную сводку рецепта для подтверждения.
    """
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    data = context.user_data['admin']['recipe']
    components = data['components']
    
    # Проверка суммы компонентов
    total_percentage = sum(comp['percentage'] for comp in components)
    
    if total_percentage != 100:
        text = (
            "⚠️ <b>Предупреждение!</b>\n\n"
            f"Сумма компонентов: {total_percentage}%\n"
            "Рекомендуется 100%.\n\n"
            "Вы уверены, что хотите создать рецепт с неполной суммой?"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить компоненты", callback_data='recipe_add_more_comp')],
            [InlineKeyboardButton("✅ Создать как есть", callback_data='recipe_confirm_create')],
            [InlineKeyboardButton("❌ Отменить", callback_data='recipe_cancel')]
        ])
    else:
        # Формирование финальной сводки
        summary = (
            "📋 <b>Подтверждение создания рецепта</b>\n\n"
            f"📝 <b>Название:</b> {data['name']}\n"
            f"🛢 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
            f"📊 <b>Выход:</b> {data['output_percentage']}%\n"
            f"⚖️ <b>Размер замеса:</b> {data['batch_size']} кг\n\n"
            f"<b>Компоненты ({len(components)}):</b>\n"
        )
        
        for i, comp in enumerate(components, 1):
            summary += f"  {i}. {comp['name']}: {comp['percentage']}%\n"
        
        summary += f"\n<b>Итого:</b> {total_percentage}% ✅\n"
        
        if data.get('description'):
            summary += f"\n📝 <b>Описание:</b> {data['description']}\n"
        
        summary += "\n❓ Создать рецепт?"
        
        text = summary
        keyboard = get_confirmation_keyboard(
            confirm_callback='recipe_confirm_create',
            cancel_callback='recipe_cancel'
        )
    
    if update.callback_query:
        await message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return CONFIRM_CREATE_RECIPE


async def confirm_create_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Создает рецепт в базе данных.
    """
    query = update.callback_query
    await query.answer("⏳ Создание рецепта...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['admin']['recipe']
    
    try:
        # Создание рецепта через сервис
        recipe = await recipe_service.create_recipe(
            session=session,
            name=data['name'],
            semi_finished_sku_id=data['semi_sku_id'],
            output_percentage=data['output_percentage'],
            batch_size=data['batch_size'],
            description=data.get('description')
        )
        
        # Добавление компонентов
        for component_data in data['components']:
            await recipe_service.add_recipe_component(
                session=session,
                recipe_id=recipe.id,
                raw_sku_id=component_data['raw_sku_id'],
                percentage=component_data['percentage']
            )
        
        text = (
            "✅ <b>Рецепт успешно создан!</b>\n\n"
            f"🆔 <b>ID:</b> {recipe.id}\n"
            f"📝 <b>Название:</b> {recipe.name}\n"
            f"🛢 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
            f"📊 <b>Выход:</b> {recipe.output_percentage}%\n"
            f"⚖️ <b>Размер замеса:</b> {recipe.batch_size} кг\n"
            f"🧪 <b>Компонентов:</b> {len(data['components'])}\n"
            f"📊 <b>Статус:</b> Активен"
        )
        
        # Очистка данных
        context.user_data['admin'].pop('recipe', None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать еще", callback_data='recipe_create')],
            [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='admin_start')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return RECIPE_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании рецепта:</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К рецептам", callback_data='admin_recipes')]
            ]),
            parse_mode='HTML'
        )
        
        return RECIPE_MENU


async def list_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список всех рецептов.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка рецептов...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение рецептов
        recipes = await recipe_service.get_recipes(session, active_only=False, limit=100)
        
        if not recipes:
            text = (
                "📋 <b>Список рецептов</b>\n\n"
                "❌ Нет созданных рецептов."
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать рецепт", callback_data='recipe_create')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_recipes')]
            ])
        else:
            text = f"📋 <b>Список рецептов ({len(recipes)})</b>\n\n"
            
            for recipe in recipes:
                status = "✅" if recipe.is_active else "🔒"
                text += f"{status} <b>{recipe.name}</b>\n"
                text += f"   🛢 Результат: {recipe.semi_finished_sku.name}\n"
                text += f"   📊 Выход: {recipe.output_percentage}%\n"
                text += f"   ⚖️ Замес: {recipe.batch_size} кг\n"
                text += f"   🧪 Компонентов: {len(recipe.components)}\n"
                text += f"   🆔 ID: {recipe.id}\n\n"
            
            # Разбивка если слишком длинное
            if len(text) > 4000:
                text = text[:3900] + "\n\n<i>... список слишком длинный</i>"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_recipes')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return RECIPE_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_recipes')]
            ])
        )
        return RECIPE_MENU


# ============================================================================
# ОТМЕНА И ВЫХОД
# ============================================================================

async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет административную операцию.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('admin', None)
    
    await message.reply_text(
        "✅ Административная сессия завершена.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_admin_warehouse_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для административной панели.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('admin', start_admin),
            CallbackQueryHandler(start_admin, pattern='^admin_panel_start$')
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(warehouse_menu, pattern='^admin_warehouses$'),
                CallbackQueryHandler(sku_menu, pattern='^admin_sku$'),
                CallbackQueryHandler(recipe_menu, pattern='^admin_recipes$'),
                CallbackQueryHandler(start_admin, pattern='^admin_start$'),
                CallbackQueryHandler(cancel_admin, pattern='^admin_exit$')
            ],
            # Склады
            WAREHOUSE_MENU: [
                CallbackQueryHandler(create_warehouse_start, pattern='^wh_create$'),
                CallbackQueryHandler(list_warehouses, pattern='^wh_list$'),
                CallbackQueryHandler(start_admin, pattern='^admin_start$'),
                CallbackQueryHandler(cancel_admin, pattern='^admin_exit$')
            ],
            CREATE_WAREHOUSE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_warehouse_name)
            ],
            CREATE_WAREHOUSE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_warehouse_address)
            ],
            CREATE_WAREHOUSE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_warehouse_desc)
            ],
            CONFIRM_CREATE_WAREHOUSE: [
                CallbackQueryHandler(confirm_create_warehouse, pattern='^wh_confirm_create$'),
                CallbackQueryHandler(warehouse_menu, pattern='^wh_cancel$')
            ],
            # SKU
            SKU_MENU: [
                CallbackQueryHandler(create_sku_select_type, pattern='^sku_create$'),
                CallbackQueryHandler(list_sku_select_type, pattern='^sku_list$'),
                CallbackQueryHandler(start_admin, pattern='^admin_start$'),
                CallbackQueryHandler(cancel_admin, pattern='^admin_exit$')
            ],
            SELECT_SKU_TYPE_CREATE: [
                CallbackQueryHandler(create_sku_type_selected, pattern='^sku_type_'),
                CallbackQueryHandler(sku_menu, pattern='^admin_sku$'),
                CallbackQueryHandler(cancel_admin, pattern='^admin_exit$')
            ],
            CREATE_SKU_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_sku_name)
            ],
            CREATE_SKU_UNIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_sku_unit)
            ],
            CREATE_SKU_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_sku_desc)
            ],
            CONFIRM_CREATE_SKU: [
                CallbackQueryHandler(confirm_create_sku, pattern='^sku_confirm_create$'),
                CallbackQueryHandler(sku_menu, pattern='^sku_cancel$')
            ],
            SELECT_SKU_TYPE_LIST: [
                CallbackQueryHandler(list_sku_by_type, pattern='^sku_list_'),
                CallbackQueryHandler(sku_menu, pattern='^admin_sku$')
            ],
            # Рецепты
            RECIPE_MENU: [
                CallbackQueryHandler(create_recipe_start, pattern='^recipe_create$'),
                CallbackQueryHandler(list_recipes, pattern='^recipe_list$'),
                CallbackQueryHandler(start_admin, pattern='^admin_start$'),
                CallbackQueryHandler(cancel_admin, pattern='^admin_exit$')
            ],
            CREATE_RECIPE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_recipe_name)
            ],
            CREATE_RECIPE_SEMI_SKU: [
                CallbackQueryHandler(create_recipe_semi_sku, pattern='^recipe_semi_\\d+$')
            ],
            CREATE_RECIPE_OUTPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_recipe_output)
            ],
            CREATE_RECIPE_BATCH_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_recipe_batch_size)
            ],
            CREATE_RECIPE_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_recipe_desc)
            ],
            ADD_COMPONENT_SELECT_RAW: [
                CallbackQueryHandler(add_component_select_raw, pattern='^recipe_comp_\\d+$')
            ],
            ADD_COMPONENT_PERCENTAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_component_percentage)
            ],
            REVIEW_RECIPE_COMPONENTS: [
                CallbackQueryHandler(add_more_components, pattern='^recipe_add_more_comp$'),
                CallbackQueryHandler(review_recipe_components, pattern='^recipe_review_comp$'),
                CallbackQueryHandler(recipe_menu, pattern='^recipe_cancel$')
            ],
            CONFIRM_CREATE_RECIPE: [
                CallbackQueryHandler(confirm_create_recipe, pattern='^recipe_confirm_create$'),
                CallbackQueryHandler(add_more_components, pattern='^recipe_add_more_comp$'),
                CallbackQueryHandler(recipe_menu, pattern='^recipe_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_admin),
            CallbackQueryHandler(cancel_admin, pattern='^cancel$')
        ],
        name='admin_warehouse_conversation',
        persistent=False
    )
