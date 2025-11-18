"""
Обработчик команд приемки сырья на склад (aiogram 3.x).

Этот модуль реализует диалоговые сценарии для:
- Выбора склада и сырья
- Ввода количества и цены
- Указания поставщика и документов
- Подтверждения и выполнения приемки
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import SKUType, User, ApprovalStatus, Category, SKU as SKUModel, Stock
from app.services import warehouse_service, stock_service
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_sku_keyboard,
    get_categories_keyboard,
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

logger = get_logger("arrival_handler")

# Создаём роутер для arrival handlers
arrival_router = Router(name="arrival")


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_unit_display(unit_value: str) -> str:
    """Преобразует значение единицы измерения в читаемый формат."""
    unit_map = {
        'kg': 'кг',
        'liters': 'л',
        'grams': 'г',
        'pieces': 'шт'
    }
    return unit_map.get(unit_value, unit_value)


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class ArrivalStates(StatesGroup):
    """Состояния диалога приемки сырья."""
    select_category = State()
    select_sku = State()
    enter_quantity = State()
    enter_price = State()
    enter_supplier = State()
    enter_document = State()
    enter_notes = State()
    confirm_arrival = State()


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРИЕМКИ
# ============================================================================

@arrival_router.message(Command("arrival"))
@arrival_router.callback_query(F.data == "arrival_start")
async def start_arrival(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс приемки сырья.
    
    Команда: /arrival или кнопка "Приемка сырья"
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
    if not db_user.can_receive_materials:
        await message.answer(
            "❌ У вас нет прав для приемки сырья.\n"
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

        # Получение списка категорий с сырьем
        stmt = select(Category).order_by(Category.sort_order, Category.name)
        result = await session.execute(stmt)
        categories = result.scalars().all()

        if not categories:
            await message.answer(
                "❌ В системе нет категорий сырья.\n"
                "Обратитесь к администратору для добавления категорий.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Получение количества сырья в каждой категории
        from sqlalchemy import func
        stmt = select(SKUModel.category_id, func.count(SKUModel.id)).where(
            SKUModel.category_id.in_([c.id for c in categories]),
            SKUModel.type == SKUType.raw,
            SKUModel.is_active == True
        ).group_by(SKUModel.category_id)
        result = await session.execute(stmt)
        stats_dict = {category_id: count for category_id, count in result.all()}

        # Фильтруем категории, оставляем только те, где есть сырье
        categories_with_raw = [c for c in categories if c.id in stats_dict and stats_dict[c.id] > 0]

        if not categories_with_raw:
            await message.answer(
                "❌ В системе нет сырья для приемки.\n"
                "Обратитесь к администратору для добавления номенклатуры.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Сохранение данных в FSM
        await state.update_data(
            user_id=user.id,
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            started_at=datetime.utcnow().isoformat()
        )

        # Клавиатура выбора категории
        keyboard = get_categories_keyboard(
            categories_with_raw,
            stats_dict=stats_dict,
            prefix='arrival_category'
        )

        text = (
            "📦 <b>Приемка сырья на склад</b>\n\n"
            f"🏭 <b>Склад:</b> {warehouse.name}\n\n"
            "📂 Выберите категорию сырья:"
        )

        if isinstance(update, CallbackQuery):
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)

        await state.set_state(ArrivalStates.select_category)

    except Exception as e:
        logger.error(f"Error in start_arrival: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при загрузке данных: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )


# ============================================================================
# ВЫБОР КАТЕГОРИИ
# ============================================================================

@arrival_router.callback_query(
    StateFilter(ArrivalStates.select_category),
    F.data.startswith("arrival_category_")
)
async def select_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор категории и показывает сырье из неё.
    """
    await callback.answer()

    # Извлечение ID категории
    category_id = int(callback.data.split('_')[-1])

    # Получение категории
    stmt = select(Category).where(Category.id == category_id)
    result = await session.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    # Получение сырья из этой категории
    stmt = select(SKUModel).where(
        SKUModel.category_id == category_id,
        SKUModel.type == SKUType.raw,
        SKUModel.is_active == True
    ).order_by(SKUModel.name)
    result = await session.execute(stmt)
    skus = result.scalars().all()

    if not skus:
        await callback.answer(
            f"❌ В категории '{category.name}' нет активного сырья",
            show_alert=True
        )
        return

    # Сохранение ID категории
    await state.update_data(category_id=category_id, category_name=category.name)

    # Получаем данные из FSM
    data = await state.get_data()
    warehouse_name = data['warehouse_name']

    # Клавиатура выбора сырья (кнопка "Назад" возвращает к выбору категорий)
    keyboard = get_sku_keyboard(
        skus,
        prefix='arrival_sku',
        back_callback='arrival_back_to_categories'
    )

    text = (
        "📦 <b>Приемка сырья на склад</b>\n\n"
        f"🏭 <b>Склад:</b> {warehouse_name}\n"
        f"📂 <b>Категория:</b> {category.name}\n\n"
        "📋 Выберите принимаемое сырье:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(ArrivalStates.select_sku)


# ============================================================================
# ВЫБОР СЫРЬЯ
# ============================================================================

@arrival_router.callback_query(
    StateFilter(ArrivalStates.select_sku),
    F.data.startswith("arrival_sku_")
)
async def select_sku(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор сырья.
    """
    await callback.answer()
    
    # Извлечение ID SKU
    sku_id = int(callback.data.split('_')[-1])

    # Загрузка информации о SKU
    try:
        # Получение SKU напрямую из базы
        stmt = select(SKUModel).where(SKUModel.id == sku_id)
        result = await session.execute(stmt)
        sku = result.scalar_one_or_none()

        if not sku:
            await callback.answer("❌ Товар не найден", show_alert=True)
            return

        # Получаем данные из FSM
        data = await state.get_data()
        warehouse_id = data['warehouse_id']
        warehouse_name = data['warehouse_name']

        # Сохранение выбора
        await state.update_data(
            sku_id=sku_id,
            sku_name=sku.name,
            sku_unit=sku.unit.value  # Используем .value для получения строки из enum
        )

        # Текущий остаток на складе - прямой запрос к БД
        stmt = select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.sku_id == sku_id
        )
        result = await session.execute(stmt)
        stock = result.scalar_one_or_none()
        current_stock = stock.quantity if stock else 0.0

        # Преобразуем UnitType в читаемый формат
        unit_display = get_unit_display(sku.unit.value)

        text = (
            f"📦 <b>Склад:</b> {warehouse_name}\n"
            f"📋 <b>Сырье:</b> {sku.name}\n"
            f"📊 <b>Текущий остаток:</b> {current_stock} {unit_display}\n\n"
            f"📝 Введите количество для приемки ({unit_display}):\n\n"
            "<i>Примеры: 100, 50.5, 1000</i>"
        )

        await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
        await state.set_state(ArrivalStates.enter_quantity)
        
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

@arrival_router.message(StateFilter(ArrivalStates.enter_quantity), F.text)
async def enter_quantity(
    message: Message,
    state: FSMContext
) -> None:
    """
    Обрабатывает ввод количества.
    """
    user_input = message.text.strip()
    
    # Парсинг и валидация числа
    quantity = parse_decimal_input(user_input)
    
    if quantity is None:
        await message.answer(
            "❌ Некорректный формат числа.\n"
            "Используйте точку или запятую в качестве разделителя.\n\n"
            "Примеры: <code>100</code>, <code>50.5</code>, <code>1000</code>\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверка положительности
    validation = validate_positive_decimal(quantity, min_value=Decimal('0.001'))
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение количества
    await state.update_data(quantity=str(quantity))

    # Получаем единицу измерения
    data = await state.get_data()
    sku_unit = data['sku_unit']
    unit_display = get_unit_display(sku_unit)

    # Запрос цены
    text = (
        f"✅ Количество: <b>{quantity} {unit_display}</b>\n\n"
        f"💰 Введите цену за {unit_display} (необязательно):\n\n"
        "<i>Примеры: 1500, 2450.50</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ArrivalStates.enter_price)


# ============================================================================
# ВВОД ЦЕНЫ
# ============================================================================

@arrival_router.message(StateFilter(ArrivalStates.enter_price), F.text)
async def enter_price(
    message: Message,
    state: FSMContext
) -> None:
    """
    Обрабатывает ввод цены.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        await state.update_data(price_per_unit=None)
    else:
        # Парсинг цены
        price = parse_decimal_input(user_input)
        
        if price is None:
            await message.answer(
                "❌ Некорректный формат числа.\n\n"
                "Примеры: <code>1500</code>, <code>2450.50</code>\n"
                "Или отправьте <code>-</code> для пропуска\n\n"
                "Попробуйте снова:",
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
        
        await state.update_data(price_per_unit=str(price))
    
    # Запрос поставщика
    text = (
        "🏢 Введите название поставщика (необязательно):\n\n"
        "<i>Например: ООО \"Химпром\", ИП Иванов</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ArrivalStates.enter_supplier)


# ============================================================================
# ВВОД ПОСТАВЩИКА
# ============================================================================

@arrival_router.message(StateFilter(ArrivalStates.enter_supplier), F.text)
async def enter_supplier(
    message: Message,
    state: FSMContext
) -> None:
    """
    Обрабатывает ввод поставщика.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        await state.update_data(supplier=None)
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=200)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        await state.update_data(supplier=user_input)
    
    # Запрос номера документа
    text = (
        "📄 Введите номер документа (необязательно):\n\n"
        "<i>Например: ТТН-12345, Накладная №567</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ArrivalStates.enter_document)


# ============================================================================
# ВВОД НОМЕРА ДОКУМЕНТА
# ============================================================================

@arrival_router.message(StateFilter(ArrivalStates.enter_document), F.text)
async def enter_document(
    message: Message,
    state: FSMContext
) -> None:
    """
    Обрабатывает ввод номера документа.
    """
    user_input = message.text.strip()
    
    # Проверка на пропуск
    if user_input == '-':
        await state.update_data(document_number=None)
    else:
        # Валидация длины
        validation = validate_text_length(user_input, max_length=100)
        
        if not validation['valid']:
            await message.answer(
                f"❌ {validation['error']}\n\n"
                "Попробуйте снова:",
                reply_markup=get_cancel_keyboard()
            )
            return
        
        await state.update_data(document_number=user_input)
    
    # Запрос примечаний
    text = (
        "📝 Введите примечания (необязательно):\n\n"
        "<i>Любая дополнительная информация о приемке</i>\n"
        "<i>Или отправьте '-' для пропуска</i>"
    )
    
    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(ArrivalStates.enter_notes)


# ============================================================================
# ВВОД ПРИМЕЧАНИЙ
# ============================================================================

@arrival_router.message(StateFilter(ArrivalStates.enter_notes), F.text)
async def enter_notes(
    message: Message,
    state: FSMContext
) -> None:
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
    
    # Получаем все данные для подтверждения
    data = await state.get_data()

    # Формирование сводки
    quantity = Decimal(data['quantity'])
    unit_display = get_unit_display(data['sku_unit'])

    summary = (
        "📋 <b>Подтверждение приемки</b>\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📋 <b>Сырье:</b> {data['sku_name']}\n"
        f"📊 <b>Количество:</b> {quantity} {unit_display}\n"
    )

    if data.get('price_per_unit'):
        price = Decimal(data['price_per_unit'])
        total_cost = quantity * price
        summary += (
            f"💰 <b>Цена за {unit_display}:</b> {price} ₽\n"
            f"💵 <b>Общая стоимость:</b> {total_cost} ₽\n"
        )
    
    if data.get('supplier'):
        summary += f"🏢 <b>Поставщик:</b> {data['supplier']}\n"
    
    if data.get('document_number'):
        summary += f"📄 <b>Документ:</b> {data['document_number']}\n"
    
    if data.get('notes'):
        summary += f"📝 <b>Примечания:</b> {data['notes']}\n"
    
    summary += "\n❓ Подтвердить приемку?"
    
    await message.answer(
        summary,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='arrival_confirm',
            cancel_callback='arrival_cancel'
        )
    )
    
    await state.set_state(ArrivalStates.confirm_arrival)


# ============================================================================
# ПОДТВЕРЖДЕНИЕ И ВЫПОЛНЕНИЕ
# ============================================================================

@arrival_router.callback_query(
    StateFilter(ArrivalStates.confirm_arrival),
    F.data == "arrival_confirm"
)
async def confirm_arrival(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Выполняет приемку сырья после подтверждения.
    """
    await callback.answer()
    
    # Получаем данные из FSM
    data = await state.get_data()
    
    try:
        # Конвертируем строки обратно в Decimal
        quantity = Decimal(data['quantity'])
        price_per_unit = Decimal(data['price_per_unit']) if data.get('price_per_unit') else None
        
        # Выполнение приемки через сервис
        stock, movement = await stock_service.receive_materials(
            session=session,
            warehouse_id=data['warehouse_id'],
            sku_id=data['sku_id'],
            quantity=quantity,
            price_per_unit=price_per_unit,
            supplier=data.get('supplier'),
            document_number=data.get('document_number'),
            received_by_id=data['user_id'],
            notes=data.get('notes')
        )
        
        # Успешное завершение
        unit_display = get_unit_display(data['sku_unit'])
        success_text = (
            "✅ <b>Приемка успешно выполнена!</b>\n\n"
            f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
            f"📋 <b>Сырье:</b> {data['sku_name']}\n"
            f"📊 <b>Принято:</b> {quantity} {unit_display}\n"
            f"📈 <b>Новый остаток:</b> {stock.quantity} {unit_display}\n\n"
            f"🆔 <b>ID движения:</b> {movement.id}"
        )
        
        await callback.message.edit_text(
            success_text,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Очистка состояния
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in confirm_arrival: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при выполнении приемки:</b>\n\n"
            f"{str(e)}\n\n"
            "Приемка отменена.",
            reply_markup=get_main_menu_keyboard()
        )
        
        await state.clear()


# ============================================================================
# ВОЗВРАТ К КАТЕГОРИЯМ
# ============================================================================

@arrival_router.callback_query(
    F.data == "arrival_back_to_categories",
    StateFilter(ArrivalStates.select_sku)
)
async def back_to_categories(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Возврат к выбору категорий сырья.
    """
    await callback.answer()

    # Получение данных из FSM
    data = await state.get_data()
    warehouse_name = data['warehouse_name']

    # Получение списка категорий с сырьем
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    result = await session.execute(stmt)
    categories = result.scalars().all()

    # Получение количества сырья в каждой категории
    from sqlalchemy import func
    stmt = select(SKUModel.category_id, func.count(SKUModel.id)).where(
        SKUModel.category_id.in_([c.id for c in categories]),
        SKUModel.type == SKUType.raw,
        SKUModel.is_active == True
    ).group_by(SKUModel.category_id)
    result = await session.execute(stmt)
    stats_dict = {category_id: count for category_id, count in result.all()}

    # Фильтруем категории, оставляем только те, где есть сырье
    categories_with_raw = [c for c in categories if c.id in stats_dict and stats_dict[c.id] > 0]

    # Клавиатура выбора категории
    keyboard = get_categories_keyboard(
        categories_with_raw,
        stats_dict=stats_dict,
        prefix='arrival_category'
    )

    text = (
        "📦 <b>Приемка сырья на склад</b>\n\n"
        f"🏭 <b>Склад:</b> {warehouse_name}\n\n"
        "📂 Выберите категорию сырья:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(ArrivalStates.select_category)


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@arrival_router.callback_query(F.data.in_(["arrival_cancel", "cancel"]))
@arrival_router.message(Command("cancel"), StateFilter('*'))
async def cancel_arrival(
    update: Message | CallbackQuery,
    state: FSMContext
) -> None:
    """
    Отменяет процесс приемки.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
    else:
        message = update
    
    # Очистка состояния
    await state.clear()
    
    await message.answer(
        "❌ Приемка отменена.",
        reply_markup=get_main_menu_keyboard()
    )



__all__ = ['arrival_router']

