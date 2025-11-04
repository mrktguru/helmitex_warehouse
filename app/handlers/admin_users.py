"""
Административный обработчик управления пользователями и правами доступа.

Этот модуль реализует функциональность для:
- Просмотра списка пользователей
- Поиска пользователей
- Управления правами доступа
- Просмотра статистики пользователей
- Блокировки/разблокировки пользователей
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.database.models import (
    User, Movement, ProductionBatch, Shipment
)
from app.utils.keyboards import (
    get_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import validate_text_length


# Состояния диалога
(
    USERS_MENU,
    LIST_USERS,
    SEARCH_USER_INPUT,
    VIEW_USER_DETAILS,
    MANAGE_PERMISSIONS,
    TOGGLE_PERMISSION,
    CONFIRM_PERMISSION_CHANGE,
    VIEW_USER_STATISTICS,
    BLOCK_USER_REASON,
    CONFIRM_BLOCK_USER,
    CONFIRM_UNBLOCK_USER
) = range(11)


# ============================================================================
# МЕНЮ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ
# ============================================================================

async def users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает главное меню управления пользователями.
    
    Доступно из /admin -> "Пользователи"
    """
    query = update.callback_query
    
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
    
    if not user or not user.is_admin:
        await message.reply_text(
            "❌ У вас нет административных прав."
        )
        return ConversationHandler.END
    
    # Инициализация данных
    context.user_data['admin_users'] = {
        'admin_id': user_id,
        'started_at': datetime.utcnow()
    }
    
    # Статистика пользователей
    try:
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_active == True)
        )
        admin_users = await session.scalar(
            select(func.count(User.id)).where(User.is_admin == True)
        )
        
        stats_text = (
            f"📊 <b>Статистика:</b>\n"
            f"  • Всего пользователей: {total_users}\n"
            f"  • Активных: {active_users}\n"
            f"  • Администраторов: {admin_users}\n\n"
        )
    except:
        stats_text = ""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Список пользователей", callback_data='users_list')],
        [InlineKeyboardButton("🔍 Найти пользователя", callback_data='users_search')],
        [InlineKeyboardButton("🔙 Назад к админке", callback_data='admin_start')],
        [InlineKeyboardButton("❌ Выход", callback_data='users_exit')]
    ])
    
    text = (
        "👥 <b>Управление пользователями</b>\n\n"
        f"{stats_text}"
        "Выберите действие:"
    )
    
    if query:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return USERS_MENU


# ============================================================================
# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ============================================================================

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает список всех пользователей.
    """
    query = update.callback_query
    await query.answer("⏳ Загрузка пользователей...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Получение пользователей
        stmt = select(User).order_by(User.created_at.desc()).limit(50)
        result = await session.execute(stmt)
        users = list(result.scalars().all())
        
        if not users:
            text = (
                "📋 <b>Список пользователей</b>\n\n"
                "❌ Нет зарегистрированных пользователей."
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='users_menu')]
            ])
        else:
            text = f"📋 <b>Список пользователей ({len(users)})</b>\n\n"
            
            for user in users[:30]:  # Показываем первые 30
                # Иконки статуса
                status_icon = "✅" if user.is_active else "🔒"
                admin_icon = "👑" if user.is_admin else ""
                
                # Права доступа
                permissions = []
                if user.can_receive_materials:
                    permissions.append("📥")
                if user.can_produce:
                    permissions.append("🏭")
                if user.can_pack:
                    permissions.append("📦")
                if user.can_ship:
                    permissions.append("🚚")
                
                permissions_str = "".join(permissions) if permissions else "🚫"
                
                text += (
                    f"{status_icon} {admin_icon} "
                    f"<b>{user.username or f'ID:{user.telegram_id}'}</b> "
                    f"{permissions_str}\n"
                    f"   🆔 {user.id} | "
                    f"📅 {user.created_at.strftime('%d.%m.%Y')}\n\n"
                )
            
            if len(users) > 30:
                text += f"<i>... и еще {len(users) - 30} пользователей</i>\n\n"
            
            text += (
                "<b>Обозначения:</b>\n"
                "👑 - Администратор\n"
                "📥 - Приемка | 🏭 - Производство\n"
                "📦 - Фасовка | 🚚 - Отгрузка\n"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Найти пользователя", callback_data='users_search')],
                [InlineKeyboardButton("🔙 Назад", callback_data='users_menu')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return LIST_USERS
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке пользователей: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# ПОИСК ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрашивает ввод для поиска пользователя.
    """
    query = update.callback_query
    await query.answer()
    
    text = (
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите username, имя или ID пользователя:\n\n"
        "<i>Примеры: @username, Иван, 123456789</i>"
    )
    
    await query.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode='HTML'
    )
    
    return SEARCH_USER_INPUT


