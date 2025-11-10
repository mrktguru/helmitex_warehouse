"""
Обработчик команд просмотра истории операций.

Этот модуль реализует функциональность для:
- Просмотра истории движений по складам
- Просмотра истории производственных партий
- Просмотра истории фасовки
- Просмотра истории отгрузок
- Просмотра истории отходов
- Фильтрации по датам и типам операций
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from app.database.models import (
    User, Movement, ProductionBatch, Shipment, WasteRecord,
    MovementType, ProductionStatus, ShipmentStatus
)
from app.services import (
    warehouse_service,
    production_service,
    packing_service,
    shipment_service
)
from app.utils.keyboards import get_main_menu_keyboard


# ============================================================================
# FSM СОСТОЯНИЯ
# ============================================================================

class HistoryStates(StatesGroup):
    """Состояния FSM для просмотра истории операций."""
    select_action = State()      # Выбор типа истории
    select_period = State()       # Выбор периода
    select_warehouse = State()    # Выбор склада
    view_movements = State()      # Просмотр движений
    view_production = State()     # Просмотр производства
    view_packing = State()        # Просмотр фасовки
    view_shipments = State()      # Просмотр отгрузок
    view_waste = State()          # Просмотр отходов


# ============================================================================
# РОУТЕР
# ============================================================================

router = Router(name='history')


# ============================================================================
# НАЧАЛО ДИАЛОГА ИСТОРИИ
# ============================================================================

@router.message(Command('history'))
@router.callback_query(F.data == 'history_start')
async def start_history(
    event: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс просмотра истории операций.
    
    Команда: /history или кнопка "История"
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
    
    # Инициализация данных диалога
    await state.update_data(
        user_id=user_id,
        started_at=datetime.utcnow().isoformat(),
        period='today'
    )
    
    # Меню выбора типа истории
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Движения товаров", callback_data='hist_movements')],
        [InlineKeyboardButton(text="🏭 История производства", callback_data='hist_production')],
        [InlineKeyboardButton(text="📦 История фасовки", callback_data='hist_packing')],
        [InlineKeyboardButton(text="🚚 История отгрузок", callback_data='hist_shipments')],
        [InlineKeyboardButton(text="🗑 История отходов", callback_data='hist_waste')],
        [InlineKeyboardButton(text="❌ Отменить", callback_data='hist_cancel')]
    ])
    
    text = (
        "📜 <b>История операций</b>\n\n"
        "Выберите тип операций:"
    )
    
    if isinstance(event, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    
    await state.set_state(HistoryStates.select_action)


# ============================================================================
# ВЫБОР ПЕРИОДА
# ============================================================================

async def select_period_menu(
    query: CallbackQuery,
    state: FSMContext,
    operation_type: str
) -> None:
    """
    Показывает меню выбора периода для просмотра истории.
    """
    await query.answer()
    
    # Сохранение типа операции
    await state.update_data(operation_type=operation_type)
    
    # Определение названия операции
    operation_names = {
        'movements': 'движений товаров',
        'production': 'производства',
        'packing': 'фасовки',
        'shipments': 'отгрузок',
        'waste': 'отходов'
    }
    
    operation_name = operation_names.get(operation_type, 'операций')
    
    # Меню выбора периода
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data='hist_period_today')],
        [InlineKeyboardButton(text="📅 Вчера", callback_data='hist_period_yesterday')],
        [InlineKeyboardButton(text="📅 Последние 7 дней", callback_data='hist_period_week')],
        [InlineKeyboardButton(text="📅 Последние 30 дней", callback_data='hist_period_month')],
        [InlineKeyboardButton(text="📅 Весь период", callback_data='hist_period_all')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='hist_start')],
        [InlineKeyboardButton(text="❌ Отменить", callback_data='hist_cancel')]
    ])
    
    text = (
        f"📜 <b>История {operation_name}</b>\n\n"
        "Выберите период:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(HistoryStates.select_period)


@router.callback_query(HistoryStates.select_action, F.data == 'hist_movements')
async def select_movements_period(query: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору периода для движений."""
    await select_period_menu(query, state, 'movements')


