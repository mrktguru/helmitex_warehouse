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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import parse_date_input


# Состояния диалога
(
    SELECT_ACTION,
    SELECT_PERIOD,
    SELECT_WAREHOUSE,
    VIEW_MOVEMENTS,
    VIEW_PRODUCTION,
    VIEW_PACKING,
    VIEW_SHIPMENTS,
    VIEW_WASTE
) = range(8)


# ============================================================================
# НАЧАЛО ДИАЛОГА ИСТОРИИ
# ============================================================================

async def start_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс просмотра истории операций.
    
    Команда: /history или кнопка "История"
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
    
    # Инициализация данных диалога
    context.user_data['history'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow(),
        'period': 'today'  # По умолчанию сегодня
    }
    
    # Меню выбора типа истории
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Движения товаров", callback_data='hist_movements')],
        [InlineKeyboardButton("🏭 История производства", callback_data='hist_production')],
        [InlineKeyboardButton("📦 История фасовки", callback_data='hist_packing')],
        [InlineKeyboardButton("🚚 История отгрузок", callback_data='hist_shipments')],
        [InlineKeyboardButton("🗑 История отходов", callback_data='hist_waste')],
        [InlineKeyboardButton("❌ Отменить", callback_data='hist_cancel')]
    ])
    
    text = (
        "📜 <b>История операций</b>\n\n"
        "Выберите тип операций:"
    )
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    return SELECT_ACTION


# ============================================================================
# ВЫБОР ПЕРИОДА
# ============================================================================

