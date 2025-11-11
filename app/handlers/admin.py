"""
Обработчик команд администрирования (aiogram 3.x).

Этот модуль реализует функциональность для администраторов:
- Просмотр списка ожидающих утверждения пользователей
- Утверждение/отклонение пользователей
- Управление правами доступа пользователей
- Просмотр списка всех пользователей
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.models import User, ApprovalStatus
from app.utils.logger import get_logger
from app.utils.keyboards import get_main_menu_keyboard

logger = get_logger("admin_handler")

# Создаём роутер для admin handlers
admin_router = Router(name="admin")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class AdminStates(StatesGroup):
    """Состояния диалога администрирования."""
    main_menu = State()
    view_pending_users = State()
    manage_user = State()
    view_all_users = State()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню админа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Ожидают утверждения", callback_data='admin_pending')],
        [InlineKeyboardButton(text="📋 Все пользователи", callback_data='admin_all_users')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_back')],
    ])


def get_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления пользователем."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Утвердить", callback_data=f'admin_approve_{user_id}')],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f'admin_reject_{user_id}')],
        [InlineKeyboardButton(text="⚙️ Права доступа", callback_data=f'admin_permissions_{user_id}')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_pending')],
    ])


def get_permissions_keyboard(user_id: int, user: User) -> InlineKeyboardMarkup:
    """Клавиатура для управления правами пользователя."""
    buttons = []

    # Приемка сырья
    receive_icon = "✅" if user.can_receive_materials else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{receive_icon} Приемка сырья",
        callback_data=f'admin_toggle_receive_{user_id}'
    )])

    # Производство
    produce_icon = "✅" if user.can_produce else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{produce_icon} Производство",
        callback_data=f'admin_toggle_produce_{user_id}'
    )])

    # Фасовка
    pack_icon = "✅" if user.can_pack else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{pack_icon} Фасовка",
        callback_data=f'admin_toggle_pack_{user_id}'
    )])

    # Отгрузка
    ship_icon = "✅" if user.can_ship else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{ship_icon} Отгрузка",
        callback_data=f'admin_toggle_ship_{user_id}'
    )])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f'admin_user_{user_id}')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# КОМАНДА /ADMIN
# ============================================================================

@admin_router.message(Command("admin"))
@admin_router.callback_query(F.data == "admin_start")
async def admin_command(
    update: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """
    Главное меню администрирования.

    Команда: /admin или кнопка "Администрирование"
    """
    # Определяем тип update
    if isinstance(update, CallbackQuery):
        await update.answer()
        message = update.message
        user = update.from_user
    else:
        message = update
        user = update.from_user

    # Получение пользователя из БД
    stmt = select(User).where(User.telegram_id == user.id)
    db_user = await session.scalar(stmt)

    if not db_user:
        await message.answer(
            "❌ Пользователь не найден. Используйте /start для регистрации."
        )
        return

    # Проверка прав администратора
    if not db_user.is_admin:
        await message.answer(
            "❌ У вас нет прав администратора."
        )
        return

    # Получение статистики
    pending_count = await session.scalar(
        select(func.count(User.id)).where(User.approval_status == ApprovalStatus.pending)
    )

    text = (
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"⏳ Ожидают утверждения: <b>{pending_count}</b> польз.\n\n"
        "Выберите действие:"
    )

    keyboard = get_admin_menu_keyboard()

    if isinstance(update, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

    await state.set_state(AdminStates.main_menu)


# ============================================================================
# ПРОСМОТР ОЖИДАЮЩИХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================================

@admin_router.callback_query(F.data == "admin_pending")
async def view_pending_users(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает список пользователей, ожидающих утверждения."""
    await callback.answer()

    # Получение pending пользователей
    stmt = select(User).where(User.approval_status == ApprovalStatus.pending).order_by(User.created_at)
    result = await session.execute(stmt)
    pending_users = result.scalars().all()

    if not pending_users:
        await callback.message.edit_text(
            "👥 <b>Ожидающие утверждения</b>\n\n"
            "✅ Нет пользователей, ожидающих утверждения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')]
            ])
        )
        return

    # Формирование списка с кнопками
    text = "👥 <b>Пользователи, ожидающие утверждения:</b>\n\n"

    buttons = []
    for user in pending_users:
        username = f"@{user.username}" if user.username else "без username"
        text += f"• {user.full_name or 'Без имени'} ({username})\n"
        text += f"  ID: <code>{user.telegram_id}</code>\n"
        text += f"  Зарегистрирован: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"👤 {user.full_name or user.username or user.telegram_id}",
            callback_data=f'admin_user_{user.id}'
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data='admin_start')])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    await state.set_state(AdminStates.view_pending_users)


# ============================================================================
# УПРАВЛЕНИЕ КОНКРЕТНЫМ ПОЛЬЗОВАТЕЛЕМ
# ============================================================================

