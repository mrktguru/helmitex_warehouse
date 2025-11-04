"""
Обработчик команд фасовки готовой продукции.

Этот модуль реализует диалоговые сценарии для:
- Выбора полуфабриката из бочек для фасовки
- Выбора варианта упаковки (тара)
- Расчета возможного количества единиц
- Выполнения фасовки с FIFO-логикой
- Учета брака тары и технологических потерь
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.services import (
    packing_service,
    barrel_service,
    warehouse_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_barrels_keyboard,
    get_packing_variants_keyboard,
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
    SELECT_WAREHOUSE,
    SELECT_SEMI_SKU,
    SELECT_PACKING_VARIANT,
    ENTER_UNITS_COUNT,
    REVIEW_CALCULATION,
    CONFIRM_PACKING,
    ENTER_WASTE_CONTAINER,
    ENTER_NOTES,
    CONFIRM_EXECUTION
) = range(9)


# ============================================================================
# НАЧАЛО ДИАЛОГА ФАСОВКИ
# ============================================================================

async def start_packing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс фасовки готовой продукции.
    
    Команда: /packing или кнопка "Фасовка"
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
    if not user.can_pack:
        await message.reply_text(
            "❌ У вас нет прав для фасовки.\n"
            "Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    # Инициализация данных диалога
    context.user_data['packing'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow()
    }
    
    # Получение списка складов
    try:
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await message.reply_text(
                "❌ Нет доступных складов.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='pack_wh')
        
        text = (
            "📦 <b>Фасовка готовой продукции</b>\n\n"
            "Выберите склад для фасовки:"
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
    Обрабатывает выбор склада и показывает доступные бочки.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID склада
    warehouse_id = int(query.data.split('_')[-1])
    context.user_data['packing']['warehouse_id'] = warehouse_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        context.user_data['packing']['warehouse_name'] = warehouse.name
        
        # Получение бочек с полуфабрикатом
        barrels = await barrel_service.get_barrels_for_packing(
            session,
            warehouse_id=warehouse_id
        )
        
        if not barrels:
            await query.message.reply_text(
                "❌ На складе нет бочек с полуфабрикатом для фасовки.\n"
                "Сначала необходимо выполнить производство.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Группировка бочек по SKU
        sku_map = {}
        for barrel in barrels:
            sku_id = barrel.semi_sku_id
            sku_name = barrel.semi_sku.name
            
            if sku_id not in sku_map:
                sku_map[sku_id] = {
                    'name': sku_name,
                    'unit': barrel.semi_sku.unit,
                    'total_weight': Decimal('0'),
                    'barrel_count': 0
                }
            
            sku_map[sku_id]['total_weight'] += barrel.current_weight
            sku_map[sku_id]['barrel_count'] += 1
        
        # Сохранение информации о доступных SKU
        context.user_data['packing']['available_skus'] = sku_map
        
        # Создание клавиатуры выбора полуфабриката
        keyboard_buttons = []
        for sku_id, info in sku_map.items():
            button_text = (
                f"{info['name']} "
                f"({info['total_weight']} {info['unit']}, "
                f"{info['barrel_count']} бочек)"
            )
            keyboard_buttons.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f'pack_sku_{sku_id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("❌ Отменить", callback_data='pack_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text = (
            f"📦 <b>Склад:</b> {warehouse.name}\n\n"
            "📋 Выберите полуфабрикат для фасовки:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_SEMI_SKU
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР ПОЛУФАБРИКАТА
# ============================================================================

async def select_semi_sku(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор полуфабриката и показывает варианты упаковки.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID SKU
    semi_sku_id = int(query.data.split('_')[-1])
    context.user_data['packing']['semi_sku_id'] = semi_sku_id
    
    # Информация о выбранном SKU
    sku_info = context.user_data['packing']['available_skus'][semi_sku_id]
    context.user_data['packing']['semi_sku_name'] = sku_info['name']
    context.user_data['packing']['semi_sku_unit'] = sku_info['unit']
    context.user_data['packing']['available_weight'] = sku_info['total_weight']
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение вариантов упаковки для этого полуфабриката
        variants = await packing_service.get_packing_variants(
            session,
            semi_sku_id=semi_sku_id,
            active_only=True
        )
        
        if not variants:
            await query.message.reply_text(
                f"❌ Нет доступных вариантов упаковки для '{sku_info['name']}'.\n"
                "Обратитесь к администратору для настройки упаковки.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора варианта упаковки
        keyboard = get_packing_variants_keyboard(
            variants,
            callback_prefix='pack_var',
            show_details=True
        )
        
        text = (
            f"📦 <b>Полуфабрикат:</b> {sku_info['name']}\n"
            f"⚖️ <b>Доступно:</b> {sku_info['total_weight']} {sku_info['unit']}\n"
            f"🛢 <b>Бочек:</b> {sku_info['barrel_count']}\n\n"
            "📋 Выберите вариант упаковки:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_PACKING_VARIANT
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР ВАРИАНТА УПАКОВКИ
# ============================================================================

async def select_packing_variant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор варианта упаковки.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID варианта упаковки
    variant_id = int(query.data.split('_')[-1])
    context.user_data['packing']['variant_id'] = variant_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка варианта упаковки
        variant = await packing_service.get_packing_variant(session, variant_id)
        
        context.user_data['packing']['variant_name'] = (
            f"{variant.finished_sku.name} ({variant.container_weight} {variant.container_unit})"
        )
        context.user_data['packing']['container_weight'] = variant.container_weight
        context.user_data['packing']['container_unit'] = variant.container_unit
        context.user_data['packing']['finished_sku_name'] = variant.finished_sku.name
        context.user_data['packing']['finished_sku_unit'] = variant.finished_sku.unit
        
        # Расчет максимально возможного количества
        available_weight = context.user_data['packing']['available_weight']
        max_units = int(available_weight / variant.container_weight)
        
        context.user_data['packing']['max_units'] = max_units
        
        text = (
            f"📦 <b>Полуфабрикат:</b> {context.user_data['packing']['semi_sku_name']}\n"
            f"⚖️ <b>Доступно:</b> {available_weight} {context.user_data['packing']['semi_sku_unit']}\n\n"
            f"📋 <b>Вариант упаковки:</b> {variant.finished_sku.name}\n"
            f"🥫 <b>Вес тары:</b> {variant.container_weight} {variant.container_unit}\n"
            f"📊 <b>Максимум единиц:</b> {max_units} шт\n\n"
            "📝 Введите количество единиц для фасовки:\n\n"
            f"<i>Максимум: {max_units}</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return ENTER_UNITS_COUNT
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВВОД КОЛИЧЕСТВА ЕДИНИЦ
# ============================================================================

async def enter_units_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод количества единиц для фасовки.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг целого числа
    units_count = parse_integer_input(user_input)
    
    if units_count is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n"
            "Введите целое положительное число.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_UNITS_COUNT
    
    # Валидация положительности
    validation = validate_positive_integer(units_count, min_value=1)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_UNITS_COUNT
    
    # Проверка не превышает ли максимум
    max_units = context.user_data['packing']['max_units']
    
    if units_count > max_units:
        await message.reply_text(
            f"❌ Количество ({units_count}) превышает максимум ({max_units}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_UNITS_COUNT
    
    # Сохранение количества
    context.user_data['packing']['units_count'] = units_count
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Расчет требуемого веса и проверка доступности
        data = context.user_data['packing']
        
        calculation = await packing_service.calculate_available_for_packing(
            session=session,
            warehouse_id=data['warehouse_id'],
            semi_sku_id=data['semi_sku_id'],
            variant_id=data['variant_id']
        )
        
        required_weight = data['container_weight'] * units_count
        
        # Формирование отчета
        review = (
            "📊 <b>Расчет фасовки</b>\n\n"
            f"📦 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
            f"🥫 <b>Упаковка:</b> {data['finished_sku_name']}\n"
            f"📦 <b>Вес тары:</b> {data['container_weight']} {data['container_unit']}\n\n"
            f"📊 <b>Количество единиц:</b> {units_count} шт\n"
            f"⚖️ <b>Требуется полуфабриката:</b> {required_weight} {data['semi_sku_unit']}\n"
            f"✅ <b>Доступно:</b> {calculation['available_weight']} {data['semi_sku_unit']}\n"
            f"🛢 <b>Будет использовано бочек:</b> ~{calculation['barrels_count']}\n\n"
            "➡️ Продолжить?"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Продолжить", callback_data='pack_continue')],
            [InlineKeyboardButton("🔄 Изменить количество", callback_data='pack_change_count')],
            [InlineKeyboardButton("❌ Отменить", callback_data='pack_cancel')]
        ])
        
        await message.reply_text(
            review,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return REVIEW_CALCULATION
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при расчете: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ОБРАБОТКА КНОПКИ "ИЗМЕНИТЬ КОЛИЧЕСТВО"
# ============================================================================

async def change_units_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает запрос на изменение количества единиц.
    """
    query = update.callback_query
    await query.answer()
    
    max_units = context.user_data['packing']['max_units']
    
    text = (
        "📝 Введите новое количество единиц для фасовки:\n\n"
        f"<i>Максимум: {max_units}</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_UNITS_COUNT


# ============================================================================
# ПОДТВЕРЖДЕНИЕ НАЧАЛА ФАСОВКИ
# ============================================================================

async def confirm_continue_packing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Переходит к запросу данных о браке тары.
    """
    query = update.callback_query
    await query.answer()
    
    text = (
        "🗑 <b>Учет брака тары</b>\n\n"
        "📝 Введите количество единиц брака тары (шт):\n\n"
        "<i>Если брака нет, введите 0</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_WASTE_CONTAINER


# ============================================================================
# ВВОД БРАКА ТАРЫ
# ============================================================================

async def enter_waste_container(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод брака тары.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг целого числа
    waste_container = parse_integer_input(user_input)
    
    if waste_container is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n"
            "Введите целое неотрицательное число.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_CONTAINER
    
    # Валидация неотрицательности
    if waste_container < 0:
        await message.reply_text(
            "❌ Количество брака не может быть отрицательным.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_CONTAINER
    
    # Проверка: брак не может превышать количество единиц
    units_count = context.user_data['packing']['units_count']
    
    if waste_container > units_count:
        await message.reply_text(
            f"❌ Брак тары ({waste_container}) не может превышать "
            f"количество единиц ({units_count}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_CONTAINER
    
    # Сохранение брака
    context.user_data['packing']['waste_container'] = waste_container
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания к фасовке (необязательно):\n\n"
        "<i>Любая дополнительная информация</i>\n"
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
        context.user_data['packing']['notes'] = None
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
        
        context.user_data['packing']['notes'] = user_input
    
    # Формирование сводки
    data = context.user_data['packing']
    
    required_weight = data['container_weight'] * data['units_count']
    net_units = data['units_count'] - data['waste_container']
    net_weight = data['container_weight'] * net_units
    
    summary = (
        "📋 <b>Подтверждение фасовки</b>\n\n"
        f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📦 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
        f"🥫 <b>Упаковка:</b> {data['finished_sku_name']}\n"
        f"⚖️ <b>Вес тары:</b> {data['container_weight']} {data['container_unit']}\n\n"
        f"📊 <b>Фасовка:</b>\n"
        f"   • Количество единиц: {data['units_count']} шт\n"
        f"   • Требуется полуфабриката: {required_weight} {data['semi_sku_unit']}\n"
    )
    
    if data['waste_container'] > 0:
        summary += f"   • Брак тары: {data['waste_container']} шт\n"
    
    summary += (
        f"   • Годных единиц: {net_units} шт\n"
        f"   • Чистый вес: {net_weight} {data['container_unit']}\n"
    )
    
    if data.get('notes'):
        summary += f"\n📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить выполнение фасовки?"
    
    await message.reply_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='pack_execute',
            cancel_callback='pack_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_EXECUTION


# ============================================================================
# ВЫПОЛНЕНИЕ ФАСОВКИ
# ============================================================================

async def execute_packing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет фасовку: списывает полуфабрикат, создает готовую продукцию.
    """
    query = update.callback_query
    await query.answer("⏳ Выполнение фасовки...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['packing']
    
    try:
        # Выполнение фасовки через сервис
        result = await packing_service.execute_packing(
            session=session,
            warehouse_id=data['warehouse_id'],
            variant_id=data['variant_id'],
            units_count=data['units_count'],
            waste_container_units=data['waste_container'],
            packed_by_id=data['user_id'],
            packing_date=date.today(),
            notes=data.get('notes')
        )
        
        # Формирование отчета
        finished_stock = result['finished_stock']
        barrels_used = result['barrels_used']
        movements = result['movements']
        waste_records = result['waste_records']
        
        net_units = data['units_count'] - data['waste_container']
        
        report = (
            "✅ <b>Фасовка успешно выполнена!</b>\n\n"
            f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
            f"📦 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
            f"🥫 <b>Готовая продукция:</b> {data['finished_sku_name']}\n\n"
            f"📊 <b>Результаты:</b>\n"
            f"   • Упаковано единиц: {data['units_count']} шт\n"
        )
        
        if data['waste_container'] > 0:
            report += f"   • Брак тары: {data['waste_container']} шт\n"
        
        report += (
            f"   • Годных единиц: {net_units} шт\n"
            f"   • Использовано бочек: {len(barrels_used)}\n"
        )
        
        # Информация об использованных бочках
        if barrels_used:
            report += "\n🛢 <b>Использованные бочки:</b>\n"
            for barrel_info in barrels_used[:5]:  # Показываем первые 5
                report += f"   • {barrel_info['barrel_number']}: {barrel_info['weight_used']} кг\n"
            
            if len(barrels_used) > 5:
                report += f"   ... и еще {len(barrels_used) - 5}\n"
        
        report += f"\n📦 <b>Остаток готовой продукции:</b> {finished_stock.quantity} {data['finished_sku_unit']}"
        
        if waste_records:
            report += f"\n🗑 <b>Учтено отходов:</b> {len(waste_records)}"
        
        await query.message.edit_text(
            report,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистка данных
        context.user_data.pop('packing', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при выполнении фасовки:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        context.user_data.pop('packing', None)
        return ConversationHandler.END


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_packing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет процесс фасовки.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('packing', None)
    
    await message.reply_text(
        "❌ Фасовка отменена.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_packing_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для фасовки.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('packing', start_packing),
            CallbackQueryHandler(start_packing, pattern='^packing_start$')
        ],
        states={
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse, pattern='^pack_wh_\\d+$')
            ],
            SELECT_SEMI_SKU: [
                CallbackQueryHandler(select_semi_sku, pattern='^pack_sku_\\d+$')
            ],
            SELECT_PACKING_VARIANT: [
                CallbackQueryHandler(select_packing_variant, pattern='^pack_var_\\d+$')
            ],
            ENTER_UNITS_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_units_count),
                CallbackQueryHandler(change_units_count, pattern='^pack_change_count$')
            ],
            REVIEW_CALCULATION: [
                CallbackQueryHandler(confirm_continue_packing, pattern='^pack_continue$'),
                CallbackQueryHandler(change_units_count, pattern='^pack_change_count$'),
                CallbackQueryHandler(cancel_packing, pattern='^pack_cancel$')
            ],
            ENTER_WASTE_CONTAINER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_waste_container)
            ],
            ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_notes)
            ],
            CONFIRM_EXECUTION: [
                CallbackQueryHandler(execute_packing, pattern='^pack_execute$'),
                CallbackQueryHandler(cancel_packing, pattern='^pack_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_packing),
            CallbackQueryHandler(cancel_packing, pattern='^cancel$')
        ],
        name='packing_conversation',
        persistent=False
    )