@router.callback_query(HistoryStates.select_action, F.data == 'hist_production')
async def select_production_period(query: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору периода для производства."""
    await select_period_menu(query, state, 'production')


@router.callback_query(HistoryStates.select_action, F.data == 'hist_packing')
async def select_packing_period(query: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору периода для фасовки."""
    await select_period_menu(query, state, 'packing')


@router.callback_query(HistoryStates.select_action, F.data == 'hist_shipments')
async def select_shipments_period(query: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору периода для отгрузок."""
    await select_period_menu(query, state, 'shipments')


@router.callback_query(HistoryStates.select_action, F.data == 'hist_waste')
async def select_waste_period(query: CallbackQuery, state: FSMContext) -> None:
    """Переход к выбору периода для отходов."""
    await select_period_menu(query, state, 'waste')


# ============================================================================
# ОБРАБОТКА ВЫБОРА ПЕРИОДА
# ============================================================================

@router.callback_query(HistoryStates.select_period, F.data.startswith('hist_period_'))
async def select_period(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор периода и переходит к выбору склада.
    """
    await query.answer()
    
    # Определение периода
    callback_data = query.data
    today = date.today()
    
    if callback_data == 'hist_period_today':
        start_date = today
        end_date = today
        period_name = "Сегодня"
    elif callback_data == 'hist_period_yesterday':
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
        period_name = "Вчера"
    elif callback_data == 'hist_period_week':
        start_date = today - timedelta(days=7)
        end_date = today
        period_name = "Последние 7 дней"
    elif callback_data == 'hist_period_month':
        start_date = today - timedelta(days=30)
        end_date = today
        period_name = "Последние 30 дней"
    else:  # all
        start_date = None
        end_date = None
        period_name = "Весь период"
    
    # Сохранение периода
    await state.update_data(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        period_name=period_name
    )
    
    try:
        # Получение списка складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await query.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Клавиатура выбора склада (+ опция "Все склады")
        keyboard_buttons = []
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🏭 Все склады", callback_data='hist_wh_all')
        ])
        
        for warehouse in warehouses:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=warehouse.name,
                    callback_data=f'hist_wh_{warehouse.id}'
                )
            ])
        
        data = await state.get_data()
        operation_type = data.get('operation_type', 'movements')
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data=f'hist_{operation_type}'),
            InlineKeyboardButton(text="❌ Отменить", callback_data='hist_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = (
            f"📜 <b>Период:</b> {period_name}\n\n"
            "Выберите склад:"
        )
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.select_warehouse)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВЫБОР СКЛАДА И ПРОСМОТР ДАННЫХ
# ============================================================================