@admin_router.callback_query(F.data.startswith("admin_user_"))
async def manage_user(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает информацию о пользователе и кнопки управления."""
    await callback.answer()

    user_id = int(callback.data.split('_')[-1])

    # Получение пользователя
    user = await session.get(User, user_id)

    if not user:
        await callback.message.edit_text(
            "❌ Пользователь не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data='admin_pending')]
            ])
        )
        return

    # Формирование информации о пользователе
    status_emoji = {
        ApprovalStatus.pending: "⏳",
        ApprovalStatus.approved: "✅",
        ApprovalStatus.rejected: "❌"
    }

    text = (
        "👤 <b>Информация о пользователе</b>\n\n"
        f"ФИО: <b>{user.full_name or 'Не указано'}</b>\n"
        f"Username: @{user.username or 'не указан'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Статус: {status_emoji.get(user.approval_status, '❓')} {user.approval_status.value}\n\n"
        f"<b>Права доступа:</b>\n"
        f"{'✅' if user.can_receive_materials else '❌'} Приемка сырья\n"
        f"{'✅' if user.can_produce else '❌'} Производство\n"
        f"{'✅' if user.can_pack else '❌'} Фасовка\n"
        f"{'✅' if user.can_ship else '❌'} Отгрузка\n\n"
        f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Активность: {user.last_active.strftime('%d.%m.%Y %H:%M') if user.last_active else 'Никогда'}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_user_keyboard(user_id)
    )

    await state.set_state(AdminStates.manage_user)


# ============================================================================
# УТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@admin_router.callback_query(F.data.startswith("admin_approve_"))
async def approve_user(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Утверждает пользователя."""
    await callback.answer()

    user_id = int(callback.data.split('_')[-1])

    # Получение пользователя
    user = await session.get(User, user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    # Утверждение
    user.approval_status = ApprovalStatus.approved

    # Даем базовые права работника (arrival, production, packing, shipment)
    user.can_receive_materials = True
    user.can_produce = True
    user.can_pack = True
    user.can_ship = True

    await session.commit()

    # Уведомление пользователя
    try:
        bot = callback.bot
        await bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "✅ <b>Ваша регистрация утверждена!</b>\n\n"
                "Теперь у вас есть доступ к системе.\n"
                "Используйте /start для начала работы."
            )
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user.telegram_id}: {e}")

    await callback.answer("✅ Пользователь утвержден", show_alert=True)

    # Обновление информации
    await manage_user(callback, state, session)


# ============================================================================
# ОТКЛОНЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================================

@admin_router.callback_query(F.data.startswith("admin_reject_"))
async def reject_user(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Отклоняет пользователя."""
    await callback.answer()

    user_id = int(callback.data.split('_')[-1])

    # Получение пользователя
    user = await session.get(User, user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    # Отклонение
    user.approval_status = ApprovalStatus.rejected
    user.can_receive_materials = False
    user.can_produce = False
    user.can_pack = False
    user.can_ship = False

    await session.commit()

    # Уведомление пользователя
    try:
        bot = callback.bot
        await bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "❌ <b>Ваша регистрация была отклонена.</b>\n\n"
                "Обратитесь к администратору для уточнения деталей."
            )
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user.telegram_id}: {e}")

    await callback.answer("❌ Пользователь отклонен", show_alert=True)

    # Обновление информации
    await manage_user(callback, state, session)


# ============================================================================
# УПРАВЛЕНИЕ ПРАВАМИ ДОСТУПА
# ============================================================================

@admin_router.callback_query(F.data.startswith("admin_permissions_"))
async def manage_permissions(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показывает меню управления правами пользователя."""
    await callback.answer()

    user_id = int(callback.data.split('_')[-1])

    # Получение пользователя
    user = await session.get(User, user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    text = (
        f"⚙️ <b>Права доступа</b>\n\n"
        f"Пользователь: <b>{user.full_name or user.username}</b>\n\n"
        f"Нажмите на операцию для переключения доступа:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_permissions_keyboard(user_id, user)
    )


# ============================================================================
# ПЕРЕКЛЮЧЕНИЕ ПРАВ ДОСТУПА
# ============================================================================

@admin_router.callback_query(F.data.startswith("admin_toggle_"))
async def toggle_permission(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Переключает конкретное право пользователя."""
    await callback.answer()

    # Парсинг callback_data: admin_toggle_{permission}_{user_id}
    parts = callback.data.split('_')
    permission = parts[2]  # receive, produce, pack, ship
    user_id = int(parts[3])

    # Получение пользователя
    user = await session.get(User, user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    # Переключение права
    if permission == 'receive':
        user.can_receive_materials = not user.can_receive_materials
        perm_name = "Приемка сырья"
    elif permission == 'produce':
        user.can_produce = not user.can_produce
        perm_name = "Производство"
    elif permission == 'pack':
        user.can_pack = not user.can_pack
        perm_name = "Фасовка"
    elif permission == 'ship':
        user.can_ship = not user.can_ship
        perm_name = "Отгрузка"
    else:
        await callback.answer("❌ Неизвестное право", show_alert=True)
        return

    await session.commit()

    status = "включено" if getattr(user, f'can_{permission}') else "выключено"
    await callback.answer(f"✅ {perm_name}: {status}")

    # Обновление клавиатуры
    await manage_permissions(callback, state, session)


# ============================================================================
# ВОЗВРАТ В ГЛАВНОЕ МЕНЮ
# ============================================================================

# ============================================================================
# ОБРАБОТЧИК КНОПКИ "⚙️ УПРАВЛЕНИЕ"
# ============================================================================

@admin_router.message(F.text == "⚙️ Управление")
async def management_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Меню управления (аналог /admin)."""
    # Проверяем, что пользователь является администратором
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    db_user = await session.scalar(stmt)

    if not db_user or not db_user.is_admin:
        await message.answer(
            "❌ У вас нет прав доступа к этой функции.",
            reply_markup=get_main_menu_keyboard(False)
        )
        return

    # Отображение меню администрирования
    text = (
        "⚙️ <b>Меню управления</b>\n\n"
        "Выберите действие:"
    )

    await message.answer(text, reply_markup=get_admin_menu_keyboard())
    await state.set_state(AdminStates.main_menu)


@admin_router.callback_query(F.data == "admin_back")
async def admin_back(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Возврат в главное меню бота."""
    await callback.answer()

    # Получение пользователя
    stmt = select(User).where(User.telegram_id == callback.from_user.id)
    db_user = await session.scalar(stmt)

    await callback.message.edit_text(
        "👋 Главное меню",
        reply_markup=get_main_menu_keyboard(db_user)
    )

    await state.clear()
