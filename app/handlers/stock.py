"""
Обработчик команд просмотра остатков и статистики складов.

Этот модуль реализует функциональность для:
- Просмотра остатков по складам и типам номенклатуры
- Просмотра информации о бочках с полуфабрикатами
- Получения статистики по движениям
- Просмотра резервов и доступности
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from decimal import Decimal
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, SKUType
from app.services import (
    warehouse_service,
    stock_service,
    barrel_service
)
from app.utils.keyboards import (
    get_warehouses_keyboard,
    get_main_menu_keyboard
)


# Состояния диалога
(
    SELECT_ACTION,
    SELECT_WAREHOUSE,
    SELECT_SKU_TYPE,
    VIEW_DETAILS
) = range(4)


# ============================================================================
# НАЧАЛО ДИАЛОГА ПРОСМОТРА ОСТАТКОВ
# ============================================================================

async def start_stock_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс просмотра остатков.
    
    Команда: /stock или кнопка "Остатки"
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
    context.user_data['stock_view'] = {
        'user_id': user_id,
        'started_at': datetime.utcnow()
    }
    
    # Меню выбора действия
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Остатки по складам", callback_data='stock_by_warehouse')],
        [InlineKeyboardButton("🛢 Бочки с полуфабрикатами", callback_data='stock_barrels')],
        [InlineKeyboardButton("📊 Общая статистика", callback_data='stock_overall')],
        [InlineKeyboardButton("🔒 Резервы", callback_data='stock_reserves')],
        [InlineKeyboardButton("❌ Отменить", callback_data='stock_cancel')]
    ])
    
    text = (
        "📊 <b>Просмотр остатков и статистики</b>\n\n"
        "Выберите действие:"
    )
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    return SELECT_ACTION


# ============================================================================
# ОСТАТКИ ПО СКЛАДАМ
# ============================================================================

async def view_by_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список складов для просмотра остатков.
    """
    query = update.callback_query
    await query.answer()
    
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
        
        # Клавиатура выбора склада
        keyboard = get_warehouses_keyboard(warehouses, callback_prefix='stock_wh')
        
        text = (
            "📦 <b>Остатки по складам</b>\n\n"
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


async def select_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор склада и показывает меню типов номенклатуры.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID склада
    warehouse_id = int(query.data.split('_')[-1])
    context.user_data['stock_view']['warehouse_id'] = warehouse_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Загрузка информации о складе
        warehouse = await warehouse_service.get_warehouse(session, warehouse_id)
        context.user_data['stock_view']['warehouse_name'] = warehouse.name
        
        # Меню выбора типа номенклатуры
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌾 Сырье", callback_data='stock_type_raw')],
            [InlineKeyboardButton("🛢 Полуфабрикаты", callback_data='stock_type_semi')],
            [InlineKeyboardButton("📦 Готовая продукция", callback_data='stock_type_finished')],
            [InlineKeyboardButton("📋 Все категории", callback_data='stock_type_all')],
            [InlineKeyboardButton("🔙 Назад", callback_data='stock_by_warehouse')],
            [InlineKeyboardButton("❌ Отменить", callback_data='stock_cancel')]
        ])
        
        text = (
            f"📦 <b>Склад:</b> {warehouse.name}\n\n"
            "Выберите категорию номенклатуры:"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_SKU_TYPE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


async def view_stock_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает остатки по выбранному типу номенклатуры.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка остатков...")
    
    # Определение типа номенклатуры
    callback_data = query.data
    
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
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    data = context.user_data['stock_view']
    warehouse_id = data['warehouse_id']
    warehouse_name = data['warehouse_name']
    
    try:
        # Получение остатков
        if sku_type:
            stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse_id,
                sku_type=sku_type
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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=f'stock_wh_{warehouse_id}')],
                [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            return SELECT_SKU_TYPE
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=callback_data)],
            [InlineKeyboardButton("🔙 Назад", callback_data=f'stock_wh_{warehouse_id}')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await query.message.edit_text(
            report,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_SKU_TYPE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке остатков: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР БОЧЕК
# ============================================================================

async def view_barrels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список складов для просмотра бочек.
    """
    query = update.callback_query
    await query.answer()
    
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
        
        # Клавиатура выбора склада
        keyboard_buttons = []
        for warehouse in warehouses:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    warehouse.name,
                    callback_data=f'stock_barrels_wh_{warehouse.id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 Назад", callback_data='stock_start'),
            InlineKeyboardButton("❌ Отменить", callback_data='stock_cancel')
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text = (
            "🛢 <b>Бочки с полуфабрикатами</b>\n\n"
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


async def view_barrels_by_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список бочек на выбранном складе.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка бочек...")
    
    # Извлечение ID склада
    warehouse_id = int(query.data.split('_')[-1])
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='stock_barrels')],
                [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            return SELECT_WAREHOUSE
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data=f'stock_barrels_wh_{warehouse_id}')],
            [InlineKeyboardButton("🔙 Назад", callback_data='stock_barrels')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await query.message.edit_text(
            report,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_WAREHOUSE
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке бочек: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ОБЩАЯ СТАТИСТИКА
# ============================================================================

async def view_overall_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает общую статистику по всем складам.
    """
    query = update.callback_query
    await query.answer("⏳ Подготовка статистики...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение всех складов
        warehouses = await warehouse_service.get_warehouses(session, active_only=True)
        
        if not warehouses:
            await query.message.edit_text(
                "❌ Нет доступных складов.",
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
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
                sku_type=SKUType.RAW
            )
            
            semi_stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse.id,
                sku_type=SKUType.SEMI_FINISHED
            )
            
            finished_stocks = await stock_service.get_stock_by_warehouse_and_type(
                session,
                warehouse_id=warehouse.id,
                sku_type=SKUType.FINISHED
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data='stock_overall')],
            [InlineKeyboardButton("🔙 Назад", callback_data='stock_start')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await query.message.edit_text(
            report,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_ACTION
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при подготовке статистики: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ПРОСМОТР РЕЗЕРВОВ
# ============================================================================

async def view_reserves(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает активные резервы по всем складам.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка резервов...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение всех активных резервов
        from app.database.models import InventoryReserve
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
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
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='stock_start')],
                [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
            ])
            
            await query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            return SELECT_ACTION
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data='stock_reserves')],
            [InlineKeyboardButton("🔙 Назад", callback_data='stock_start')],
            [InlineKeyboardButton("❌ Закрыть", callback_data='stock_cancel')]
        ])
        
        await query.message.edit_text(
            report,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return SELECT_ACTION
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке резервов: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END


# ============================================================================
# ВОЗВРАТ К НАЧАЛУ
# ============================================================================

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Возвращает к начальному меню просмотра остатков.
    """
    query = update.callback_query
    await query.answer()
    
    return await start_stock_view(update, context)


# ============================================================================
# ОТМЕНА ДИАЛОГА
# ============================================================================

async def cancel_stock_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Закрывает просмотр остатков.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('stock_view', None)
    
    await message.reply_text(
        "✅ Просмотр завершен.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_stock_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для просмотра остатков.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('stock', start_stock_view),
            CallbackQueryHandler(start_stock_view, pattern='^stock_view_start$')
        ],
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(view_by_warehouse, pattern='^stock_by_warehouse$'),
                CallbackQueryHandler(view_barrels, pattern='^stock_barrels$'),
                CallbackQueryHandler(view_overall_statistics, pattern='^stock_overall$'),
                CallbackQueryHandler(view_reserves, pattern='^stock_reserves$'),
                CallbackQueryHandler(back_to_start, pattern='^stock_start$'),
                CallbackQueryHandler(cancel_stock_view, pattern='^stock_cancel$')
            ],
            SELECT_WAREHOUSE: [
                CallbackQueryHandler(select_warehouse, pattern='^stock_wh_\\d+$'),
                CallbackQueryHandler(view_barrels_by_warehouse, pattern='^stock_barrels_wh_\\d+$'),
                CallbackQueryHandler(view_by_warehouse, pattern='^stock_by_warehouse$'),
                CallbackQueryHandler(view_barrels, pattern='^stock_barrels$'),
                CallbackQueryHandler(back_to_start, pattern='^stock_start$'),
                CallbackQueryHandler(cancel_stock_view, pattern='^stock_cancel$')
            ],
            SELECT_SKU_TYPE: [
                CallbackQueryHandler(view_stock_by_type, pattern='^stock_type_'),
                CallbackQueryHandler(select_warehouse, pattern='^stock_wh_\\d+$'),
                CallbackQueryHandler(view_by_warehouse, pattern='^stock_by_warehouse$'),
                CallbackQueryHandler(back_to_start, pattern='^stock_start$'),
                CallbackQueryHandler(cancel_stock_view, pattern='^stock_cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_stock_view),
            CallbackQueryHandler(cancel_stock_view, pattern='^cancel$')
        ],
        name='stock_view_conversation',
        persistent=False
    )
