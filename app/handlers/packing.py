"""
Обработчик команд фасовки готовой продукции (aiogram 3.x).

Этот модуль реализует диалоговые сценарии для:
- Выбора полуфабриката из бочек для фасовки
- Выбора варианта упаковки (тара)
- Расчета возможного количества единиц
- Выполнения фасовки с FIFO-логикой
- Учета брака тары и технологических потерь
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from decimal import Decimal
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
from app.utils.logger import get_logger

logger = get_logger("packing_handler")

# Создаём роутер для packing handlers
packing_router = Router(name="packing")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class PackingStates(StatesGroup):
    """Состояния диалога фасовки."""
    select_warehouse = State()
    select_semi_sku = State()
    select_packing_variant = State()
    enter_units_count = State()
    review_calculation = State()
    enter_waste_container = State()
    enter_notes = State()
    confirm_execution = State()


# ============================================================================
# НАЧАЛО ДИАЛОГА ФАСОВКИ
# ============================================================================

@packing_router.message(Command("packing"))
@packing_router.callback_query(F.data == "packing_start")
async def start_packing(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс фасовки готовой продукции.
    
    Команда: /packing или кнопка "Фасовка"
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
    
    # Проверка прав доступа
    if not db_user.can_pack:
        await message.answer(
            "❌ У вас нет прав для фасовки.\n"
            "Обратитесь к администратору."
        )
        return
    
    # Получение списка складов
    try:
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await message.answer(
                "❌ Нет доступных складов.\n"
                "Обратитесь к администратору.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Сохранение начальных данных
        await state.update_data(
            user_id=user.id,
            started_at=datetime.utcnow().isoformat()
        )
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='pack_wh')
        
        text = (
            "📦 <b>Фасовка готовой продукции</b>\n\n"
            "Выберите склад для фасовки:"
        )
        
        if isinstance(update, CallbackQuery):
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        
        await state.set_state(PackingStates.select_warehouse)
        
    except Exception as e:
        logger.error(f"Error in start_packing: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при загрузке складов: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )


# ============================================================================
# ВЫБОР СКЛАДА
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.select_warehouse),
    F.data.startswith("pack_wh_")
)
async def select_warehouse(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор склада и показывает доступные бочки.
    """
    await callback.answer()
    
    # Извлечение ID склада
    warehouse_id = int(callback.data.split('_')[-1])
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        
        # Сохранение выбора
        await state.update_data(
            warehouse_id=warehouse_id,
            warehouse_name=warehouse.name
        )
        
        # Получение бочек с полуфабрикатом
        barrels = await barrel_service.get_barrels_for_packing(
            session,
            warehouse_id=warehouse_id
        )
        
        if not barrels:
            await callback.message.answer(
                "❌ На складе нет бочек с полуфабрикатом для фасовки.\n"
                "Сначала необходимо выполнить производство.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
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
        
        # Сохранение информации (конвертируем Decimal в строки)
        sku_map_serializable = {}
        for sku_id, info in sku_map.items():
            sku_map_serializable[str(sku_id)] = {
                'name': info['name'],
                'unit': info['unit'],
                'total_weight': str(info['total_weight']),
                'barrel_count': info['barrel_count']
            }
        
        await state.update_data(available_skus=sku_map_serializable)
        
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
                    text=button_text,
                    callback_data=f'pack_sku_{sku_id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data='pack_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = (
            f"📦 <b>Склад:</b> {warehouse.name}\n\n"
            "📋 Выберите полуфабрикат для фасовки:"
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(PackingStates.select_semi_sku)
        
    except Exception as e:
        logger.error(f"Error in select_warehouse: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВЫБОР ПОЛУФАБРИКАТА
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.select_semi_sku),
    F.data.startswith("pack_sku_")
)
async def select_semi_sku(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор полуфабриката и показывает варианты упаковки.
    """
    await callback.answer()
    
    # Извлечение ID SKU
    semi_sku_id = int(callback.data.split('_')[-1])
    
    # Получаем данные из FSM
    data = await state.get_data()
    sku_info = data['available_skus'][str(semi_sku_id)]
    
    # Сохранение выбора
    await state.update_data(
        semi_sku_id=semi_sku_id,
        semi_sku_name=sku_info['name'],
        semi_sku_unit=sku_info['unit'],
        available_weight=sku_info['total_weight']
    )
    
    try:
        # Получение вариантов упаковки для этого полуфабриката
        variants = await packing_service.get_packing_variants(
            session,
            semi_sku_id=semi_sku_id,
            active_only=True
        )
        
        if not variants:
            await callback.message.answer(
                f"❌ Нет доступных вариантов упаковки для '{sku_info['name']}'.\n"
                "Обратитесь к администратору для настройки упаковки.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
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
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(PackingStates.select_packing_variant)
        
    except Exception as e:
        logger.error(f"Error in select_semi_sku: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВЫБОР ВАРИАНТА УПАКОВКИ
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.select_packing_variant),
    F.data.startswith("pack_var_")
)
async def select_packing_variant(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор варианта упаковки.
    """
    await callback.answer()
    
    # Извлечение ID варианта упаковки
    variant_id = int(callback.data.split('_')[-1])
    
    try:
        # Загрузка варианта упаковки
        variant = await packing_service.get_packing_variant(session, variant_id)
        
        # Получаем данные
        data = await state.get_data()
        available_weight = Decimal(data['available_weight'])
        
        # Расчет максимально возможного количества
        max_units = int(available_weight / variant.container_weight)
        
        # Сохранение данных
        await state.update_data(
            variant_id=variant_id,
            variant_name=f"{variant.finished_sku.name} ({variant.container_weight} {variant.container_unit})",
            container_weight=str(variant.container_weight),
            container_unit=variant.container_unit,
            finished_sku_name=variant.finished_sku.name,
            finished_sku_unit=variant.finished_sku.unit,
            max_units=max_units
        )
        
        text = (
            f"📦 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
            f"⚖️ <b>Доступно:</b> {available_weight} {data['semi_sku_unit']}\n\n"
            f"📋 <b>Вариант упаковки:</b> {variant.finished_sku.name}\n"
            f"🥫 <b>Вес тары:</b> {variant.container_weight} {variant.container_unit}\n"
            f"📊 <b>Максимум единиц:</b> {max_units} шт\n\n"
            "📝 Введите количество единиц для фасовки:\n\n"
            f"<i>Максимум: {max_units}</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
        await state.set_state(PackingStates.enter_units_count)
        
    except Exception as e:
        logger.error(f"Error in select_packing_variant: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВВОД КОЛИЧЕСТВА ЕДИНИЦ
# ============================================================================

@packing_router.message(StateFilter(PackingStates.enter_units_count), F.text)
async def enter_units_count(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает ввод количества единиц для фасовки.
    """
    user_input = message.text.strip()
    
    # Парсинг целого числа
    units_count = parse_integer_input(user_input)
    
    if units_count is None:
        await message.answer(
            "❌ Некорректный формат числа.\n"
            "Введите целое положительное число.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация положительности
    validation = validate_positive_integer(units_count, min_value=1)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные
    data = await state.get_data()
    max_units = data['max_units']
    
    # Проверка не превышает ли максимум
    if units_count > max_units:
        await message.answer(
            f"❌ Количество ({units_count}) превышает максимум ({max_units}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение количества
    await state.update_data(units_count=units_count)
    
    try:
        # Расчет требуемого веса и проверка доступности
        calculation = await packing_service.calculate_available_for_packing(
            session=session,
            warehouse_id=data['warehouse_id'],
            semi_sku_id=data['semi_sku_id'],
            variant_id=data['variant_id']
        )
        
        container_weight = Decimal(data['container_weight'])
        required_weight = container_weight * units_count
        
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продолжить", callback_data='pack_continue')],
            [InlineKeyboardButton(text="🔄 Изменить количество", callback_data='pack_change_count')],
            [InlineKeyboardButton(text="❌ Отменить", callback_data='pack_cancel')]
        ])
        
        await message.answer(review, reply_markup=keyboard)
        await state.set_state(PackingStates.review_calculation)
        
    except Exception as e:
        logger.error(f"Error in enter_units_count: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при расчете: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ОБРАБОТКА КНОПКИ "ИЗМЕНИТЬ КОЛИЧЕСТВО"
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.enter_units_count, PackingStates.review_calculation),
    F.data == "pack_change_count"
)
async def change_units_count(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает запрос на изменение количества единиц.
    """
    await callback.answer()
    
    data = await state.get_data()
    max_units = data['max_units']
    
    text = (
        "📝 Введите новое количество единиц для фасовки:\n\n"
        f"<i>Максимум: {max_units}</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(PackingStates.enter_units_count)


# ============================================================================
# ПОДТВЕРЖДЕНИЕ НАЧАЛА ФАСОВКИ
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.review_calculation),
    F.data == "pack_continue"
)
async def confirm_continue_packing(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Переходит к запросу данных о браке тары.
    """
    await callback.answer()
    
    text = (
        "🗑 <b>Учет брака тары</b>\n\n"
        "📝 Введите количество единиц брака тары (шт):\n\n"
        "<i>Если брака нет, введите 0</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(PackingStates.enter_waste_container)


# ============================================================================
# ВВОД БРАКА ТАРЫ
# ============================================================================

@packing_router.message(StateFilter(PackingStates.enter_waste_container), F.text)
async def enter_waste_container(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод брака тары.
    """
    user_input = message.text.strip()
    
    # Парсинг целого числа
    waste_container = parse_integer_input(user_input)
    
    if waste_container is None:
        await message.answer(
            "❌ Некорректный формат числа.\n"
            "Введите целое неотрицательное число.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Валидация неотрицательности
    if waste_container < 0:
        await message.answer(
            "❌ Количество брака не может быть отрицательным.\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Получаем данные
    data = await state.get_data()
    units_count = data['units_count']
    
    # Проверка: брак не может превышать количество единиц
    if waste_container > units_count:
        await message.answer(
            f"❌ Брак тары ({waste_container}) не может превышать "
            f"количество единиц ({units_count}).\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение брака
    await state.update_data(waste_container=waste_container)
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания к фасовке (необязательно):\n\n"
        "<i>Любая дополнительная информация</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(PackingStates.enter_notes)


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ
# ============================================================================

@packing_router.message(StateFilter(PackingStates.enter_notes), F.text)
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
    
    container_weight = Decimal(data['container_weight'])
    units_count = data['units_count']
    waste_container = data['waste_container']
    
    required_weight = container_weight * units_count
    net_units = units_count - waste_container
    net_weight = container_weight * net_units
    
    summary = (
        "📋 <b>Подтверждение фасовки</b>\n\n"
        f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📦 <b>Полуфабрикат:</b> {data['semi_sku_name']}\n"
        f"🥫 <b>Упаковка:</b> {data['finished_sku_name']}\n"
        f"⚖️ <b>Вес тары:</b> {data['container_weight']} {data['container_unit']}\n\n"
        f"📊 <b>Фасовка:</b>\n"
        f"   • Количество единиц: {units_count} шт\n"
        f"   • Требуется полуфабриката: {required_weight} {data['semi_sku_unit']}\n"
    )
    
    if waste_container > 0:
        summary += f"   • Брак тары: {waste_container} шт\n"
    
    summary += (
        f"   • Годных единиц: {net_units} шт\n"
        f"   • Чистый вес: {net_weight} {data['container_unit']}\n"
    )
    
    if data.get('notes'):
        summary += f"\n📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить выполнение фасовки?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='pack_execute',
            cancel_callback='pack_cancel'
        )
    )
    
    await state.set_state(PackingStates.confirm_execution)


# ============================================================================
# ВЫПОЛНЕНИЕ ФАСОВКИ
# ============================================================================

@packing_router.callback_query(
    StateFilter(PackingStates.confirm_execution),
    F.data == "pack_execute"
)
async def execute_packing(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Выполняет фасовку: списывает полуфабрикат, создает готовую продукцию.
    """
    await callback.answer("⏳ Выполнение фасовки...")
    
    data = await state.get_data()
    
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
        
        await callback.message.edit_text(report, reply_markup=get_main_menu_keyboard())
        
        # Очистка состояния
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in execute_packing: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при выполнении фасовки:</b>\n\n"
            f"{str(e)}\n\n"
            "Операция отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@packing_router.callback_query(F.data.in_(["pack_cancel", "cancel"]))
@packing_router.message(Command("cancel"), StateFilter('*'))
async def cancel_packing(update: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Отменяет процесс фасовки.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
    else:
        message = update
    
    # Очистка состояния
    await state.clear()
    
    await message.answer(
        "❌ Фасовка отменена.",
        reply_markup=get_main_menu_keyboard()
    )



__all__ = ['packing_router']