async def search_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает поиск пользователя.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        # Поиск пользователя
        found_user = None
        
        # Поиск по ID
        if user_input.isdigit():
            user_id = int(user_input)
            found_user = await session.get(User, user_id)
            
            # Если не найден по ID, попробовать по telegram_id
            if not found_user:
                stmt = select(User).where(User.telegram_id == user_id)
                found_user = await session.scalar(stmt)
        
        # Поиск по username
        if not found_user:
            search_username = user_input.lstrip('@')
            stmt = select(User).where(User.username.ilike(f"%{search_username}%"))
            found_user = await session.scalar(stmt)
        
        if not found_user:
            await message.reply_text(
                f"❌ Пользователь '{user_input}' не найден.\n\n"
                "Попробуйте другой запрос:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
                ])
            )
            return SEARCH_USER_INPUT
        
        # Сохранение найденного пользователя
        context.user_data['admin_users']['selected_user_id'] = found_user.id
        
        # Показ деталей
        return await view_user_details(update, context, found_user)
        
    except Exception as e:
        await message.reply_text(
            f"❌ Ошибка при поиске: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# ПРОСМОТР ДЕТАЛЕЙ ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def view_user_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> int:
    """
    Показывает детальную информацию о пользователе.
    """
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    # Если пользователь не передан, загружаем из контекста
    if not user:
        user_id = context.user_data['admin_users'].get('selected_user_id')
        if not user_id:
            await message.reply_text("❌ Пользователь не выбран.")
            return USERS_MENU
        
        user = await session.get(User, user_id)
        if not user:
            await message.reply_text("❌ Пользователь не найден.")
            return USERS_MENU
    
    # Формирование карточки пользователя
    status = "✅ Активен" if user.is_active else "🔒 Заблокирован"
    role = "👑 Администратор" if user.is_admin else "👤 Пользователь"
    
    # Права доступа
    permissions_text = "<b>Права доступа:</b>\n"
    permissions_text += f"  📥 Приемка сырья: {'✅' if user.can_receive_materials else '❌'}\n"
    permissions_text += f"  🏭 Производство: {'✅' if user.can_produce else '❌'}\n"
    permissions_text += f"  📦 Фасовка: {'✅' if user.can_pack else '❌'}\n"
    permissions_text += f"  🚚 Отгрузка: {'✅' if user.can_ship else '❌'}\n"
    permissions_text += f"  👑 Администратор: {'✅' if user.is_admin else '❌'}\n"
    
    # Активность
    activity_text = ""
    if user.last_active:
        last_active = user.last_active
        time_diff = datetime.utcnow() - last_active
        
        if time_diff < timedelta(minutes=5):
            activity_str = "онлайн"
        elif time_diff < timedelta(hours=1):
            activity_str = f"{int(time_diff.total_seconds() / 60)} мин назад"
        elif time_diff < timedelta(days=1):
            activity_str = f"{int(time_diff.total_seconds() / 3600)} ч назад"
        else:
            activity_str = last_active.strftime('%d.%m.%Y %H:%M')
        
        activity_text = f"🕐 <b>Последняя активность:</b> {activity_str}\n"
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 <b>ID:</b> {user.id}\n"
        f"📱 <b>Telegram ID:</b> {user.telegram_id}\n"
        f"👤 <b>Username:</b> @{user.username or 'не указан'}\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"🎭 <b>Роль:</b> {role}\n"
        f"📅 <b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"{activity_text}\n"
        f"{permissions_text}"
    )
    
    # Кнопки действий
    keyboard_buttons = []
    
    # Управление правами
    keyboard_buttons.append([
        InlineKeyboardButton("🔧 Управление правами", callback_data=f'user_perms_{user.id}')
    ])
    
    # Статистика
    keyboard_buttons.append([
        InlineKeyboardButton("📊 Статистика", callback_data=f'user_stats_{user.id}')
    ])
    
    # Блокировка/разблокировка (но не самого себя)
    current_admin_id = context.user_data['admin_users']['admin_id']
    if user.id != current_admin_id:
        if user.is_active:
            keyboard_buttons.append([
                InlineKeyboardButton("🔒 Заблокировать", callback_data=f'user_block_{user.id}')
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton("✅ Разблокировать", callback_data=f'user_unblock_{user.id}')
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')
    ])
    
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    if update.callback_query:
        await message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    return VIEW_USER_DETAILS


