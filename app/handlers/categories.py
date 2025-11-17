"""
Обработчик для управления справочниками (aiogram 3.x).

Этот модуль реализует функциональность для:
- Просмотра списка категорий сырья
- Создания новых категорий
- Редактирования существующих категорий
- Удаления категорий
"""

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.models import User, Category, SKU
from app.services import category_service
from app.utils.logger import get_logger
from app.utils.keyboards import get_main_menu_keyboard

logger = get_logger("categories_handler")

# Создаём роутер для categories handlers
categories_router = Router(name="categories")


# ============================================================================
# СОСТОЯНИЯ FSM
# ============================================================================

class CategoryStates(StatesGroup):
    """Состояния диалога управления категориями."""
    main_menu = State()
    list_categories = State()
    create_name = State()
    create_code = State()
    create_description = State()
    edit_select_field = State()
    edit_name = State()
    edit_code = State()
    edit_description = State()
    edit_sort_order = State()
    confirm_delete = State()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def get_references_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню справочников."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Категории сырья", callback_data='ref_categories')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data='ref_back')],
    ])


def get_categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    """Клавиатура со списком категорий."""
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"{category.name} ({category.code})",
                callback_data=f'cat_view_{category.id}'
            )
        )

    builder.row(
        InlineKeyboardButton(text="➕ Добавить категорию", callback_data='cat_create')
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data='ref_main')
    )

    return builder.as_markup()


def get_category_view_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра категории."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Товары в категории", callback_data=f'cat_skus_{category_id}')],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f'cat_add_sku_{category_id}')],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f'cat_edit_{category_id}')],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f'cat_delete_{category_id}')],
        [InlineKeyboardButton(text="🔙 К списку", callback_data='cat_list')],
    ])


def get_category_edit_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора поля редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f'cat_edit_name_{category_id}')],
        [InlineKeyboardButton(text="Код", callback_data=f'cat_edit_code_{category_id}')],
        [InlineKeyboardButton(text="Описание", callback_data=f'cat_edit_desc_{category_id}')],
        [InlineKeyboardButton(text="Порядок сортировки", callback_data=f'cat_edit_sort_{category_id}')],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f'cat_view_{category_id}')],
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data='cat_cancel')],
    ])


def get_confirm_delete_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f'cat_delete_confirm_{category_id}')],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f'cat_view_{category_id}')],
    ])


# ============================================================================
# ОБРАБОТЧИК КНОПКИ "📚 СПРАВОЧНИКИ"
# ============================================================================

@categories_router.message(F.text == "📚 Справочники")
async def references_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Главное меню справочников."""
    # Проверяем, что пользователь является администратором
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    db_user = await session.scalar(stmt)

    if not db_user or not db_user.is_admin:
        await message.answer(
            "❌ У вас нет прав доступа к этой функции.",
            reply_markup=get_main_menu_keyboard(False)
        )
        return

    # Отображение меню справочников
    text = (
        "📚 <b>Справочники</b>\n\n"
        "Выберите справочник для управления:"
    )

    await message.answer(text, reply_markup=get_references_menu_keyboard())
    await state.set_state(CategoryStates.main_menu)


@categories_router.callback_query(F.data == "ref_main")
async def references_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Возврат в главное меню справочников."""
    await callback.answer()

    text = (
        "📚 <b>Справочники</b>\n\n"
        "Выберите справочник для управления:"
    )

    await callback.message.edit_text(text, reply_markup=get_references_menu_keyboard())
    await state.set_state(CategoryStates.main_menu)


# ============================================================================
# СПИСОК КАТЕГОРИЙ
# ============================================================================

