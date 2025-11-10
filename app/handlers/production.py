"""
Обработчик команд производства полуфабрикатов (aiogram 3.x).

Этот модуль реализует диалоговые сценарии для:
- Создания производственных партий
- Выбора технологической карты (рецепта)
- Проверки наличия сырья
- Выполнения замеса с созданием бочек
- Учета отходов и брака
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, ProductionStatus, ApprovalStatus
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
from app.utils.logger import get_logger

logger = get_logger("production_handler")

# Создаём роутер для production handlers
production_router = Router(name="production")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class ProductionStates(StatesGroup):
    """Состояния диалога производства."""
    select_recipe = State()
    enter_batch_size = State()
    review_requirements = State()
    enter_actual_output = State()
    enter_waste_semi = State()
    enter_notes = State()
    confirm_execution = State()


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРОИЗВОДСТВА
# ============================================================================

@production_router.message(Command("production"))
@production_router.callback_query(F.data == "production_start")
async def start_production(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс создания производственной партии.
    
    Команда: /production или кнопка "Производство"
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
    if not db_user.can_produce:
        await message.answer(
            "❌ У вас нет прав для производства.\n"
            "Обратитесь к администратору."
        )
        return

    # Получение склада по умолчанию
    try:
        warehouse = await warehouse_service.get_default_warehouse(session)

        if not warehouse:
            await message.answer(
                "❌ Склад не найден.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Получение активных рецептов
        recipes = await recipe_service.get_recipes(session, active_only=True)

        if not recipes:
            await message.answer(
                "❌ Нет доступных рецептов для производства.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Сохранение данных
        await state.update_data(
            user_id=user.id,
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            started_at=datetime.utcnow().isoformat()
        )

        # Клавиатура выбора рецепта
        keyboard = get_recipes_keyboard(recipes, callback_prefix='prod_recipe')

        text = (
            "🏭 <b>Производство полуфабрикатов</b>\n\n"
            f"🏭 <b>Склад:</b> {warehouse.name}\n\n"
            "📋 Выберите технологическую карту (рецепт):"
        )

        if isinstance(update, CallbackQuery):
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)

        await state.set_state(ProductionStates.select_recipe)

    except Exception as e:
        logger.error(f"Error in start_production: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при загрузке данных: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )


# ============================================================================
# ВЫБОР РЕЦЕПТА
# ============================================================================

@production_router.callback_query(
    StateFilter(ProductionStates.select_recipe),
    F.data.startswith("prod_recipe_")
)
async def select_recipe(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор технологической карты.
    """
    await callback.answer()
    
    # Извлечение ID рецепта
    recipe_id = int(callback.data.split('_')[-1])
    
    try:
        # Загрузка рецепта с компонентами
        recipe = await recipe_service.get_recipe_with_components(session, recipe_id)
        
        # Сохранение данных
        await state.update_data(
            recipe_id=recipe_id,
            recipe_name=recipe.name,
            output_percentage=str(recipe.output_percentage),
            semi_sku_name=recipe.semi_finished_sku.name,
            semi_sku_unit=recipe.semi_finished_sku.unit,
            batch_size_recommended=str(recipe.batch_size)
        )
        
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
        
        await callback.message.edit_text(recipe_text, reply_markup=get_cancel_keyboard())
        await state.set_state(ProductionStates.enter_batch_size)
        
    except Exception as e:
        logger.error(f"Error in select_recipe: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВВОД РАЗМЕРА ЗАМЕСА
# ============================================================================

@production_router.message(StateFilter(ProductionStates.enter_batch_size), F.text)
async def enter_batch_size(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает ввод размера замеса и проверяет наличие сырья.
    """
    user_input = message.text.strip()
    
    # Парсинг количества
    batch_size = parse_decimal_input(user_input)
    
    if batch_size is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Примеры: <code>100</code>, <code>500</code>, <code>1000</code>\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация положительности
    validation = validate_positive_decimal(batch_size, min_value=Decimal('0.1'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные
    data = await state.get_data()
    
    try:
        # Проверка наличия сырья
        availability = await production_service.check_materials_availability(
            session=session,
            recipe_id=data['recipe_id'],
            batch_size=batch_size,
            warehouse_id=data['warehouse_id']
        )
        
        # Сохранение данных
        await state.update_data(
            batch_size=str(batch_size),
            requirements=availability['requirements'],
            all_available=availability['all_available']
        )
        
        # Формирование отчета о наличии
        output_percentage = Decimal(data['output_percentage'])
        expected_output = batch_size * output_percentage / 100
        
        report = (
            f"📊 <b>Проверка наличия сырья</b>\n\n"
            f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
            f"📋 <b>Рецепт:</b> {data['recipe_name']}\n"
            f"⚖️ <b>Размер замеса:</b> {batch_size} кг\n"
            f"📈 <b>Ожидаемый выход:</b> {expected_output} {data['semi_sku_unit']}\n\n"
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
            await state.set_state(ProductionStates.review_requirements)
        else:
            report += (
                "❌ <b>Недостаточно сырья для производства.</b>\n\n"
                "Выберите действие:"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Изменить размер замеса", callback_data='prod_change_size')],
                [InlineKeyboardButton(text="❌ Отменить", callback_data='prod_cancel')]
            ])
            # Остаемся в состоянии enter_batch_size
        
        await message.answer(report, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in enter_batch_size: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при проверке сырья: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ОБРАБОТКА КНОПКИ "ИЗМЕНИТЬ РАЗМЕР"
# ============================================================================

@production_router.callback_query(
    StateFilter(ProductionStates.enter_batch_size),
    F.data == "prod_change_size"
)
async def change_batch_size(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает запрос на изменение размера замеса.
    """
    await callback.answer()
    
    text = (
        "📝 Введите новый размер замеса (кг):\n\n"
        "<i>Примеры: 100, 500, 1000</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    # Остаемся в состоянии enter_batch_size


# ============================================================================
# ПОДТВЕРЖДЕНИЕ НАЧАЛА ПРОИЗВОДСТВА
# ============================================================================

@production_router.callback_query(
    StateFilter(ProductionStates.review_requirements),
    F.data == "prod_start"
)
async def confirm_start_production(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Создает производственную партию и запускает производство.
    """
    await callback.answer("⏳ Создание партии...")
    
    data = await state.get_data()
    
    try:
        # Создание партии через сервис
        batch = await production_service.create_batch(
            session=session,
            warehouse_id=data['warehouse_id'],
            recipe_id=data['recipe_id'],
            batch_size=Decimal(data['batch_size']),
            created_by_id=data['user_id'],
            production_date=date.today()
        )
        
        # Сохранение ID партии
        await state.update_data(
            batch_id=batch.id,
            batch_number=batch.batch_number
        )
        
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
        
        await callback.message.edit_text(success_text)
        
        # Автоматический переход к вводу фактического выхода
        output_percentage = Decimal(data['output_percentage'])
        batch_size = Decimal(data['batch_size'])
        expected_output = batch_size * output_percentage / 100
        
        await callback.message.answer(
            f"📊 <b>Выполнение замеса</b>\n\n"
            f"Ожидаемый выход: {expected_output} {data['semi_sku_unit']}\n\n"
            f"📝 Введите фактический выход полуфабриката ({data['semi_sku_unit']}):\n\n"
            "<i>Примеры: 95, 98.5, 100</i>",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(ProductionStates.enter_actual_output)
        
    except Exception as e:
        logger.error(f"Error in confirm_start_production: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при создании партии:</b>\n\n"
            f"{str(e)}\n\n"
            "Производство отменено.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ВВОД ФАКТИЧЕСКОГО ВЫХОДА
# ============================================================================

@production_router.message(StateFilter(ProductionStates.enter_actual_output), F.text)
async def enter_actual_output(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод фактического выхода полуфабриката.
    """
    user_input = message.text.strip()
    
    # Парсинг количества
    actual_output = parse_decimal_input(user_input)
    
    if actual_output is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация
    validation = validate_positive_decimal(actual_output, min_value=Decimal('0.1'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверка разумности значения
    data = await state.get_data()
    batch_size = Decimal(data['batch_size'])
    output_percentage = Decimal(data['output_percentage'])
    expected_output = batch_size * output_percentage / 100
    
    if actual_output > expected_output * Decimal('1.5'):
        await message.answer(
            f"⚠️ Фактический выход ({actual_output}) значительно превышает "
            f"ожидаемый ({expected_output}).\n\n"
            "Проверьте правильность ввода.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение фактического выхода
    await state.update_data(actual_output=str(actual_output))
    
    # Запрос брака полуфабриката
    text = (
        f"✅ Фактический выход: <b>{actual_output} {data['semi_sku_unit']}</b>\n\n"
        f"📝 Введите количество брака полуфабриката ({data['semi_sku_unit']}):\n\n"
        "<i>Если брака нет, введите 0</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ProductionStates.enter_waste_semi)


# ============================================================================
# ВВОД БРАКА ПОЛУФАБРИКАТА
# ============================================================================

@production_router.message(StateFilter(ProductionStates.enter_waste_semi), F.text)
async def enter_waste_semi(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод брака полуфабриката.
    """
    user_input = message.text.strip()
    
    # Парсинг количества
    waste_semi = parse_decimal_input(user_input)
    
    if waste_semi is None:
        await message.answer(
            "❌ Некорректный формат числа.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация неотрицательности
    if waste_semi < 0:
        await message.answer(
            "❌ Количество брака не может быть отрицательным.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверка: брак не может превышать фактический выход
    data = await state.get_data()
    actual_output = Decimal(data['actual_output'])
    
    if waste_semi > actual_output:
        await message.answer(
            f"❌ Брак ({waste_semi}) не может превышать "
            f"фактический выход ({actual_output}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение брака
    await state.update_data(waste_semi=str(waste_semi))
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания к замесу (необязательно):\n\n"
        "<i>Любая дополнительная информация о процессе производства</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ProductionStates.enter_notes)


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ
# ============================================================================

@production_router.message(StateFilter(ProductionStates.enter_notes), F.text)
async def enter_notes(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод примечаний и показывает подтверждение.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        await state.update_data(notes=None)
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
        
        await state.update_data(notes=user_input)
    
    # Формирование сводки
    data = await state.get_data()
    
    actual_output = Decimal(data['actual_output'])
    waste_semi = Decimal(data['waste_semi'])
    batch_size = Decimal(data['batch_size'])
    output_percentage = Decimal(data['output_percentage'])
    
    net_output = actual_output - waste_semi
    expected_output = batch_size * output_percentage / 100
    efficiency = (net_output / expected_output * 100) if expected_output > 0 else 0
    
    summary = (
        "📋 <b>Подтверждение выполнения замеса</b>\n\n"
        f"🆔 <b>Партия:</b> {data['batch_number']}\n"
        f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📋 <b>Рецепт:</b> {data['recipe_name']}\n"
        f"⚖️ <b>Размер замеса:</b> {batch_size} кг\n\n"
        f"📊 <b>Результаты:</b>\n"
        f"   • Ожидаемый выход: {expected_output} {data['semi_sku_unit']}\n"
        f"   • Фактический выход: {actual_output} {data['semi_sku_unit']}\n"
        f"   • Брак полуфабриката: {waste_semi} {data['semi_sku_unit']}\n"
        f"   • Чистый выход: {net_output} {data['semi_sku_unit']}\n"
        f"   • Эффективность: {efficiency:.1f}%\n"
    )
    
    if data.get('notes'):
        summary += f"\n📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить выполнение замеса?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='prod_execute',
            cancel_callback='prod_cancel'
        )
    )
    
    await state.set_state(ProductionStates.confirm_execution)


# ============================================================================
# ВЫПОЛНЕНИЕ ЗАМЕСА
# ============================================================================

@production_router.callback_query(
    StateFilter(ProductionStates.confirm_execution),
    F.data == "prod_execute"
)
async def execute_production(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Выполняет замес: списывает сырье, создает бочки, учитывает отходы.
    """
    await callback.answer("⏳ Выполнение замеса...")
    
    data = await state.get_data()
    
    try:
        # Выполнение замеса через сервис
        result = await production_service.execute_batch(
            session=session,
            batch_id=data['batch_id'],
            actual_output=Decimal(data['actual_output']),
            waste_semi_finished=Decimal(data['waste_semi']),
            performed_by_id=data['user_id'],
            notes=data.get('notes')
        )
        
        # Формирование отчета
        batch = result['batch']
        barrels = result['barrels']
        movements = result['movements']
        waste_records = result['waste_records']
        
        net_output = Decimal(data['actual_output']) - Decimal(data['waste_semi'])
        
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
        
        if Decimal(data['waste_semi']) > 0:
            report += f"🗑 <b>Брак полуфабриката:</b> {data['waste_semi']} {data['semi_sku_unit']}\n"
        
        report += f"\n📋 <b>Списано сырья:</b> {len([m for m in movements if m.quantity < 0])}\n"
        
        if waste_records:
            report += f"🗑 <b>Учтено отходов:</b> {len(waste_records)}\n"
        
        report += f"\n📊 <b>Статус партии:</b> {batch.status.value}"
        
        await callback.message.edit_text(report, reply_markup=get_main_menu_keyboard())
        
        # Очистка состояния
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in execute_production: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при выполнении замеса:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@production_router.callback_query(F.data.in_(["prod_cancel", "cancel"]))
@production_router.message(Command("cancel"), StateFilter('*'))
async def cancel_production(update: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Отменяет процесс производства.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
    else:
        message = update
    
    # Очистка состояния
    await state.clear()
    
    await message.answer(
        "❌ Производство отменено.",
        reply_markup=get_main_menu_keyboard()
    )



__all__ = ['production_router']