@router.callback_query(HistoryStates.select_warehouse, F.data.startswith('hist_wh_'))
async def select_warehouse_and_view(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор склада и показывает данные.
    """
    await query.answer("⏳ Загрузка данных...")
    
    # Извлечение ID склада
    callback_data = query.data
    
    if callback_data == 'hist_wh_all':
        warehouse_id = None
        warehouse_name = "Все склады"
    else:
        warehouse_id = int(callback_data.split('_')[-1])
        
        # Получение названия склада
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        warehouse_name = warehouse.name
    
    # Сохранение выбора
    await state.update_data(
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name
    )
    
    # Перенаправление на нужный обработчик
    data = await state.get_data()
    operation_type = data.get('operation_type')
    
    if operation_type == 'movements':
        await view_movements(query, state, session)
    elif operation_type == 'production':
        await view_production(query, state, session)
    elif operation_type == 'packing':
        await view_packing(query, state, session)
    elif operation_type == 'shipments':
        await view_shipments(query, state, session)
    elif operation_type == 'waste':
        await view_waste(query, state, session)
    else:
        await query.message.edit_text(
            "❌ Неизвестный тип операции.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР ДВИЖЕНИЙ
# ============================================================================

async def view_movements(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает историю движений товаров.
    """
    data = await state.get_data()
    
    try:
        # Получение движений
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        stmt = select(Movement).options(
            selectinload(Movement.sku),
            selectinload(Movement.warehouse),
            selectinload(Movement.user)
        ).order_by(Movement.created_at.desc())
        
        # Фильтры
        filters = []
        
        if data.get('warehouse_id'):
            filters.append(Movement.warehouse_id == data['warehouse_id'])
        
        if data.get('start_date'):
            start_dt = datetime.fromisoformat(data['start_date'])
            filters.append(Movement.created_at >= datetime.combine(start_dt.date(), datetime.min.time()))
        
        if data.get('end_date'):
            end_dt = datetime.fromisoformat(data['end_date'])
            filters.append(Movement.created_at <= datetime.combine(end_dt.date(), datetime.max.time()))
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        stmt = stmt.limit(100)  # Ограничение для производительности
        
        result = await session.execute(stmt)
        movements = list(result.scalars().all())
        
        if not movements:
            text = (
                f"📦 <b>Движения товаров</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n\n"
                "❌ Нет движений за выбранный период."
            )
        else:
            # Группировка по типам
            movements_by_type = {}
            
            for movement in movements:
                type_val = movement.movement_type.value
                if type_val not in movements_by_type:
                    movements_by_type[type_val] = []
                movements_by_type[type_val].append(movement)
            
            # Формирование отчета
            text = (
                f"📦 <b>Движения товаров</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n"
                f"📊 <b>Всего записей:</b> {len(movements)}\n\n"
            )
            
            # Типы движений с эмодзи
            movement_icons = {
                'arrival': '📥',
                'production': '🏭',
                'packing': '📦',
                'shipment': '🚚',
                'adjustment': '🔧',
                'waste': '🗑'
            }
            
            for mov_type, items in sorted(movements_by_type.items()):
                icon = movement_icons.get(mov_type, '📋')
                text += f"<b>{icon} {mov_type.upper()} ({len(items)}):</b>\n"
                
                for movement in items[:5]:  # Показываем первые 5
                    direction = "+" if movement.quantity > 0 else ""
                    text += (
                        f"  • {movement.sku.name}: "
                        f"{direction}{movement.quantity} {movement.sku.unit}\n"
                        f"    {movement.created_at.strftime('%d.%m %H:%M')}"
                    )

                    if movement.user:
                        text += f" | {movement.user.username}"

                    text += "\n"
                    
                    if movement.notes:
                        notes_short = movement.notes[:40] + "..." if len(movement.notes) > 40 else movement.notes
                        text += f"    <i>{notes_short}</i>\n"
                    
                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние операции</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton(text="🔙 Изменить период", callback_data='hist_movements')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.view_movements)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке движений: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР ИСТОРИИ ПРОИЗВОДСТВА
# ============================================================================