@categories_router.callback_query(F.data == "ref_categories")
@categories_router.callback_query(F.data == "cat_list")
async def list_categories(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показать список всех категорий."""
    await callback.answer()

    # Получение всех категорий
    categories = await session.run_sync(
        lambda sync_session: category_service.get_all_categories(sync_session, sort_by_order=True)
    )

    if not categories:
        text = (
            "📦 <b>Категории сырья</b>\n\n"
            "Категорий пока нет. Добавьте первую категорию."
        )
    else:
        text = (
            f"📦 <b>Категории сырья</b> (всего: {len(categories)})\n\n"
            "Выберите категорию для просмотра:"
        )

    await callback.message.edit_text(text, reply_markup=get_categories_keyboard(categories))
    await state.set_state(CategoryStates.list_categories)


# ============================================================================
# ПРОСМОТР КАТЕГОРИИ
# ============================================================================

@categories_router.callback_query(F.data.startswith("cat_view_"))
async def view_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показать детали категории."""
    await callback.answer()

    # Извлечение ID категории
    category_id = int(callback.data.split('_')[2])

    # Получение категории
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    # Получение статистики по категории
    stats = await session.run_sync(
        lambda sync_session: category_service.get_category_stats(sync_session, category_id)
    )

    text = (
        f"📦 <b>{category.name}</b>\n\n"
        f"🔤 <b>Код:</b> {category.code or '—'}\n"
        f"📝 <b>Описание:</b> {category.description or '—'}\n"
        f"🔢 <b>Порядок сортировки:</b> {category.sort_order}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Товаров в категории: {stats['total_skus']}\n"
        f"• Активных товаров: {stats['active_skus']}\n"
    )

    await callback.message.edit_text(text, reply_markup=get_category_view_keyboard(category_id))


# ============================================================================
# СОЗДАНИЕ КАТЕГОРИИ
# ============================================================================

@categories_router.callback_query(F.data == "cat_create")
async def create_category_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Начало создания новой категории."""
    await callback.answer()

    text = (
        "➕ <b>Создание новой категории</b>\n\n"
        "Введите название категории:"
    )

    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(CategoryStates.create_name)


@categories_router.message(CategoryStates.create_name)
async def create_category_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение названия новой категории."""
    name = message.text.strip()

    if not name or len(name) < 2:
        await message.answer(
            "❌ Название должно содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Сохранение названия
    await state.update_data(name=name)

    text = (
        "➕ <b>Создание новой категории</b>\n\n"
        f"📝 Название: <b>{name}</b>\n\n"
        "Введите код категории (латинскими буквами, без пробелов):"
    )

    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(CategoryStates.create_code)


@categories_router.message(CategoryStates.create_code)
async def create_category_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение кода новой категории."""
    code = message.text.strip().lower()

    # Валидация кода
    if not code or len(code) < 2:
        await message.answer(
            "❌ Код должен содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if not code.isalnum() or not code.isascii():
        await message.answer(
            "❌ Код должен содержать только латинские буквы и цифры без пробелов. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Сохранение кода
    await state.update_data(code=code)

    data = await state.get_data()

    text = (
        "➕ <b>Создание новой категории</b>\n\n"
        f"📝 Название: <b>{data['name']}</b>\n"
        f"🔤 Код: <b>{code}</b>\n\n"
        "Введите описание категории (или отправьте '-' чтобы пропустить):"
    )

    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(CategoryStates.create_description)


@categories_router.message(CategoryStates.create_description)
async def create_category_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение описания и создание категории."""
    description = message.text.strip()

    if description == '-':
        description = None

    # Получение данных из состояния
    data = await state.get_data()
    name = data['name']
    code = data['code']

    try:
        # Создание категории
        category = await session.run_sync(
            lambda sync_session: category_service.create_category(
                sync_session,
                name=name,
                code=code,
                description=description
            )
        )
        await session.commit()

        text = (
            "✅ <b>Категория успешно создана!</b>\n\n"
            f"📦 <b>{category.name}</b>\n"
            f"🔤 Код: {category.code}\n"
            f"📝 Описание: {category.description or '—'}\n"
        )

        # Получение всех категорий для обновленного списка
        categories = await session.run_sync(
            lambda sync_session: category_service.get_all_categories(sync_session, sort_by_order=True)
        )

        await message.answer(text)

        list_text = (
            f"📦 <b>Категории сырья</b> (всего: {len(categories)})\n\n"
            "Выберите категорию для просмотра:"
        )

        await message.answer(list_text, reply_markup=get_categories_keyboard(categories))
        await state.set_state(CategoryStates.list_categories)

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка при создании категории: {str(e)}\n\n"
            "Попробуйте ещё раз с другим кодом:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        await message.answer(
            f"❌ Произошла ошибка при создании категории: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


# ============================================================================
# РЕДАКТИРОВАНИЕ КАТЕГОРИИ
# ============================================================================

@categories_router.callback_query(F.data.startswith("cat_edit_"))
async def edit_category_menu(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Меню редактирования категории."""
    await callback.answer()

    # Извлечение ID категории
    parts = callback.data.split('_')

    if len(parts) == 3:  # cat_edit_{id}
        category_id = int(parts[2])

        # Получение категории
        category = await session.run_sync(
            lambda sync_session: category_service.get_category(sync_session, category_id)
        )

        if not category:
            await callback.answer("❌ Категория не найдена", show_alert=True)
            return

        text = (
            f"✏️ <b>Редактирование категории</b>\n\n"
            f"📦 {category.name}\n\n"
            "Выберите поле для редактирования:"
        )

        await callback.message.edit_text(text, reply_markup=get_category_edit_keyboard(category_id))
        await state.set_state(CategoryStates.edit_select_field)

    elif len(parts) == 4:  # cat_edit_{field}_{id}
        field = parts[2]
        category_id = int(parts[3])

        # Сохранение ID категории
        await state.update_data(category_id=category_id)

        # Получение категории
        category = await session.run_sync(
            lambda sync_session: category_service.get_category(sync_session, category_id)
        )

        if not category:
            await callback.answer("❌ Категория не найдена", show_alert=True)
            return

        if field == 'name':
            text = (
                f"✏️ <b>Редактирование названия</b>\n\n"
                f"Текущее значение: <b>{category.name}</b>\n\n"
                "Введите новое название:"
            )
            await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
            await state.set_state(CategoryStates.edit_name)

        elif field == 'code':
            text = (
                f"✏️ <b>Редактирование кода</b>\n\n"
                f"Текущее значение: <b>{category.code or '—'}</b>\n\n"
                "Введите новый код (латинскими буквами, без пробелов):"
            )
            await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
            await state.set_state(CategoryStates.edit_code)

        elif field == 'desc':
            text = (
                f"✏️ <b>Редактирование описания</b>\n\n"
                f"Текущее значение: <b>{category.description or '—'}</b>\n\n"
                "Введите новое описание (или отправьте '-' чтобы удалить):"
            )
            await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
            await state.set_state(CategoryStates.edit_description)

        elif field == 'sort':
            text = (
                f"✏️ <b>Редактирование порядка сортировки</b>\n\n"
                f"Текущее значение: <b>{category.sort_order}</b>\n\n"
                "Введите новое значение (целое число):"
            )
            await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
            await state.set_state(CategoryStates.edit_sort_order)


@categories_router.message(CategoryStates.edit_name)
async def edit_category_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Обновление названия категории."""
    name = message.text.strip()

    if not name or len(name) < 2:
        await message.answer(
            "❌ Название должно содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    data = await state.get_data()
    category_id = data['category_id']

    try:
        # Обновление категории
        category = await session.run_sync(
            lambda sync_session: category_service.update_category(
                sync_session,
                category_id,
                name=name
            )
        )
        await session.commit()

        text = (
            f"✅ Название обновлено!\n\n"
            f"📦 <b>{category.name}</b>\n"
            f"🔤 Код: {category.code or '—'}\n"
            f"📝 Описание: {category.description or '—'}\n"
            f"🔢 Порядок сортировки: {category.sort_order}\n"
        )

        await message.answer(text, reply_markup=get_category_view_keyboard(category_id))
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating category name: {e}")
        await message.answer(
            f"❌ Произошла ошибка при обновлении: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


@categories_router.message(CategoryStates.edit_code)
async def edit_category_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Обновление кода категории."""
    code = message.text.strip().lower()

    if not code or len(code) < 2:
        await message.answer(
            "❌ Код должен содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    if not code.isalnum() or not code.isascii():
        await message.answer(
            "❌ Код должен содержать только латинские буквы и цифры без пробелов. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    data = await state.get_data()
    category_id = data['category_id']

    try:
        # Обновление категории
        category = await session.run_sync(
            lambda sync_session: category_service.update_category(
                sync_session,
                category_id,
                code=code
            )
        )
        await session.commit()

        text = (
            f"✅ Код обновлен!\n\n"
            f"📦 <b>{category.name}</b>\n"
            f"🔤 Код: {category.code}\n"
            f"📝 Описание: {category.description or '—'}\n"
            f"🔢 Порядок сортировки: {category.sort_order}\n"
        )

        await message.answer(text, reply_markup=get_category_view_keyboard(category_id))
        await state.clear()

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка при обновлении кода: {str(e)}\n\n"
            "Попробуйте ещё раз с другим кодом:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error(f"Error updating category code: {e}")
        await message.answer(
            f"❌ Произошла ошибка при обновлении: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


@categories_router.message(CategoryStates.edit_description)
async def edit_category_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Обновление описания категории."""
    description = message.text.strip()

    if description == '-':
        description = None

    data = await state.get_data()
    category_id = data['category_id']

    try:
        # Обновление категории
        category = await session.run_sync(
            lambda sync_session: category_service.update_category(
                sync_session,
                category_id,
                description=description
            )
        )
        await session.commit()

        text = (
            f"✅ Описание обновлено!\n\n"
            f"📦 <b>{category.name}</b>\n"
            f"🔤 Код: {category.code or '—'}\n"
            f"📝 Описание: {category.description or '—'}\n"
            f"🔢 Порядок сортировки: {category.sort_order}\n"
        )

        await message.answer(text, reply_markup=get_category_view_keyboard(category_id))
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating category description: {e}")
        await message.answer(
            f"❌ Произошла ошибка при обновлении: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


@categories_router.message(CategoryStates.edit_sort_order)
async def edit_category_sort_order(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Обновление порядка сортировки категории."""
    try:
        sort_order = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Порядок сортировки должен быть целым числом. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    data = await state.get_data()
    category_id = data['category_id']

    try:
        # Обновление категории
        category = await session.run_sync(
            lambda sync_session: category_service.update_category(
                sync_session,
                category_id,
                sort_order=sort_order
            )
        )
        await session.commit()

        text = (
            f"✅ Порядок сортировки обновлен!\n\n"
            f"📦 <b>{category.name}</b>\n"
            f"🔤 Код: {category.code or '—'}\n"
            f"📝 Описание: {category.description or '—'}\n"
            f"🔢 Порядок сортировки: {category.sort_order}\n"
        )

        await message.answer(text, reply_markup=get_category_view_keyboard(category_id))
        await state.clear()

    except Exception as e:
        logger.error(f"Error updating category sort order: {e}")
        await message.answer(
            f"❌ Произошла ошибка при обновлении: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


# ============================================================================
# УДАЛЕНИЕ КАТЕГОРИИ
# ============================================================================

@categories_router.callback_query(F.data.startswith("cat_delete_"))
async def delete_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Удаление категории."""
    await callback.answer()

    # Извлечение ID категории
    parts = callback.data.split('_')

    if len(parts) == 3:  # cat_delete_{id} - запрос подтверждения
        category_id = int(parts[2])

        # Получение категории
        category = await session.run_sync(
            lambda sync_session: category_service.get_category(sync_session, category_id)
        )

        if not category:
            await callback.answer("❌ Категория не найдена", show_alert=True)
            return

        # Проверка, есть ли товары в категории
        stats = await session.run_sync(
            lambda sync_session: category_service.get_category_stats(sync_session, category_id)
        )

        if stats['total_skus'] > 0:
            await callback.answer(
                f"❌ Невозможно удалить категорию. В ней есть {stats['total_skus']} товар(ов).",
                show_alert=True
            )
            return

        text = (
            f"🗑 <b>Удаление категории</b>\n\n"
            f"📦 {category.name}\n"
            f"🔤 Код: {category.code or '—'}\n\n"
            "⚠️ Вы уверены, что хотите удалить эту категорию?"
        )

        await callback.message.edit_text(text, reply_markup=get_confirm_delete_keyboard(category_id))
        await state.set_state(CategoryStates.confirm_delete)

    elif len(parts) == 4 and parts[2] == 'confirm':  # cat_delete_confirm_{id}
        category_id = int(parts[3])

        try:
            # Удаление категории
            success = await session.run_sync(
                lambda sync_session: category_service.delete_category(sync_session, category_id)
            )
            await session.commit()

            if success:
                # Получение всех категорий для обновленного списка
                categories = await session.run_sync(
                    lambda sync_session: category_service.get_all_categories(sync_session, sort_by_order=True)
                )

                text = (
                    f"📦 <b>Категории сырья</b> (всего: {len(categories)})\n\n"
                    "✅ Категория успешно удалена.\n\n"
                    "Выберите категорию для просмотра:"
                )

                await callback.message.edit_text(text, reply_markup=get_categories_keyboard(categories))
                await state.set_state(CategoryStates.list_categories)
            else:
                await callback.answer("❌ Не удалось удалить категорию", show_alert=True)

        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            await callback.answer(f"❌ Произошла ошибка: {str(e)}", show_alert=True)


# ============================================================================
# ОТМЕНА ОПЕРАЦИИ
# ============================================================================

@categories_router.callback_query(F.data == "cat_cancel")
async def cancel_operation(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Отмена текущей операции."""
    await callback.answer("Операция отменена")

    # Получение всех категорий
    categories = await session.run_sync(
        lambda sync_session: category_service.get_all_categories(sync_session, sort_by_order=True)
    )

    text = (
        f"📦 <b>Категории сырья</b> (всего: {len(categories)})\n\n"
        "Выберите категорию для просмотра:"
    )

    await callback.message.edit_text(text, reply_markup=get_categories_keyboard(categories))
    await state.set_state(CategoryStates.list_categories)


# ============================================================================
# ТОВАРЫ В КАТЕГОРИИ
# ============================================================================

@categories_router.callback_query(F.data.startswith("cat_skus_"))
async def view_category_skus(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Показать товары в категории."""
    await callback.answer()

    # Извлечение ID категории
    category_id = int(callback.data.split('_')[2])

    # Получение категории
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    # Получение товаров в категории
    stmt = select(SKU).where(SKU.category_id == category_id).order_by(SKU.name)
    result = await session.execute(stmt)
    skus = result.scalars().all()

    if not skus:
        text = (
            f"📦 <b>{category.name}</b>\n\n"
            "Товаров в этой категории пока нет.\n\n"
            "Используйте кнопку '➕ Добавить товар' для добавления товара в категорию."
        )
    else:
        sku_list = "\n".join([
            f"• {sku.name} ({sku.code}) - {sku.type.value}"
            for sku in skus
        ])

        text = (
            f"📦 <b>{category.name}</b>\n\n"
            f"Всего товаров: {len(skus)}\n\n"
            f"{sku_list}"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f'cat_view_{category_id}'))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@categories_router.callback_query(F.data.startswith("cat_add_sku_"))
async def add_sku_to_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Добавить товар в категорию."""
    await callback.answer()

    # Извлечение ID категории
    category_id = int(callback.data.split('_')[3])

    # Получение категории
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return

    # Получение всех товаров без категории или сырья
    stmt = select(SKU).where(
        (SKU.category_id.is_(None)) | (SKU.category_id == category_id)
    ).where(SKU.type == 'raw').order_by(SKU.name)
    result = await session.execute(stmt)
    skus = result.scalars().all()

    if not skus:
        text = (
            f"📦 <b>{category.name}</b>\n\n"
            "Нет доступных товаров для добавления в категорию.\n\n"
            "Сначала создайте товары типа 'сырье' через раздел 'Приход сырья'."
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f'cat_view_{category_id}'))
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        return

    text = (
        f"📦 <b>{category.name}</b>\n\n"
        "Выберите товар для добавления в категорию:"
    )

    builder = InlineKeyboardBuilder()
    for sku in skus:
        status = "✅" if sku.category_id == category_id else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {sku.name} ({sku.code})",
                callback_data=f'cat_assign_{category_id}_{sku.id}'
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f'cat_view_{category_id}'))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@categories_router.callback_query(F.data.startswith("cat_assign_"))
async def assign_sku_to_category(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Назначить товар категории."""
    await callback.answer()

    # Извлечение ID категории и SKU
    parts = callback.data.split('_')
    category_id = int(parts[2])
    sku_id = int(parts[3])

    # Получение SKU
    stmt = select(SKU).where(SKU.id == sku_id)
    result = await session.execute(stmt)
    sku = result.scalar_one_or_none()

    if not sku:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    # Назначение категории
    sku.category_id = category_id
    await session.commit()

    await callback.answer(f"✅ Товар '{sku.name}' добавлен в категорию", show_alert=True)

    # Вернуться к списку товаров
    # Получение категории
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    # Получение всех товаров без категории или сырья
    stmt = select(SKU).where(
        (SKU.category_id.is_(None)) | (SKU.category_id == category_id)
    ).where(SKU.type == 'raw').order_by(SKU.name)
    result = await session.execute(stmt)
    skus = result.scalars().all()

    text = (
        f"📦 <b>{category.name}</b>\n\n"
        "Выберите товар для добавления в категорию:"
    )

    builder = InlineKeyboardBuilder()
    for s in skus:
        status = "✅" if s.category_id == category_id else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {s.name} ({s.code})",
                callback_data=f'cat_assign_{category_id}_{s.id}'
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f'cat_view_{category_id}'))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ============================================================================
# ВОЗВРАТ В ГЛАВНОЕ МЕНЮ
# ============================================================================

@categories_router.callback_query(F.data == "ref_back")
async def references_back(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Возврат в главное меню бота."""
    await callback.answer()

    # Получение пользователя
    stmt = select(User).where(User.telegram_id == callback.from_user.id)
    db_user = await session.scalar(stmt)

    await callback.message.delete()
    await callback.message.answer(
        "👋 Главное меню",
        reply_markup=get_main_menu_keyboard(db_user.is_admin if db_user else False)
    )

    await state.clear()
