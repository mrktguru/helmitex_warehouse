"""
Административный обработчик управления пользователями и правами доступа.

Этот модуль реализует функциональность для:
- Просмотра списка пользователей
- Поиска пользователей
- Управления правами доступа
- Просмотра статистики пользователей
- Блокировки/разблокировки пользователей

Конвертировано на aiogram 3.x с использованием FSM (StatesGroup).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Union

from app.database.models import (
    User, Movement, ProductionBatch, Shipment
)
from app.utils.keyboards import (
    get_confirmation_keyboard,
    get_cancel_keyboard,
    get_main_menu_keyboard
)
from app.validators.input_validators import validate_text_length
from app.utils.logger import get_logger

# Настройка логирования
logger = get_logger(__name__)


# ============================================================================
# FSM СОСТОЯНИЯ
# ============================================================================

class AdminUsersStates(StatesGroup):
    """Состояния FSM для управления пользователями."""
    users_menu = State()              # Главное меню управления пользователями
    list_users = State()              # Список пользователей
    search_user_input = State()       # Ввод для поиска пользователя
    view_user_details = State()       # Детали пользователя
    manage_permissions = State()      # Управление правами
    toggle_permission = State()       # Переключение права
    confirm_permission_change = State()  # Подтверждение изменения права
    view_user_statistics = State()    # Статистика пользователя
    block_user_reason = State()       # Ввод причины блокировки
    confirm_block_user = State()      # Подтверждение блокировки
    confirm_unblock_user = State()    # Подтверждение разблокировки


# ============================================================================
# РОУТЕР
# ============================================================================

router = Router(name='admin_users')


# ============================================================================
# МЕНЮ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ
# ============================================================================

@router.message(Command('users_admin'))
@router.callback_query(F.data == 'admin_users')
async def users_menu(
    event: Union[Message, CallbackQuery],
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Показывает главное меню управления пользователями.
    
    Доступно из /admin -> "Пользователи"
    """
    # Определение типа события
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        user_id = event.from_user.id
    else:
        message = event
        user_id = event.from_user.id
    
    # Получение пользователя по telegram_id
    stmt = select(User).where(User.telegram_id == user_id)
    user = await session.scalar(stmt)

    if not user or not user.is_admin:
        await message.answer("❌ У вас нет административных прав.")
        await state.clear()
        return
    
    # Инициализация данных
    await state.update_data(
        admin_id=user_id,
        started_at=datetime.utcnow().isoformat()
    )
    
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
    except Exception as e:
        logger.warning(f"Failed to get user stats: {e}")
        stats_text = ""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data='users_list')],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data='users_search')],
        [InlineKeyboardButton(text="🔙 Назад к админке", callback_data='admin_start')],
        [InlineKeyboardButton(text="❌ Выход", callback_data='users_exit')]
    ])
    
    text = (
        "👥 <b>Управление пользователями</b>\n\n"
        f"{stats_text}"
        "Выберите действие:"
    )
    
    if isinstance(event, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    
    await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ============================================================================

@router.callback_query(AdminUsersStates.users_menu, F.data == 'users_list')
async def list_users(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает список всех пользователей.
    """
    await query.answer("⏳ Загрузка пользователей...")
    
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
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='users_menu')]
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
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data='users_search')],
                [InlineKeyboardButton(text="🔙 Назад", callback_data='users_menu')]
            ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.list_users)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при загрузке пользователей: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# ПОИСК ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@router.callback_query(AdminUsersStates.users_menu, F.data == 'users_search')
@router.callback_query(AdminUsersStates.list_users, F.data == 'users_search')
async def search_user_start(query: CallbackQuery, state: FSMContext) -> None:
    """
    Запрашивает ввод для поиска пользователя.
    """
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
    
    await state.set_state(AdminUsersStates.search_user_input)


@router.message(AdminUsersStates.search_user_input, F.text)
async def search_user_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает поиск пользователя.
    """
    user_input = message.text.strip()
    
    try:
        # Поиск пользователя
        found_user = None
        
        # Поиск по ID
        if user_input.isdigit():
            search_id = int(user_input)

            # Сначала поиск по внутреннему ID
            found_user = await session.get(User, search_id)

            # Если не найден по ID, попробовать по telegram_id
            if not found_user:
                stmt = select(User).where(User.telegram_id == search_id)
                found_user = await session.scalar(stmt)
        
        # Поиск по username
        if not found_user:
            search_username = user_input.lstrip('@')
            stmt = select(User).where(User.username.ilike(f"%{search_username}%"))
            found_user = await session.scalar(stmt)
        
        if not found_user:
            await message.answer(
                f"❌ Пользователь '{user_input}' не найден.\n\n"
                "Попробуйте другой запрос:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
                ])
            )
            return
        
        # Сохранение найденного пользователя
        await state.update_data(selected_user_id=found_user.id)
        
        # Показ деталей
        await view_user_details_from_message(message, state, session, found_user)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при поиске: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# ПРОСМОТР ДЕТАЛЕЙ ПОЛЬЗОВАТЕЛЯ
# ============================================================================