async def view_production(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает историю производственных партий.
    """
    data = await state.get_data()
    
    try:
        # Преобразование дат
        start_date = date.fromisoformat(data['start_date']) if data.get('start_date') else None
        end_date = date.fromisoformat(data['end_date']) if data.get('end_date') else None
        
        # Получение партий
        batches = await production_service.get_batches(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=start_date,
            end_date=end_date,
            limit=50
        )
        
        if not batches:
            text = (
                f"🏭 <b>История производства</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n\n"
                "❌ Нет производственных партий за выбранный период."
            )
        else:
            # Группировка по статусам
            batches_by_status = {}
            
            for batch in batches:
                status_val = batch.status.value
                if status_val not in batches_by_status:
                    batches_by_status[status_val] = []
                batches_by_status[status_val].append(batch)
            
            # Формирование отчета
            text = (
                f"🏭 <b>История производства</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n"
                f"📊 <b>Всего партий:</b> {len(batches)}\n\n"
            )
            
            # Статусы с эмодзи
            status_icons = {
                'planned': '📝',
                'in_progress': '⏳',
                'completed': '✅',
                'cancelled': '❌'
            }
            
            for status, items in sorted(batches_by_status.items()):
                icon = status_icons.get(status, '📋')
                text += f"<b>{icon} {status.upper()} ({len(items)}):</b>\n"
                
                for batch in items[:5]:  # Показываем первые 5
                    text += f"  • <b>Партия #{batch.id}</b>\n"
                    text += f"    Рецепт: {batch.recipe.name}\n"
                    text += f"    Плановый вес: {batch.target_weight} кг\n"

                    if batch.actual_weight:
                        text += f"    Фактический выход: {batch.actual_weight} кг\n"

                    text += f"    Дата: {batch.started_at.strftime('%d.%m.%Y')}\n"

                    if batch.user:
                        text += f"    Оператор: {batch.user.username}\n"

                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние партии</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton(text="🔙 Изменить период", callback_data='hist_production')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.view_production)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории производства: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР ИСТОРИИ ФАСОВКИ
# ============================================================================

async def view_packing(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает историю операций фасовки.
    """
    data = await state.get_data()
    
    try:
        # Преобразование дат
        start_date = date.fromisoformat(data['start_date']) if data.get('start_date') else None
        end_date = date.fromisoformat(data['end_date']) if data.get('end_date') else None
        
        # Получение истории фасовки
        packing_history = await packing_service.get_packing_history(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=start_date,
            end_date=end_date,
            limit=50
        )
        
        if not packing_history:
            text = (
                f"📦 <b>История фасовки</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n\n"
                "❌ Нет операций фасовки за выбранный период."
            )
        else:
            # Формирование отчета
            text = (
                f"📦 <b>История фасовки</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n"
                f"📊 <b>Всего операций:</b> {len(packing_history)}\n\n"
            )
            
            total_units = 0
            total_waste = 0
            
            for record in packing_history[:20]:  # Показываем первые 20
                text += f"  • <b>{record['finished_sku_name']}</b>\n"
                text += f"    Упаковано: {record['units_count']} шт"
                
                if record.get('waste_container_units', 0) > 0:
                    text += f" (брак: {record['waste_container_units']} шт)"
                    total_waste += record['waste_container_units']
                
                text += "\n"
                text += f"    Дата: {record['packing_date'].strftime('%d.%m.%Y')}\n"
                
                if record.get('packed_by_username'):
                    text += f"    Оператор: {record['packed_by_username']}\n"
                
                if record.get('notes'):
                    notes_short = record['notes'][:40] + "..." if len(record['notes']) > 40 else record['notes']
                    text += f"    <i>{notes_short}</i>\n"
                
                text += "\n"
                
                total_units += record['units_count']
            
            if len(packing_history) > 20:
                text += f"<i>... и еще {len(packing_history) - 20} операций</i>\n\n"
            
            text += f"<b>Итого упаковано:</b> {total_units} шт\n"
            if total_waste > 0:
                text += f"<b>Общий брак:</b> {total_waste} шт\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние операции</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton(text="🔙 Изменить период", callback_data='hist_packing')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.view_packing)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории фасовки: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР ИСТОРИИ ОТГРУЗОК
# ============================================================================

async def view_shipments(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает историю отгрузок.
    """
    data = await state.get_data()
    
    try:
        # Преобразование дат
        start_date = date.fromisoformat(data['start_date']) if data.get('start_date') else None
        end_date = date.fromisoformat(data['end_date']) if data.get('end_date') else None
        
        # Получение отгрузок
        shipments = await shipment_service.get_shipments(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=start_date,
            end_date=end_date,
            limit=50
        )
        
        if not shipments:
            text = (
                f"🚚 <b>История отгрузок</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n\n"
                "❌ Нет отгрузок за выбранный период."
            )
        else:
            # Группировка по статусам
            shipments_by_status = {}
            
            for shipment in shipments:
                status_val = shipment.status.value
                if status_val not in shipments_by_status:
                    shipments_by_status[status_val] = []
                shipments_by_status[status_val].append(shipment)
            
            # Формирование отчета
            text = (
                f"🚚 <b>История отгрузок</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n"
                f"📊 <b>Всего отгрузок:</b> {len(shipments)}\n\n"
            )
            
            # Статусы с эмодзи
            status_icons = {
                'draft': '📝',
                'reserved': '🔒',
                'completed': '✅',
                'cancelled': '❌'
            }
            
            for status, items in sorted(shipments_by_status.items()):
                icon = status_icons.get(status, '📋')
                text += f"<b>{icon} {status.upper()} ({len(items)}):</b>\n"
                
                for shipment in items[:5]:  # Показываем первые 5
                    text += f"  • <b>Отгрузка #{shipment.id}</b>\n"
                    if shipment.recipient:
                        text += f"    Получатель: {shipment.recipient.name}\n"
                    text += f"    Позиций: {len(shipment.items)}\n"
                    text += f"    Дата: {shipment.created_at.strftime('%d.%m.%Y')}\n"

                    if shipment.notes:
                        notes_short = shipment.notes[:40] + "..." if len(shipment.notes) > 40 else shipment.notes
                        text += f"    <i>{notes_short}</i>\n"

                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние отгрузки</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton(text="🔙 Изменить период", callback_data='hist_shipments')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.view_shipments)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории отгрузок: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР ИСТОРИИ ОТХОДОВ
# ============================================================================

async def view_waste(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает историю отходов.
    """
    data = await state.get_data()
    
    try:
        # Получение записей об отходах
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        stmt = select(WasteRecord).options(
            selectinload(WasteRecord.sku),
            selectinload(WasteRecord.warehouse)
        ).order_by(WasteRecord.created_at.desc())
        
        # Фильтры
        filters = []
        
        if data.get('warehouse_id'):
            filters.append(WasteRecord.warehouse_id == data['warehouse_id'])
        
        if data.get('start_date'):
            start_dt = datetime.fromisoformat(data['start_date'])
            filters.append(WasteRecord.created_at >= datetime.combine(start_dt.date(), datetime.min.time()))
        
        if data.get('end_date'):
            end_dt = datetime.fromisoformat(data['end_date'])
            filters.append(WasteRecord.created_at <= datetime.combine(end_dt.date(), datetime.max.time()))
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        stmt = stmt.limit(100)
        
        result = await session.execute(stmt)
        waste_records = list(result.scalars().all())
        
        if not waste_records:
            text = (
                f"🗑 <b>История отходов</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n\n"
                "❌ Нет записей об отходах за выбранный период."
            )
        else:
            # Группировка по типам отходов
            waste_by_type = {}
            
            for waste in waste_records:
                type_val = waste.waste_type.value
                if type_val not in waste_by_type:
                    waste_by_type[type_val] = []
                waste_by_type[type_val].append(waste)
            
            # Формирование отчета
            text = (
                f"🗑 <b>История отходов</b>\n"
                f"🏭 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['period_name']}\n"
                f"📊 <b>Всего записей:</b> {len(waste_records)}\n\n"
            )
            
            # Типы отходов с эмодзи
            waste_icons = {
                'production_loss': '⚗️',
                'defective_semi': '🛢',
                'defective_container': '📦',
                'expired': '⏰'
            }
            
            for waste_type, items in sorted(waste_by_type.items()):
                icon = waste_icons.get(waste_type, '🗑')
                text += f"<b>{icon} {waste_type.replace('_', ' ').upper()} ({len(items)}):</b>\n"
                
                for waste in items[:5]:  # Показываем первые 5
                    text += f"  • {waste.sku.name}: {waste.quantity} {waste.sku.unit}\n"
                    text += f"    {waste.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                    
                    if waste.reason:
                        reason_short = waste.reason[:50] + "..." if len(waste.reason) > 50 else waste.reason
                        text += f"    <i>{reason_short}</i>\n"
                    
                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние записи</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton(text="🔙 Изменить период", callback_data='hist_waste')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(HistoryStates.view_waste)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории отходов: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ОБНОВЛЕНИЕ ДАННЫХ ИЗ СОСТОЯНИЙ ПРОСМОТРА
# ============================================================================

@router.callback_query(HistoryStates.view_movements, F.data.startswith('hist_wh_'))
async def refresh_movements(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление данных движений."""
    await select_warehouse_and_view(query, state, session)


@router.callback_query(HistoryStates.view_production, F.data.startswith('hist_wh_'))
async def refresh_production(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление данных производства."""
    await select_warehouse_and_view(query, state, session)


@router.callback_query(HistoryStates.view_packing, F.data.startswith('hist_wh_'))
async def refresh_packing(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление данных фасовки."""
    await select_warehouse_and_view(query, state, session)


@router.callback_query(HistoryStates.view_shipments, F.data.startswith('hist_wh_'))
async def refresh_shipments(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление данных отгрузок."""
    await select_warehouse_and_view(query, state, session)


@router.callback_query(HistoryStates.view_waste, F.data.startswith('hist_wh_'))
async def refresh_waste(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обновление данных отходов."""
    await select_warehouse_and_view(query, state, session)


# ============================================================================
# ВОЗВРАТ К ПРЕДЫДУЩИМ ШАГАМ
# ============================================================================

@router.callback_query(F.data == 'hist_start')
async def back_to_start(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возвращает к начальному меню истории."""
    await query.answer()
    
    # Сброс состояния и вызов start_history
    await state.clear()
    await start_history(query, state, session)


@router.callback_query(HistoryStates.view_movements, F.data == 'hist_movements')
async def back_to_movements_period(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору периода для движений."""
    await select_period_menu(query, state, 'movements')


@router.callback_query(HistoryStates.view_production, F.data == 'hist_production')
async def back_to_production_period(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору периода для производства."""
    await select_period_menu(query, state, 'production')


@router.callback_query(HistoryStates.view_packing, F.data == 'hist_packing')
async def back_to_packing_period(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору периода для фасовки."""
    await select_period_menu(query, state, 'packing')


@router.callback_query(HistoryStates.view_shipments, F.data == 'hist_shipments')
async def back_to_shipments_period(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору периода для отгрузок."""
    await select_period_menu(query, state, 'shipments')


@router.callback_query(HistoryStates.view_waste, F.data == 'hist_waste')
async def back_to_waste_period(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору периода для отходов."""
    await select_period_menu(query, state, 'waste')


@router.callback_query(HistoryStates.select_warehouse, F.data.in_([
    'hist_movements', 'hist_production', 'hist_packing', 'hist_shipments', 'hist_waste'
]))
async def back_from_warehouse_selection(query: CallbackQuery, state: FSMContext) -> None:
    """Возврат из выбора склада к выбору периода."""
    operation_type = query.data.replace('hist_', '')
    await select_period_menu(query, state, operation_type)


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@router.callback_query(F.data == 'hist_cancel')
@router.message(Command('cancel'))
async def cancel_history(event: Union[Message, CallbackQuery], state: FSMContext) -> None:
    """
    Закрывает просмотр истории.
    """
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event
    
    # Очистка данных
    await state.clear()
    
    await message.answer(
        "✅ Просмотр истории завершен.",
        reply_markup=get_main_menu_keyboard()
    )



# Export router with expected name
history_router = router

__all__ = ['history_router']
