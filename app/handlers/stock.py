"""
Обработчик команд просмотра остатков и статистики складов (aiogram 3.x).

Этот модуль реализует функциональность для:
- Просмотра остатков по складам и типам номенклатуры
- Просмотра информации о бочках с полуфабрикатами
- Получения статистики по движениям
- Просмотра резервов и доступности
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import User, SKUType, InventoryReserve
from app.services import (
    warehouse_service,
    stock_service,
    barrel_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_main_menu_keyboard
)
from app.utils.logger import get_logger

logger = get_logger("stock_handler")

# Создаём роутер для stock handlers
stock_router = Router(name="stock")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class StockStates(StatesGroup):
    """Состояния диалога просмотра остатков."""
    select_action = State()
    select_warehouse = State()
    select_sku_type = State()


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРОСМОТРА ОСТАТКОВ
# ============================================================================

@stock_router.message(Command("stock"))
@stock_router.callback_query(F.data == "stock_view_start")
async def start_stock_view(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Начинает процесс просмотра остатков.
    
    Команда: /stock или кнопка "Остатки"
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
    
    # Инициализация данных
    await state.update_data(
        user_id=user.id,
        started_at=datetime.utcnow().isoformat()
    )
    
    # Меню выбора действия
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Остатки по складам", callback_data='stock_by_warehouse')],
        [InlineKeyboardButton(text="🛢 Бочки с полуфабрикатами", callback_data='stock_barrels')],
        [InlineKeyboardButton(text="📊 Общая статистика", callback_data='stock_overall')],
        [InlineKeyboardButton(text="🔒 Резервы", callback_data='stock_reserves')],
        [InlineKeyboardButton(text="❌ Отменить", callback_data='stock_cancel')]
    ])
    
    text = (
        "📊 <b>Просмотр остатков и статистики</b>\n\n"
        "Выберите действие:"
    )
    
    if isinstance(update, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)
    
    await state.set_state(StockStates.select_action)


# ============================================================================
# ОСТАТКИ ПО СКЛАДАМ
# ============================================================================

@stock_router.callback_query(
    StateFilter(StockStates.select_action),
    F.data == "stock_by_warehouse"
)
async def view_by_warehouse(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает список складов для просмотра остатков.
    """
    await callback.answer()
    
    try:
        # Получение списка складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await callback.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='stock_wh')
        
        text = (
            "📦 <b>Остатки по складам</b>\n\n"
            "Выберите склад:"
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(StockStates.select_warehouse)
        
    except Exception as e:
        logger.error(f"Error in view_by_warehouse: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@stock_router.callback_query(
    StateFilter(StockStates.select_warehouse),
    F.data.startswith("stock_wh_")
)
async def select_warehouse(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Обрабатывает выбор склада и показывает меню типов номенклатуры.
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
        
        # Меню выбора типа номенклатуры
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌾 Сырье", callback_data='stock_type_raw')],
            [InlineKeyboardButton(text="🛢 Полуфабрикаты", callback_data='stock_type_semi')],
            [InlineKeyboardButton(text="📦 Готовая продукция", callback_data='stock_type_finished')],
            [InlineKeyboardButton(text="📋 Все категории", callback_data='stock_type_all')],
            [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_by_warehouse')],
            [InlineKeyboardButton(text="❌ Отменить", callback_data='stock_cancel')]
        ])
        
        text = (
            f"📦 <b>Склад:</b> {warehouse.name}\n\n"
            "Выберите категорию номенклатуры:"
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(StockStates.select_sku_type)
        
    except Exception as e:
        logger.error(f"Error in select_warehouse: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@stock_router.callback_query(
    StateFilter(StockStates.select_sku_type),
    F.data.startswith("stock_type_")
)
async def view_stock_by_type(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает остатки по выбранному типу номенклатуры.
    """
    await callback.answer("⏳ Загрузка остатков...")
    
    # Определение типа номенклатуры
    callback_data = callback.data
    
    if callback_data == 'stock_type_raw':
        sku_type = SKUType.RAW
        type_name = "Сырье"
        type_emoji = "🌾"
    elif callback_data == 'stock_type_semi':
        sku_type = SKUType.SEMI_FINISHED
        type_name = "Полуфабрикаты"
        type_emoji = "🛢"
    elif callback_data == 'stock_type_finished':
        sku_type = SKUType.FINISHED
        type_name = "Готовая продукция"
        type_emoji = "📦"
    else:  # all
        sku_type = None
        type_name = "Все категории"
        type_emoji = "📋"
    
    # Получаем данные
    data = await state.get_data()
    warehouse_id = data['warehouse_id']
    warehouse_name = data['warehouse_name']
    
    try:
        # Получение остатков
        if sku_type:
            stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse_id,
                type=sku_type
            )
        else:
            stocks = await stock_service.get_all_stock_by_warehouse(
                session,
                warehouse_id=warehouse_id
            )
        
        if not stocks:
            text = (
                f"{type_emoji} <b>{type_name}</b>\n"
                f"📦 <b>Склад:</b> {warehouse_name}\n\n"
                "❌ Нет остатков в этой категории."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f'stock_wh_{warehouse_id}')],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        
        # Группировка по типу SKU
        grouped_stocks = {}
        total_positions = 0
        
        for stock in stocks:
            sku_type_val = stock.sku.sku_type.value
            if sku_type_val not in grouped_stocks:
                grouped_stocks[sku_type_val] = []
            grouped_stocks[sku_type_val].append(stock)
            total_positions += 1
        
        # Формирование отчета
        report = (
            f"{type_emoji} <b>{type_name}</b>\n"
            f"📦 <b>Склад:</b> {warehouse_name}\n"
            f"📊 <b>Позиций:</b> {total_positions}\n\n"
        )
        
        # Сортировка групп
        type_order = {
            'raw': ('🌾', 'Сырье'),
            'semi_finished': ('🛢', 'Полуфабрикаты'),
            'finished': ('📦', 'Готовая продукция')
        }
        
        for type_key in ['raw', 'semi_finished', 'finished']:
            if type_key not in grouped_stocks:
                continue
            
            emoji, name = type_order[type_key]
            items = grouped_stocks[type_key]
            
            report += f"<b>{emoji} {name} ({len(items)}):</b>\n"
            
            for stock in sorted(items, key=lambda s: s.sku.name):
                # Расчет доступности с учетом резервов
                availability = await stock_service.calculate_stock_availability(
                    session,
                    warehouse_id=warehouse_id,
                    sku_id=stock.sku_id
                )
                
                report += f"  • <b>{stock.sku.name}</b>\n"
                report += f"    Остаток: {stock.quantity} {stock.sku.unit}\n"
                
                if availability['reserved'] > 0:
                    report += f"    Резерв: {availability['reserved']} {stock.sku.unit}\n"
                    report += f"    Доступно: {availability['available']} {stock.sku.unit}\n"
                
                if stock.batch_number:
                    report += f"    Партия: {stock.batch_number}\n"
                
                report += "\n"
        
        # Разбивка на сообщения если слишком длинное
        if len(report) > 4000:
            report = report[:3900] + "\n\n<i>... список слишком длинный, показана часть</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=callback_data)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f'stock_wh_{warehouse_id}')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await callback.message.edit_text(report, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in view_stock_by_type: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при загрузке остатков: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР БОЧЕК
# ============================================================================

@stock_router.callback_query(
    StateFilter(StockStates.select_action),
    F.data == "stock_barrels"
)
async def view_barrels(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает список складов для просмотра бочек.
    """
    await callback.answer()
    
    try:
        # Получение списка складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await callback.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Клавиатура выбора склада
        keyboard_buttons = []
        for warehouse in warehouses:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=warehouse.name,
                    callback_data=f'stock_barrels_wh_{warehouse.id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data='stock_start'),
            InlineKeyboardButton(text="❌ Отменить", callback_data='stock_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = (
            "🛢 <b>Бочки с полуфабрикатами</b>\n\n"
            "Выберите склад:"
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(StockStates.select_warehouse)
        
    except Exception as e:
        logger.error(f"Error in view_barrels: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@stock_router.callback_query(
    StateFilter(StockStates.select_warehouse),
    F.data.startswith("stock_barrels_wh_")
)
async def view_barrels_by_warehouse(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает список бочек на выбранном складе.
    """
    await callback.answer("⏳ Загрузка бочек...")
    
    # Извлечение ID склада
    warehouse_id = int(callback.data.split('_')[-1])
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        
        # Получение бочек
        barrels = await barrel_service.get_barrels(
            session,
            warehouse_id=warehouse_id,
            available_only=False
        )
        
        if not barrels:
            text = (
                f"🛢 <b>Бочки - {warehouse.name}</b>\n\n"
                "❌ На складе нет бочек."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_barrels')],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        
        # Группировка по полуфабрикату
        barrels_by_sku = {}
        total_weight = Decimal('0')
        available_weight = Decimal('0')
        
        for barrel in barrels:
            sku_name = barrel.semi_sku.name
            if sku_name not in barrels_by_sku:
                barrels_by_sku[sku_name] = {
                    'barrels': [],
                    'total_weight': Decimal('0'),
                    'available_weight': Decimal('0')
                }
            
            barrels_by_sku[sku_name]['barrels'].append(barrel)
            barrels_by_sku[sku_name]['total_weight'] += barrel.current_weight
            
            if barrel.is_available:
                barrels_by_sku[sku_name]['available_weight'] += barrel.current_weight
                available_weight += barrel.current_weight
            
            total_weight += barrel.current_weight
        
        # Формирование отчета
        report = (
            f"🛢 <b>Бочки - {warehouse.name}</b>\n\n"
            f"📊 <b>Всего бочек:</b> {len(barrels)}\n"
            f"⚖️ <b>Общий вес:</b> {total_weight} кг\n"
            f"✅ <b>Доступно:</b> {available_weight} кг\n\n"
        )
        
        # Детали по полуфабрикатам
        for sku_name, info in sorted(barrels_by_sku.items()):
            report += f"<b>{sku_name}:</b>\n"
            report += f"  Бочек: {len(info['barrels'])}\n"
            report += f"  Общий вес: {info['total_weight']} кг\n"
            report += f"  Доступно: {info['available_weight']} кг\n"
            
            # Детали первых 5 бочек
            report += "  <i>Бочки:</i>\n"
            for i, barrel in enumerate(sorted(info['barrels'], key=lambda b: b.production_date)[:5]):
                status = "✅" if barrel.is_available else "🔒"
                report += (
                    f"    {status} {barrel.barrel_number}: "
                    f"{barrel.current_weight} кг "
                    f"({barrel.production_date.strftime('%d.%m.%Y')})\n"
                )
            
            if len(info['barrels']) > 5:
                report += f"    <i>... и еще {len(info['barrels']) - 5}</i>\n"
            
            report += "\n"
        
        # Разбивка если слишком длинное
        if len(report) > 4000:
            report = report[:3900] + "\n\n<i>... список слишком длинный, показана часть</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f'stock_barrels_wh_{warehouse_id}')],
            [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_barrels')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await callback.message.edit_text(report, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in view_barrels_by_warehouse: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при загрузке бочек: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ОБЩАЯ СТАТИСТИКА
# ============================================================================

@stock_router.callback_query(
    StateFilter(StockStates.select_action),
    F.data == "stock_overall"
)
async def view_overall_statistics(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает общую статистику по всем складам.
    """
    await callback.answer("⏳ Подготовка статистики...")
    
    try:
        # Получение всех складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await callback.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Сбор статистики
        total_stats = {
            'warehouses': len(warehouses),
            'raw_positions': 0,
            'semi_positions': 0,
            'finished_positions': 0,
            'total_barrels': 0,
            'total_barrel_weight': Decimal('0')
        }
        
        warehouse_details = []
        
        for warehouse in warehouses:
            # Остатки по типам
            raw_stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse.id,
                type=SKUType.RAW
            )
            
            semi_stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse.id,
                type=SKUType.SEMI_FINISHED
            )
            
            finished_stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse.id,
                type=SKUType.FINISHED
            )
            
            # Бочки
            barrels = await barrel_service.get_barrels(
                session,
                warehouse_id=warehouse.id
            )
            
            barrel_weight = sum(b.current_weight for b in barrels)
            
            # Суммирование
            total_stats['raw_positions'] += len(raw_stocks)
            total_stats['semi_positions'] += len(semi_stocks)
            total_stats['finished_positions'] += len(finished_stocks)
            total_stats['total_barrels'] += len(barrels)
            total_stats['total_barrel_weight'] += barrel_weight
            
            warehouse_details.append({
                'name': warehouse.name,
                'raw': len(raw_stocks),
                'semi': len(semi_stocks),
                'finished': len(finished_stocks),
                'barrels': len(barrels),
                'barrel_weight': barrel_weight
            })
        
        # Формирование отчета
        report = (
            "📊 <b>Общая статистика</b>\n\n"
            f"🏭 <b>Складов:</b> {total_stats['warehouses']}\n"
            f"🌾 <b>Позиций сырья:</b> {total_stats['raw_positions']}\n"
            f"🛢 <b>Позиций полуфабрикатов:</b> {total_stats['semi_positions']}\n"
            f"📦 <b>Позиций готовой продукции:</b> {total_stats['finished_positions']}\n"
            f"🛢 <b>Всего бочек:</b> {total_stats['total_barrels']}\n"
            f"⚖️ <b>Общий вес в бочках:</b> {total_stats['total_barrel_weight']} кг\n\n"
            "<b>По складам:</b>\n"
        )
        
        for wh in warehouse_details:
            report += f"\n<b>{wh['name']}:</b>\n"
            report += f"  Сырье: {wh['raw']} | Полуф.: {wh['semi']} | Готовая: {wh['finished']}\n"
            if wh['barrels'] > 0:
                report += f"  Бочки: {wh['barrels']} ({wh['barrel_weight']} кг)\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data='stock_overall')],
            [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_start')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await callback.message.edit_text(report, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in view_overall_statistics: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при подготовке статистики: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ПРОСМОТР РЕЗЕРВОВ
# ============================================================================

@stock_router.callback_query(
    StateFilter(StockStates.select_action),
    F.data == "stock_reserves"
)
async def view_reserves(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает активные резервы по всем складам.
    """
    await callback.answer("⏳ Загрузка резервов...")
    
    try:
        # Получение всех активных резервов
        stmt = select(InventoryReserve).options(
            selectinload(InventoryReserve.warehouse),
            selectinload(InventoryReserve.sku),
            selectinload(InventoryReserve.reserved_by)
        ).order_by(InventoryReserve.created_at.desc())
        
        result = await session.execute(stmt)
        reserves = list(result.scalars().all())
        
        if not reserves:
            text = (
                "🔒 <b>Резервы</b>\n\n"
                "✅ Нет активных резервов."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_start')],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        
        # Группировка по складам
        reserves_by_warehouse = {}
        total_reserves = 0
        
        for reserve in reserves:
            wh_name = reserve.warehouse.name
            if wh_name not in reserves_by_warehouse:
                reserves_by_warehouse[wh_name] = []
            reserves_by_warehouse[wh_name].append(reserve)
            total_reserves += 1
        
        # Формирование отчета
        report = (
            "🔒 <b>Активные резервы</b>\n\n"
            f"📊 <b>Всего резервов:</b> {total_reserves}\n\n"
        )
        
        for wh_name, wh_reserves in sorted(reserves_by_warehouse.items()):
            report += f"<b>📦 {wh_name} ({len(wh_reserves)}):</b>\n"
            
            for reserve in wh_reserves[:10]:  # Показываем первые 10
                report += f"  • <b>{reserve.sku.name}</b>\n"
                report += f"    Количество: {reserve.quantity} {reserve.sku.unit}\n"
                report += f"    Тип: {reserve.reserve_type.value}\n"
                report += f"    До: {reserve.reserved_until.strftime('%d.%m.%Y')}\n"
                
                if reserve.notes:
                    notes_short = reserve.notes[:50] + "..." if len(reserve.notes) > 50 else reserve.notes
                    report += f"    <i>{notes_short}</i>\n"
                
                report += "\n"
            
            if len(wh_reserves) > 10:
                report += f"  <i>... и еще {len(wh_reserves) - 10}</i>\n\n"
        
        # Разбивка если слишком длинное
        if len(report) > 4000:
            report = report[:3900] + "\n\n<i>... список слишком длинный, показана часть</i>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data='stock_reserves')],
            [InlineKeyboardButton(text="🔙 Назад", callback_data='stock_start')],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await callback.message.edit_text(report, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in view_reserves: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при загрузке резервов: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


# ============================================================================
# ВОЗВРАТ К НАЧАЛУ
# ============================================================================

@stock_router.callback_query(F.data == "stock_start")
async def back_to_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Возвращает к начальному меню просмотра остатков.
    """
    await callback.answer()
    await start_stock_view(callback, state, session)


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

@stock_router.callback_query(F.data.in_(["stock_cancel", "cancel"]))
@stock_router.message(Command("cancel"), StateFilter('*'))
async def cancel_stock_view(update: Message | CallbackQuery, state: FSMContext) -> None:
    """
    Закрывает просмотр остатков.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
    else:
        message = update
    
    # Очистка состояния
    await state.clear()
    
    await message.answer(
        "✅ Просмотр завершен.",
        reply_markup=get_main_menu_keyboard()
    )


__all__ = ['stock_router']