async def view_user_details_from_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User
) -> None:
    """
    Показывает детальную информацию о пользователе (из message).
    """
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
        InlineKeyboardButton(text="🔧 Управление правами", callback_data=f'user_perms_{user.id}')
    ])
    
    # Статистика
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data=f'user_stats_{user.id}')
    ])
    
    # Блокировка/разблокировка (но не самого себя)
    data = await state.get_data()
    current_admin_id = data.get('admin_id')
    
    if user.id != current_admin_id:
        if user.is_active:
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f'user_block_{user.id}')
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton(text="✅ Разблокировать", callback_data=f'user_unblock_{user.id}')
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminUsersStates.view_user_details)


@router.callback_query(AdminUsersStates.view_user_details, F.data.startswith('user_view_'))
@router.callback_query(AdminUsersStates.toggle_permission, F.data.startswith('user_view_'))
@router.callback_query(AdminUsersStates.view_user_statistics, F.data.startswith('user_view_'))
async def view_user_details(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает детальную информацию о пользователе (из callback).
    """
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    await state.update_data(selected_user_id=user_id)
    
    user = await session.get(User, user_id)
    if not user:
        await query.message.edit_text("❌ Пользователь не найден.")
        await state.set_state(AdminUsersStates.users_menu)
        return
    
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
        InlineKeyboardButton(text="🔧 Управление правами", callback_data=f'user_perms_{user.id}')
    ])
    
    # Статистика
    keyboard_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data=f'user_stats_{user.id}')
    ])
    
    # Блокировка/разблокировка (но не самого себя)
    data = await state.get_data()
    current_admin_id = data.get('admin_id')
    
    if user.id != current_admin_id:
        if user.is_active:
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f'user_block_{user.id}')
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton(text="✅ Разблокировать", callback_data=f'user_unblock_{user.id}')
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminUsersStates.view_user_details)


# ============================================================================
# УПРАВЛЕНИЕ ПРАВАМИ
# ============================================================================

@router.callback_query(AdminUsersStates.view_user_details, F.data.startswith('user_perms_'))
@router.callback_query(AdminUsersStates.toggle_permission, F.data.startswith('user_perms_'))
async def manage_permissions(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает меню управления правами пользователя.
    """
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    await state.update_data(selected_user_id=user_id)
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
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
                text=f"📥 Приемка сырья: {receive_status}",
                callback_data=f'perm_receive_{user_id}'
            )
        ])
        
        # Производство
        produce_status = "✅ Включено" if user.can_produce else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🏭 Производство: {produce_status}",
                callback_data=f'perm_produce_{user_id}'
            )
        ])
        
        # Фасовка
        pack_status = "✅ Включено" if user.can_pack else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📦 Фасовка: {pack_status}",
                callback_data=f'perm_pack_{user_id}'
            )
        ])
        
        # Отгрузка
        ship_status = "✅ Включено" if user.can_ship else "❌ Отключено"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🚚 Отгрузка: {ship_status}",
                callback_data=f'perm_ship_{user_id}'
            )
        ])
        
        # Администратор (только если не последний админ)
        data = await state.get_data()
        current_admin_id = data.get('admin_id')
        
        if user.id != current_admin_id:  # Нельзя забрать права у самого себя
            admin_status = "✅ Включено" if user.is_admin else "❌ Отключено"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"👑 Администратор: {admin_status}",
                    callback_data=f'perm_admin_{user_id}'
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 К пользователю", callback_data=f'user_view_{user_id}'),
            InlineKeyboardButton(text="🏠 К пользователям", callback_data='users_menu')
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.manage_permissions)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