async def select_period_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, operation_type: str) -> int:
    """
    Показывает меню выбора периода для просмотра истории.
    """
    query = update.callback_query
    await query.answer()
    
    # Сохранение типа операции
    context.user_data['history']['operation_type'] = operation_type
    
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data='hist_period_today')],
        [InlineKeyboardButton("📅 Вчера", callback_data='hist_period_yesterday')],
        [InlineKeyboardButton("📅 Последние 7 дней", callback_data='hist_period_week')],
        [InlineKeyboardButton("📅 Последние 30 дней", callback_data='hist_period_month')],
        [InlineKeyboardButton("📅 Весь период", callback_data='hist_period_all')],
        [InlineKeyboardButton("🔙 Назад", callback_data='hist_start')],
        [InlineKeyboardButton("❌ Отменить", callback_data='hist_cancel')]
    ])
    
    text = (
        f"📜 <b>История {operation_name}</b>\n\n"
        "Выберите период:"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    return SELECT_PERIOD


# ============================================================================
# ОБРАБОТКА ВЫБОРА ПЕРИОДА
# ============================================================================

async def select_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор периода и переходит к выбору склада.
    """
    query = update.callback_query
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
    context.user_data['history']['start_date'] = start_date
    context.user_data['history']['end_date'] = end_date
    context.user_data['history']['period_name'] = period_name
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение списка складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await query.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Клавиатура выбора склада (+ опция "Все склады")
        keyboard_buttons = []
        
        keyboard_buttons.append([
            InlineKeyboardButton("🏭 Все склады", callback_data='hist_wh_all')
        ])
        
        for warehouse in warehouses:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    warehouse.name,
                    callback_data=f'hist_wh_{warehouse.id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 Назад", callback_data=f'hist_{context.user_data["history"]["operation_type"]}'),
            InlineKeyboardButton("❌ Отменить", callback_data='hist_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text = (
            f"📜 <b>Период:</b> {period_name}\n\n"
            "Выберите склад:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_WAREHOUSE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВЫБОР СКЛАДА И ПРОСМОТР ДАННЫХ
# ============================================================================

async def select_warehouse_and_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор склада и показывает данные.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка данных...")
    
    # Извлечение ID склада
    callback_data = query.data
    
    if callback_data == 'hist_wh_all':
        warehouse_id = None
        warehouse_name = "Все склады"
    else:
        warehouse_id = int(callback_data.split('_')[-1])
        
        # Получение названия склада
        session: AsyncSession = context.bot_data['db_session']
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        warehouse_name = warehouse.name
    
    # Сохранение выбора
    context.user_data['history']['warehouse_id'] = warehouse_id
    context.user_data['history']['warehouse_name'] = warehouse_name
    
    # Перенаправление на нужный обработчик
    operation_type = context.user_data['history']['operation_type']
    
    if operation_type == 'movements':
        return await view_movements(update, context)
    elif operation_type == 'production':
        return await view_production(update, context)
    elif operation_type == 'packing':
        return await view_packing(update, context)
    elif operation_type == 'shipments':
        return await view_shipments(update, context)
    elif operation_type == 'waste':
        return await view_waste(update, context)
    else:
        await query.message.edit_text(
            "❌ Неизвестный тип операции.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР ДВИЖЕНИЙ
# ============================================================================

async def view_movements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает историю движений товаров.
    """
    query = update.callback_query
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['history']
    
    try:
        # Получение движений
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        stmt = select(Movement).options(
            selectinload(Movement.sku),
            selectinload(Movement.warehouse),
            selectinload(Movement.performed_by)
        ).order_by(Movement.created_at.desc())
        
        # Фильтры
        filters = []
        
        if data.get('warehouse_id'):
            filters.append(Movement.warehouse_id == data['warehouse_id'])
        
        if data.get('start_date'):
            filters.append(Movement.created_at >= datetime.combine(data['start_date'], datetime.min.time()))
        
        if data.get('end_date'):
            filters.append(Movement.created_at <= datetime.combine(data['end_date'], datetime.max.time()))
        
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
                    
                    if movement.performed_by:
                        text += f" | {movement.performed_by.username}"
                    
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton("🔙 Изменить период", callback_data='hist_movements')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return VIEW_MOVEMENTS
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке движений: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР ИСТОРИИ ПРОИЗВОДСТВА
# ============================================================================

async def view_production(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает историю производственных партий.
    """
    query = update.callback_query
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['history']
    
    try:
        # Получение партий
        batches = await production_service.get_batches(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
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
                    text += f"  • <b>{batch.batch_number}</b>\n"
                    text += f"    Рецепт: {batch.recipe.name}\n"
                    text += f"    Размер: {batch.batch_size} кг\n"
                    
                    if batch.actual_output:
                        text += f"    Выход: {batch.actual_output} кг"
                        if batch.waste_semi_finished and batch.waste_semi_finished > 0:
                            text += f" (брак: {batch.waste_semi_finished} кг)"
                        text += "\n"
                    
                    text += f"    Дата: {batch.production_date.strftime('%d.%m.%Y')}\n"
                    
                    if batch.created_by:
                        text += f"    Оператор: {batch.created_by.username}\n"
                    
                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние партии</i>"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton("🔙 Изменить период", callback_data='hist_production')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return VIEW_PRODUCTION
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории производства: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР ИСТОРИИ ФАСОВКИ
# ============================================================================

async def view_packing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает историю операций фасовки.
    """
    query = update.callback_query
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['history']
    
    try:
        # Получение истории фасовки
        packing_history = await packing_service.get_packing_history(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton("🔙 Изменить период", callback_data='hist_packing')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return VIEW_PACKING
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории фасовки: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР ИСТОРИИ ОТГРУЗОК
# ============================================================================

async def view_shipments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает историю отгрузок.
    """
    query = update.callback_query
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['history']
    
    try:
        # Получение отгрузок
        shipments = await shipment_service.get_shipments(
            session,
            warehouse_id=data.get('warehouse_id'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
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
                    text += f"    Получатель: {shipment.recipient.name}\n"
                    text += f"    Позиций: {len(shipment.items)}\n"
                    
                    # Общая сумма
                    total_value = sum(
                        (item.quantity * item.price_per_unit) if item.price_per_unit else 0
                        for item in shipment.items
                    )
                    
                    if total_value > 0:
                        text += f"    Сумма: {total_value} ₽\n"
                    
                    text += f"    Дата: {shipment.shipment_date.strftime('%d.%m.%Y')}\n"
                    
                    if shipment.created_by:
                        text += f"    Создал: {shipment.created_by.username}\n"
                    
                    text += "\n"
                
                if len(items) > 5:
                    text += f"  <i>... и еще {len(items) - 5}</i>\n"
                
                text += "\n"
        
        # Разбивка если слишком длинное
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>... список слишком длинный, показаны последние отгрузки</i>"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton("🔙 Изменить период", callback_data='hist_shipments')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return VIEW_SHIPMENTS
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории отгрузок: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР ИСТОРИИ ОТХОДОВ
# ============================================================================

async def view_waste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает историю отходов.
    """
    query = update.callback_query
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['history']
    
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
            filters.append(WasteRecord.created_at >= datetime.combine(data['start_date'], datetime.min.time()))
        
        if data.get('end_date'):
            filters.append(WasteRecord.created_at <= datetime.combine(data['end_date'], datetime.max.time()))
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'hist_wh_{data.get("warehouse_id") or "all"}')],
            [InlineKeyboardButton("🔙 Изменить период", callback_data='hist_waste')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='hist_cancel')]
        ])
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return VIEW_WASTE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке истории отходов: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВОЗВРАТ К НАЧАЛУ
# ============================================================================

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Возвращает к начальному меню истории.
    """
    query = update.callback_query
    await query.answer()
    
    return await start_history(update, context)


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Закрывает просмотр истории.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('history', None)
    
    await message.reply_text(
        "✅ Просмотр истории завершен.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_history_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для просмотра истории.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('history', start_history),
            CallbackQueryHandler(start_history, pattern='^history_start$')
        ],
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'movements'), pattern='^hist_movements$'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'production'), pattern='^hist_production$'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'packing'), pattern='^hist_packing$'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'shipments'), pattern='^hist_shipments$'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'waste'), pattern='^hist_waste$'),
                CallbackQueryHandler(back_to_start, pattern='^hist_start$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            SELECT_PERIOD: [
                CallbackQueryHandler(select_period, pattern='^hist_period_'),
                CallbackQueryHandler(back_to_start, pattern='^hist_start$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, c.user_data['history']['operation_type']), pattern='^hist_(movements|production|packing|shipments|waste)$'),
                CallbackQueryHandler(back_to_start, pattern='^hist_start$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            VIEW_MOVEMENTS: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'movements'), pattern='^hist_movements$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            VIEW_PRODUCTION: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'production'), pattern='^hist_production$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            VIEW_PACKING: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'packing'), pattern='^hist_packing$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            VIEW_SHIPMENTS: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'shipments'), pattern='^hist_shipments$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ],
            VIEW_WASTE: [
                CallbackQueryHandler(select_warehouse_and_view, pattern='^hist_wh_'),
                CallbackQueryHandler(lambda u, c: select_period_menu(u, c, 'waste'), pattern='^hist_waste$'),
                CallbackQueryHandler(cancel_history, pattern='^hist_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_history),
            CallbackQueryHandler(cancel_history, pattern='^cancel$')
        ],
        name='history_conversation',
        persistent=False
    )