# ============================================================================
# УПРАВЛЕНИЕ ПРАВАМИ
# ============================================================================

async def manage_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню управления правами пользователя.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    context.user_data['admin_users']['selected_user_id'] = user_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        # Формирование меню прав
        text = (
            f"🔧 <b>Управление правами</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n\n"
            "Выберите право для изменения:"
        )
        
        keyboard_buttons = []
        
        # Приемка
        receive_status = "✅ Включено" if user.can_receive_materials else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                f"📥 Приемка сырья: {receive_status}",
                callback_data=f'perm_receive_{user_id}'
            )
        ])
        
        # Производство
        produce_status = "✅ Включено" if user.can_produce else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                f"🏭 Производство: {produce_status}",
                callback_data=f'perm_produce_{user_id}'
            )
        ])
        
        # Фасовка
        pack_status = "✅ Включено" if user.can_pack else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                f"📦 Фасовка: {pack_status}",
                callback_data=f'perm_pack_{user_id}'
            )
        ])
        
        # Отгрузка
        ship_status = "✅ Включено" if user.can_ship else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                f"🚚 Отгрузка: {ship_status}",
                callback_data=f'perm_ship_{user_id}'
            )
        ])
        
        # Администратор (только если не последний админ)
        current_admin_id = context.user_data['admin_users']['admin_id']
        if user.id != current_admin_id:  # Нельзя забрать права у самого себя
            admin_status = "✅ Включено" if user.is_admin else "❌ Отключено"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    f"👑 Администратор: {admin_status}",
                    callback_data=f'perm_admin_{user_id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 К пользователю", callback_data=f'user_view_{user_id}'),
            InlineKeyboardButton("🏠 К пользователям", callback_data='users_menu')
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return MANAGE_PERMISSIONS
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