@router.callback_query(AdminUsersStates.manage_permissions, F.data.startswith('perm_'))
async def toggle_permission(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Переключает право пользователя.
    """
    await query.answer()
    
    # Парсинг callback_data
    parts = query.data.split('_')
    permission_type = parts[1]  # receive, produce, pack, ship, admin
    user_id = int(parts[-1])
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
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
            await state.set_state(AdminUsersStates.manage_permissions)
            return
        
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
                return
        
        # Сохранение изменений
        setattr(user, field_name, new_value)
        user.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(user)
        
        # Уведомление
        text = (
            f"✅ <b>Право изменено!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
            f"{emoji} <b>Право:</b> {display_name}\n"
            f"📊 <b>Статус:</b> {'✅ Включено' if new_value else '❌ Отключено'}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔧 Продолжить управление", callback_data=f'user_perms_{user_id}')],
            [InlineKeyboardButton(text="🔙 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton(text="🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.toggle_permission)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при изменении права: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@router.callback_query(AdminUsersStates.view_user_details, F.data.startswith('user_stats_'))
async def view_user_statistics(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Показывает статистику операций пользователя.
    """
    await query.answer("⏳ Подготовка статистики...")
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
        # Подсчет операций
        movements_count = await session.scalar(
            select(func.count(Movement.id)).where(Movement.user_id == user_id)
        )
        
        production_count = await session.scalar(
            select(func.count(ProductionBatch.id)).where(ProductionBatch.user_id == user_id)
        )
        
        shipments_count = await session.scalar(
            select(func.count(Shipment.id)).where(Shipment.user_id == user_id)
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton(text="🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.view_user_statistics)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при подготовке статистики: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@router.callback_query(AdminUsersStates.view_user_details, F.data.startswith('user_block_'))
async def block_user_start(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Запрашивает причину блокировки.
    """
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    await state.update_data(block_user_id=user_id)
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
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
        
        await state.set_state(AdminUsersStates.block_user_reason)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


@router.message(AdminUsersStates.block_user_reason, F.text)
async def block_user_reason(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """
    Обрабатывает ввод причины блокировки.
    """
    user_input = message.text.strip()
    
    # Валидация
    validation = validate_text_length(user_input, min_length=3, max_length=500)
    
    if not validation['valid']:
        await message.answer(
            f"❌ {validation['error']}\n\n"
            "Попробуйте снова:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Сохранение причины
    await state.update_data(block_reason=user_input)
    
    data = await state.get_data()
    user_id = data.get('block_user_id')
    user = await session.get(User, user_id)
    
    text = (
        f"🔒 <b>Подтверждение блокировки</b>\n\n"
        f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n"
        f"📝 <b>Причина:</b> {user_input}\n\n"
        "⚠️ Пользователь будет заблокирован и не сможет использовать систему.\n\n"
        "❓ Подтвердить блокировку?"
    )
    
    await message.answer(
        text,
        reply_markup=get_confirmation_keyboard(
            confirm_callback='user_confirm_block',
            cancel_callback='users_menu'
        ),
        parse_mode='HTML'
    )
    
    await state.set_state(AdminUsersStates.confirm_block_user)


@router.callback_query(AdminUsersStates.confirm_block_user, F.data == 'user_confirm_block')
async def confirm_block_user(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполняет блокировку пользователя.
    """
    await query.answer("⏳ Блокировка пользователя...")
    
    data = await state.get_data()
    user_id = data.get('block_user_id')
    reason = data.get('block_reason')
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
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
        await state.update_data(block_user_id=None, block_reason=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton(text="🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.users_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при блокировке: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# РАЗБЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@router.callback_query(AdminUsersStates.view_user_details, F.data.startswith('user_unblock_'))
async def unblock_user(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Разблокирует пользователя с подтверждением.
    """
    await query.answer()
    
    # Извлечение ID пользователя
    user_id = int(query.data.split('_')[-1])
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
        text = (
            f"✅ <b>Разблокировка пользователя</b>\n\n"
            f"👤 <b>Пользователь:</b> @{user.username or f'ID:{user.telegram_id}'}\n\n"
            "Пользователь получит доступ к системе.\n\n"
            "❓ Подтвердить разблокировку?"
        )
        
        await state.update_data(unblock_user_id=user_id)
        
        await query.message.edit_text(
            text,
            reply_markup=get_confirmation_keyboard(
                confirm_callback='user_confirm_unblock',
                cancel_callback=f'user_view_{user_id}'
            ),
            parse_mode='HTML'
        )
        
        await state.set_state(AdminUsersStates.confirm_unblock_user)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


@router.callback_query(AdminUsersStates.confirm_unblock_user, F.data == 'user_confirm_unblock')
async def confirm_unblock_user(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """
    Выполняет разблокировку пользователя.
    """
    await query.answer("⏳ Разблокировка...")
    
    data = await state.get_data()
    user_id = data.get('unblock_user_id')
    
    try:
        user = await session.get(User, user_id)
        if not user:
            await query.message.edit_text("❌ Пользователь не найден.")
            await state.set_state(AdminUsersStates.users_menu)
            return
        
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
        await state.update_data(unblock_user_id=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К пользователю", callback_data=f'user_view_{user_id}')],
            [InlineKeyboardButton(text="🏠 К пользователям", callback_data='users_menu')]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await state.set_state(AdminUsersStates.users_menu)
        
    except Exception as e:
        await query.message.edit_text(
            f"❌ Ошибка при разблокировке: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К пользователям", callback_data='users_menu')]
            ])
        )
        await state.set_state(AdminUsersStates.users_menu)


# ============================================================================
# НАВИГАЦИЯ И ОТМЕНА
# ============================================================================

@router.callback_query(StateFilter(AdminUsersStates), F.data == 'users_menu')
async def back_to_users_menu(query: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат в главное меню управления пользователями."""
    await users_menu(query, state, session)


@router.callback_query(F.data == 'users_exit')
@router.message(Command('cancel'), StateFilter(AdminUsersStates))
async def cancel_users_admin(event: Union[Message, CallbackQuery], state: FSMContext) -> None:
    """
    Выходит из управления пользователями.
    """
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event
    
    # Очистка данных
    await state.clear()
    
    text = "✅ Управление пользователями завершено."
    
    if isinstance(event, CallbackQuery):
        await message.edit_text(text, parse_mode='HTML')
    else:
        await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode='HTML')



# Export router with expected name
admin_users_router = router

__all__ = ['admin_users_router']

