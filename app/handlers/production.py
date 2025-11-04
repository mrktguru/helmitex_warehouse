"""
Обработчик команд производства полуфабрикатов.

Этот модуль реализует диалоговые сценарии для:
- Создания производственных партий
- Выбора технологической карты (рецепта)
- Проверки наличия сырья
- Выполнения замеса с созданием бочек
- Учета отходов и брака
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, ProductionStatus
from app.services import (
    recipe_service,
    production_service,
    warehouse_service,
    barrel_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_recipes_keyboard,
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
    SELECT_RECIPE,
    ENTER_BATCH_SIZE,
    REVIEW_REQUIREMENTS,
    CONFIRM_START,
    ENTER_ACTUAL_OUTPUT,
    ENTER_WASTE_SEMI,
    ENTER_NOTES,
    CONFIRM_EXECUTION
) = range(9)


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРОИЗВОДСТВА
# ============================================================================

async def start_production(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс создания производственной партии.
    
    Команда: /production или кнопка "Производство"
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
    if not user.can_produce:
        await message.reply_text(
            "❌ У вас нет прав для производства.\n"
            "Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    # Инициализация данных диалога
    context.user_data['production'] = {
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
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='prod_wh')
        
        text = (
            "🏭 <b>Производство полуфабрикатов</b>\n\n"
            "Выберите склад для производства:"
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
    
    # Извлечение ID склада
    warehouse_id = int(query.data.split('_')[-1])
    context.user_data['production']['warehouse_id'] = warehouse_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        context.user_data['production']['warehouse_name'] = warehouse.name
        
        # Получение активных рецептов
        recipes = await recipe_service.get_recipes(
            session,
            active_only=True,
            limit=50
        )
        
        if not recipes:
            await query.message.reply_text(
                "❌ В системе нет активных технологических карт.\n"
                "Обратитесь к администратору для создания рецептов.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора рецепта
        keyboard = get_recipes_keyboard(
            recipes,
            callback_prefix='prod_recipe',
            show_details=True
        )
        
        text = (
            f"🏭 <b>Склад:</b> {warehouse.name}\n\n"
            "📋 Выберите технологическую карту (рецепт):"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_RECIPE
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР РЕЦЕПТА
# ============================================================================

async def select_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор технологической карты.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID рецепта
    recipe_id = int(query.data.split('_')[-1])
    context.user_data['production']['recipe_id'] = recipe_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка рецепта с компонентами
        recipe = await recipe_service.get_recipe_with_components(session, recipe_id)
        
        context.user_data['production']['recipe_name'] = recipe.name
        context.user_data['production']['output_percentage'] = recipe.output_percentage
        context.user_data['production']['semi_sku_name'] = recipe.semi_finished_sku.name
        context.user_data['production']['semi_sku_unit'] = recipe.semi_finished_sku.unit
        
        # Формирование описания рецепта
        recipe_text = (
            f"📋 <b>Рецепт:</b> {recipe.name}\n"
            f"🎯 <b>Результат:</b> {recipe.semi_finished_sku.name}\n"
            f"📊 <b>Выход:</b> {recipe.output_percentage}%\n\n"
            "<b>Компоненты:</b>\n"
        )
        
        for component in recipe.components:
            recipe_text += (
                f"  • {component.raw_sku.name}: "
                f"{component.percentage}% ({component.raw_sku.unit})\n"
            )
        
        recipe_text += (
            f"\n💡 <b>Базовый размер замеса:</b> {recipe.batch_size} кг\n\n"
            "📝 Введите желаемый размер замеса (кг):\n\n"
            "<i>Примеры: 100, 500, 1000</i>\n"
            f"<i>Рекомендуется: {recipe.batch_size}</i>"
        )
        
        await query.message.edit_text(
            recipe_text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return ENTER_BATCH_SIZE
        
    except Exception as e:
        await query.message.reply_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВВОД РАЗМЕРА ЗАМЕСА
# ============================================================================

async def enter_batch_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод размера замеса и проверяет наличие сырья.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг количества
    batch_size = parse_decimal_input(user_input)
    
    if batch_size is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Примеры: <code>100</code>, <code>500</code>, <code>1000</code>\n\n"
            "Попробуйте снова:",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_BATCH_SIZE
    
    # Валидация положительности
    validation = validate_positive_decimal(batch_size, min_value=Decimal('0.1'))
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_BATCH_SIZE
    
    # Сохранение размера замеса
    context.user_data['production']['batch_size'] = batch_size
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Проверка наличия сырья
        recipe_id = context.user_data['production']['recipe_id']
        warehouse_id = context.user_data['production']['warehouse_id']
        
        availability = await production_service.check_materials_availability(
            session=session,
            recipe_id=recipe_id,
            batch_size=batch_size,
            warehouse_id=warehouse_id
        )
        
        # Сохранение данных о требованиях
        context.user_data['production']['requirements'] = availability['requirements']
        context.user_data['production']['all_available'] = availability['all_available']
        
        # Формирование отчета о наличии
        report = (
            f"📊 <b>Проверка наличия сырья</b>\n\n"
            f"🏭 <b>Склад:</b> {context.user_data['production']['warehouse_name']}\n"
            f"📋 <b>Рецепт:</b> {context.user_data['production']['recipe_name']}\n"
            f"⚖️ <b>Размер замеса:</b> {batch_size} кг\n"
            f"📈 <b>Ожидаемый выход:</b> {batch_size * context.user_data['production']['output_percentage'] / 100} "
            f"{context.user_data['production']['semi_sku_unit']}\n\n"
            "<b>Требуемое сырье:</b>\n"
        )
        
        all_ok = True
        for req in availability['requirements']:
            status_icon = "✅" if req['available'] else "❌"
            report += (
                f"{status_icon} <b>{req['sku_name']}:</b>\n"
                f"   Требуется: {req['required']} {req['unit']}\n"
                f"   Доступно: {req['in_stock']} {req['unit']}\n"
            )
            if not req['available']:
                report += f"   ⚠️ Недостаток: {req['shortage']} {req['unit']}\n"
                all_ok = False
            report += "\n"
        
        if all_ok:
            report += "✅ <b>Все сырье в наличии!</b>\n\n❓ Начать производство?"
            
            keyboard = get_confirmation_keyboard(
                confirm_callback='prod_start',
                cancel_callback='prod_cancel'
            )
        else:
            report += (
                "❌ <b>Недостаточно сырья для производства.</b>\n\n"
                "Выберите действие:"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Изменить размер замеса", callback_data='prod_change_size')],
                [InlineKeyboardButton("❌ Отменить", callback_data='prod_cancel')]
            ])
        
        await message.reply_text(
            report,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return REVIEW_REQUIREMENTS if all_ok else ENTER_BATCH_SIZE
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при проверке сырья: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ОБРАБОТКА КНОПКИ "ИЗМЕНИТЬ РАЗМЕР"
# ============================================================================

async def change_batch_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает запрос на изменение размера замеса.
    """
    query = update.callback_query
    await query.answer()
    
    text = (
        "📝 Введите новый размер замеса (кг):\n\n"
        "<i>Примеры: 100, 500, 1000</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_BATCH_SIZE


# ============================================================================
# ПОДТВЕРЖДЕНИЕ НАЧАЛА ПРОИЗВОДСТВА
# ============================================================================

async def confirm_start_production(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Создает производственную партию и запускает производство.
    """
    query = update.callback_query
    await query.answer("⏳ Создание партии...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['production']
    
    try:
        # Создание партии через сервис
        batch = await production_service.create_batch(
            session=session,
            warehouse_id=data['warehouse_id'],
            recipe_id=data['recipe_id'],
            batch_size=data['batch_size'],
            created_by_id=data['user_id'],
            production_date=date.today()
        )
        
        # Сохранение ID партии
        context.user_data['production']['batch_id'] = batch.id
        context.user_data['production']['batch_number'] = batch.batch_number
        
        # Успешное создание
        success_text = (
            "✅ <b>Партия создана!</b>\n\n"
            f"🆔 <b>Номер партии:</b> {batch.batch_number}\n"
            f"📋 <b>Рецепт:</b> {data['recipe_name']}\n"
            f"⚖️ <b>Размер замеса:</b> {data['batch_size']} кг\n"
            f"📅 <b>Дата:</b> {batch.production_date.strftime('%d.%m.%Y')}\n"
            f"📊 <b>Статус:</b> {batch.status.value}\n\n"
            "➡️ Переходим к выполнению замеса..."
        )
        
        await query.message.edit_text(
            success_text,
            parse_mode='HTML'
        )
        
        # Автоматический переход к вводу фактического выхода
        await query.message.reply_text(
            f"📊 <b>Выполнение замеса</b>\n\n"
            f"Ожидаемый выход: {data['batch_size'] * data['output_percentage'] / 100} "
            f"{data['semi_sku_unit']}\n\n"
            f"📝 Введите фактический выход полуфабриката ({data['semi_sku_unit']}):\n\n"
            "<i>Примеры: 95, 98.5, 100</i>",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        
        return ENTER_ACTUAL_OUTPUT
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при создании партии:</b>\n\n"
            f"{str(e)}\n\n"
            "Производство отменено.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        context.user_data.pop('production', None)
        return ConversationHandler.END


# ============================================================================
# ВВОД ФАКТИЧЕСКОГО ВЫХОДА
# ============================================================================

async def enter_actual_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод фактического выхода полуфабриката.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг количества
    actual_output = parse_decimal_input(user_input)
    
    if actual_output is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_ACTUAL_OUTPUT
    
    # Валидация
    validation = validate_positive_decimal(actual_output, min_value=Decimal('0.1'))
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_ACTUAL_OUTPUT
    
    # Проверка разумности значения (не больше 150% от ожидаемого)
    data = context.user_data['production']
    expected_output = data['batch_size'] * data['output_percentage'] / 100
    
    if actual_output > expected_output * Decimal('1.5'):
        await message.reply_text(
            f"⚠️ Фактический выход ({actual_output}) значительно превышает "
            f"ожидаемый ({expected_output}).\n\n"
            "Проверьте правильность ввода.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_ACTUAL_OUTPUT
    
    # Сохранение фактического выхода
    context.user_data['production']['actual_output'] = actual_output
    
    # Запрос брака полуфабриката
    text = (
        f"✅ Фактический выход: <b>{actual_output} {data['semi_sku_unit']}</b>\n\n"
        f"📝 Введите количество брака полуфабриката ({data['semi_sku_unit']}):\n\n"
        "<i>Если брака нет, введите 0</i>"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return ENTER_WASTE_SEMI


# ============================================================================
# ВВОД БРАКА ПОЛУФАБРИКАТА
# ============================================================================

async def enter_waste_semi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод брака полуфабриката.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Парсинг количества
    waste_semi = parse_decimal_input(user_input)
    
    if waste_semi is None:
        await message.reply_text(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_SEMI
    
    # Валидация неотрицательности
    if waste_semi < 0:
        await message.reply_text(
            "❌ Количество брака не может быть отрицательным.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_SEMI
    
    # Проверка: брак не может превышать фактический выход
    actual_output = context.user_data['production']['actual_output']
    
    if waste_semi > actual_output:
        await message.reply_text(
            f"❌ Брак ({waste_semi}) не может превышать "
            f"фактический выход ({actual_output}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return ENTER_WASTE_SEMI
    
    # Сохранение брака
    context.user_data['production']['waste_semi'] = waste_semi
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания к замесу (необязательно):\n\n"
        "<i>Любая дополнительная информация о процессе производства</i>\n"
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
        context.user_data['production']['notes'] = None
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
        
        context.user_data['production']['notes'] = user_input
    
    # Формирование сводки
    data = context.user_data['production']
    
    net_output = data['actual_output'] - data['waste_semi']
    expected_output = data['batch_size'] * data['output_percentage'] / 100
    efficiency = (net_output / expected_output * 100) if expected_output > 0 else 0
    
    summary = (
        "📋 <b>Подтверждение выполнения замеса</b>\n\n"
        f"🆔 <b>Партия:</b> {data['batch_number']}\n"
        f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📋 <b>Рецепт:</b> {data['recipe_name']}\n"
        f"⚖️ <b>Размер замеса:</b> {data['batch_size']} кг\n\n"
        f"📊 <b>Результаты:</b>\n"
        f"   • Ожидаемый выход: {expected_output} {data['semi_sku_unit']}\n"
        f"   • Фактический выход: {data['actual_output']} {data['semi_sku_unit']}\n"
        f"   • Брак полуфабриката: {data['waste_semi']} {data['semi_sku_unit']}\n"
        f"   • Чистый выход: {net_output} {data['semi_sku_unit']}\n"
        f"   • Эффективность: {efficiency:.1f}%\n"
    )
    
    if data.get('notes'):
        summary += f"\n📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить выполнение замеса?"
    
    await message.reply_text(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='prod_execute',
            cancel_callback='prod_cancel'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_EXECUTION


# ============================================================================
# ВЫПОЛНЕНИЕ ЗАМЕСА
# ============================================================================

async def execute_production(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет замес: списывает сырье, создает бочки, учитывает отходы.
    """
    query = update.callback_query
    await query.answer("⏳ Выполнение замеса...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['production']
    
    try:
        # Выполнение замеса через сервис
        result = await production_service.execute_batch(
            session=session,
            batch_id=data['batch_id'],
            actual_output=data['actual_output'],
            waste_semi_finished=data['waste_semi'],
            performed_by_id=data['user_id'],
            notes=data.get('notes')
        )
        
        # Формирование отчета
        batch = result['batch']
        barrels = result['barrels']
        movements = result['movements']
        waste_records = result['waste_records']
        
        net_output = data['actual_output'] - data['waste_semi']
        
        report = (
            "✅ <b>Замес успешно выполнен!</b>\n\n"
            f"🆔 <b>Партия:</b> {batch.batch_number}\n"
            f"📋 <b>Рецепт:</b> {data['recipe_name']}\n"
            f"⚖️ <b>Размер замеса:</b> {data['batch_size']} кг\n\n"
            f"📦 <b>Создано бочек:</b> {len(barrels)}\n"
        )
        
        for i, barrel in enumerate(barrels, 1):
            report += f"   {i}. {barrel.barrel_number}: {barrel.current_weight} кг\n"
        
        report += f"\n📊 <b>Итого полуфабриката:</b> {net_output} {data['semi_sku_unit']}\n"
        
        if data['waste_semi'] > 0:
            report += f"🗑 <b>Брак полуфабриката:</b> {data['waste_semi']} {data['semi_sku_unit']}\n"
        
        report += f"\n📋 <b>Списано сырья:</b> {len([m for m in movements if m.quantity < 0])}\n"
        
        if waste_records:
            report += f"🗑 <b>Учтено отходов:</b> {len(waste_records)}\n"
        
        report += f"\n📊 <b>Статус партии:</b> {batch.status.value}"
        
        await query.message.edit_text(
            report,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        # Очистка данных
        context.user_data.pop('production', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ <b>Ошибка при выполнении замеса:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='HTML'
        )
        
        context.user_data.pop('production', None)
        return ConversationHandler.END


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_production(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет процесс производства.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('production', None)
    
    await message.reply_text(
        "❌ Производство отменено.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_production_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для производства.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('production', start_production),
            CallbackQueryHandler(start_production, pattern='^production_start$')
        ],
        states={
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse, pattern='^prod_wh_\\d+$')
            ],
            SELECT_RECIPE: [
                CallbackQueryHandler(select_recipe, pattern='^prod_recipe_\\d+$')
            ],
            ENTER_BATCH_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_batch_size),
                CallbackQueryHandler(change_batch_size, pattern='^prod_change_size$')
            ],
            REVIEW_REQUIREMENTS: [
                CallbackQueryHandler(confirm_start_production, pattern='^prod_start$'),
                CallbackQueryHandler(cancel_production, pattern='^prod_cancel$')
            ],
            ENTER_ACTUAL_OUTPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_actual_output)
            ],
            ENTER_WASTE_SEMI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_waste_semi)
            ],
            ENTER_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_notes)
            ],
            CONFIRM_EXECUTION: [
                CallbackQueryHandler(execute_production, pattern='^prod_execute$'),
                CallbackQueryHandler(cancel_production, pattern='^prod_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_production),
            CallbackQueryHandler(cancel_production, pattern='^cancel$')
        ],
        name='production_conversation',
        persistent=False
    )