async def toggle_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Переключает право пользователя.
    """
    query = update.callback_query
    await query.answer()
    
    # Парсинг callback_data
    parts = query.data.split('_')
    permission_type = parts[1]  # receive, produce, pack, ship, admin
    user_id = int(parts[-1])
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        # Определение изменяемого права
        permission_names = {
            'receive': ('can_receive_materials', 'Приемка сырья', '📥'),
            'produce': ('can_produce', 'Производство', '🏭'),
            'pack': ('can_pack', 'Фасовка', '📦'),
            'ship': ('can_ship', 'Отгрузка', '🚚'),
            'admin': ('is_admin', 'Администратор', '👑')
        }
        
        if permission_type not in permission_names:
            await query.message.edit_text("❌ Неизвестное право.")
            return MANAGE_PERMISSIONS
        
        field_name, display_name, emoji = permission_names[permission_type]
        current_value = getattr(user, field_name)
        new_value = not current_value
        
        # Проверка: нельзя забрать права администратора у последнего админа
        if permission_type == 'admin' and current_value and new_value == False:
            # Подсчет администраторов
            admin_count = await session.scalar(
                select(func.count(User.id)).where(User.is_admin == True)
            )
            
            if admin_count <= 1:
                await query.answer("❌ Нельзя забрать права у последнего администратора!", show_alert=True)
                return MANAGE_PERMISSIONS
        
        # Сохранение изменений
        setattr(user, field_name, new_value)
        user.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(user)
        
        # Уведомление
        action = "включено" if new_value else "отключено"
        text = (
            f"✅ <b>Право изменено!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
            f"{emoji} <b>Право:</b> {display_name}\n"
            f"📊 <b>Статус:</b> {'✅ Включено' if new_value else '❌ Отключено'}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔧 Продолжить управление", callback_data=f'user_perms_{user_id}')],
            [InlineKeyboardButton("🔙 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton("🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return TOGGLE_PERMISSION
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при изменении права: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def view_user_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает статистику операций пользователя.
    """
    query = update.callback_query
    await query.answer("⏳ Подготовка статистики...")
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        # Подсчет операций
        # Движения
        movements_count = await session.scalar(
            select(func.count(Movement.id)).where(Movement.performed_by_id == user_id)
        )
        
        # Производственные партии
        production_count = await session.scalar(
            select(func.count(ProductionBatch.id)).where(ProductionBatch.created_by_id == user_id)
        )
        
        # Отгрузки
        shipments_count = await session.scalar(
            select(func.count(Shipment.id)).where(Shipment.created_by_id == user_id)
        )
        
        # Период активности
        if user.last_active and user.created_at:
            days_active = (user.last_active - user.created_at).days
        else:
            days_active = 0
        
        text = (
            f"📊 <b>Статистика пользователя</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
            f"📅 <b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
            f"🕐 <b>Дней в системе:</b> {days_active}\n\n"
            f"<b>Выполненные операции:</b>\n"
            f"  📦 Движений товаров: {movements_count}\n"
            f"  🏭 Производственных партий: {production_count}\n"
            f"  🚚 Отгрузок: {shipments_count}\n\n"
            f"<b>Всего операций:</b> {movements_count + production_count + shipments_count}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton("🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return VIEW_USER_STATISTICS
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при подготовке статистики: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def block_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрашивает причину блокировки.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    context.user_data['admin_users']['block_user_id'] = user_id
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        text = (
            f"🔒 <b>Блокировка пользователя</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n\n"
            "📝 Введите причину блокировки:\n\n"
            "<i>Эта информация будет сохранена в системе</i>"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        
        return BLOCK_USER_REASON
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


async def block_user_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод причины блокировки.
    """
    message = update.message
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=500)
    
    if not validation['valid']:
        await message.reply_text(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return BLOCK_USER_REASON
    
    # Сохранение причины
    context.user_data['admin_users']['block_reason'] = user_input
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    user_id = context.user_data['admin_users']['block_user_id']
    user = await session.get(User, user_id)
    
    text = (
        f"🔒 <b>Подтверждение блокировки</b>\n\n"
        f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
        f"📝 <b>Причина:</b> {user_input}\n\n"
        "⚠️ Пользователь будет заблокирован и не сможет использовать систему.\n\n"
        "❓ Подтвердить блокировку?"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='user_confirm_block',
            cancel_callback='users_menu'
        ),
        parse_mode='HTML'
    )
    
    return CONFIRM_BLOCK_USER


async def confirm_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет блокировку пользователя.
    """
    query = update.callback_query
    await query.answer("⏳ Блокировка пользователя...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    user_id = context.user_data['admin_users']['block_user_id']
    reason = context.user_data['admin_users']['block_reason']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        # Блокировка
        user.is_active = False
        user.updated_at = datetime.utcnow()
        
        # Можно добавить поле для хранения причины блокировки в модели User
        # user.block_reason = reason
        
        await session.commit()
        await session.refresh(user)
        
        text = (
            f"✅ <b>Пользователь заблокирован!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
            f"📝 <b>Причина:</b> {reason}\n"
            f"📊 <b>Статус:</b> 🔒 Заблокирован"
        )
        
        # Очистка данных
        context.user_data['admin_users'].pop('block_user_id', None)
        context.user_data['admin_users'].pop('block_reason', None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton("🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return USERS_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при блокировке: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# РАЗБЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Разблокирует пользователя.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        text = (
            f"✅ <b>Разблокировка пользователя</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n\n"
            "Пользователь получит доступ к системе.\n\n"
            "❓ Подтвердить разблокировку?"
        )
        
        context.user_data['admin_users']['unblock_user_id'] = user_id
        
        await query.message.edit_text(
            text,
            reply_markup=get_confirmation_keyboard(
                confirm_callback='user_confirm_unblock',
                cancel_callback=f'user_view_{user_id}'
            ),
            parse_mode='HTML'
        )
        
        return CONFIRM_UNBLOCK_USER
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


async def confirm_unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выполняет разблокировку пользователя.
    """
    query = update.callback_query
    await query.answer("⏳ Разблокировка...")
    
    # Получение сессии БД
    session: AsyncSession = context.bot_data['db_session']
    
    user_id = context.user_data['admin_users']['unblock_user_id']
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            return USERS_MENU
        
        # Разблокировка
        user.is_active = True
        user.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(user)
        
        text = (
            f"✅ <b>Пользователь разблокирован!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
            f"📊 <b>Статус:</b> ✅ Активен"
        )
        
        # Очистка данных
        context.user_data['admin_users'].pop('unblock_user_id', None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton("🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
        return USERS_MENU
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при разблокировке: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        return USERS_MENU


# ============================================================================
# ВОЗВРАТ К ПОЛЬЗОВАТЕЛЮ
# ============================================================================

async def back_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Возвращает к карточке пользователя.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[-1])
    context.user_data['admin_users']['selected_user_id'] = user_id
    
    return await view_user_details(update, context)


# ============================================================================
# ОТМЕНА И ВЫХОД
# ============================================================================

async def cancel_users_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выходит из управления пользователями.
    """
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    # Очистка данных
    context.user_data.pop('admin_users', None)
    
    await message.reply_text(
        "✅ Управление пользователями завершено.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


# ============================================================================
# РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
# ============================================================================

def get_admin_users_handler() -> ConversationHandler:
    """
    Создает и возвращает ConversationHandler для управления пользователями.
    
    Returns:
        ConversationHandler: Настроенный обработчик диалога
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('users_admin', users_menu),
            CallbackQueryHandler(users_menu, pattern='^admin_users$')
        ],
        states={
            USERS_MENU: [
                CallbackQueryHandler(list_users, pattern='^users_list$'),
                CallbackQueryHandler(search_user_start, pattern='^users_search$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$'),
                CallbackQueryHandler(cancel_users_admin, pattern='^users_exit$')
            ],
            LIST_USERS: [
                CallbackQueryHandler(search_user_start, pattern='^users_search$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            SEARCH_USER_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_input)
            ],
            VIEW_USER_DETAILS: [
                CallbackQueryHandler(manage_permissions, pattern='^user_perms_\\d+$'),
                CallbackQueryHandler(view_user_statistics, pattern='^user_stats_\\d+$'),
                CallbackQueryHandler(block_user_start, pattern='^user_block_\\d+$'),
                CallbackQueryHandler(unblock_user, pattern='^user_unblock_\\d+$'),
                CallbackQueryHandler(back_to_user, pattern='^user_view_\\d+$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            MANAGE_PERMISSIONS: [
                CallbackQueryHandler(toggle_permission, pattern='^perm_'),
                CallbackQueryHandler(back_to_user, pattern='^user_view_\\d+$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            TOGGLE_PERMISSION: [
                CallbackQueryHandler(manage_permissions, pattern='^user_perms_\\d+$'),
                CallbackQueryHandler(back_to_user, pattern='^user_view_\\d+$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            VIEW_USER_STATISTICS: [
                CallbackQueryHandler(back_to_user, pattern='^user_view_\\d+$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            BLOCK_USER_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, block_user_reason)
            ],
            CONFIRM_BLOCK_USER: [
                CallbackQueryHandler(confirm_block_user, pattern='^user_confirm_block$'),
                CallbackQueryHandler(users_menu, pattern='^users_menu$')
            ],
            CONFIRM_UNBLOCK_USER: [
                CallbackQueryHandler(confirm_unblock_user, pattern='^user_confirm_unblock$'),
                CallbackQueryHandler(back_to_user, pattern='^user_view_\\d+$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_users_admin),
            CallbackQueryHandler(cancel_users_admin, pattern='^cancel$')
        ],
        name='admin_users_conversation',
        persistent=False
    )
