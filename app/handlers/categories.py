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
    edit_select_field = State()
    edit_name = State()
    edit_sort_order = State()
    confirm_delete = State()
    # Состояния для создания товара в категории
    sku_create_name = State()
    sku_create_unit = State()
    sku_create_min_stock = State()


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
        [InlineKeyboardButton(text="➕ Создать товар", callback_data=f'cat_add_sku_{category_id}')],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f'cat_edit_{category_id}')],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f'cat_delete_{category_id}')],
        [InlineKeyboardButton(text="🔙 К списку", callback_data='cat_list')],
    ])


def get_category_edit_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора поля редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f'cat_edit_name_{category_id}')],
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
    """Получение названия и создание категории."""
    name = message.text.strip()

    if not name or len(name) < 2:
        await message.answer(
            "❌ Название должно содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Автоматическая генерация кода из названия
    import re
    import transliterate

    # Транслитерация названия (если есть кириллица)
    try:
        code = transliterate.translit(name, 'ru', reversed=True).lower()
    except:
        code = name.lower()

    # Убираем все кроме букв и цифр
    code = re.sub(r'[^a-z0-9]', '_', code)
    # Убираем повторяющиеся подчеркивания
    code = re.sub(r'_+', '_', code)
    # Убираем подчеркивания в начале и конце
    code = code.strip('_')

    # Если код пустой, генерируем на основе счетчика
    if not code:
        import time
        code = f"cat_{int(time.time())}"

    # Проверяем уникальность кода
    from app.database.models import Category
    base_code = code
    counter = 1
    while True:
        stmt = select(Category).where(Category.code == code)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            break
        code = f"{base_code}_{counter}"
        counter += 1

    try:
        # Создание категории
        category = await session.run_sync(
            lambda sync_session: category_service.create_category(
                sync_session,
                name=name,
                code=code,
                description=None
            )
        )
        await session.commit()

        text = (
            "✅ <b>Категория успешно создана!</b>\n\n"
            f"📦 <b>{category.name}</b>"
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
            f"❌ Ошибка при создании категории: {str(e)}",
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
            "Используйте кнопку '➕ Создать товар' для создания нового товара в категории."
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
async def create_sku_in_category_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Начать создание нового товара в категории."""
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

    # Сохраняем ID категории в состоянии
    await state.update_data(category_id=category_id)

    text = (
        f"➕ <b>Создание товара в категории</b>\n\n"
        f"📦 Категория: <b>{category.name}</b>\n\n"
        "Введите название товара:"
    )

    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(CategoryStates.sku_create_name)


@categories_router.message(CategoryStates.sku_create_name)
async def create_sku_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение названия товара."""
    name = message.text.strip()

    if not name or len(name) < 2:
        await message.answer(
            "❌ Название должно содержать минимум 2 символа. Попробуйте ещё раз:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Сохранение названия
    await state.update_data(sku_name=name)

    # Клавиатура выбора единицы измерения
    from app.database.models import UnitType

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="кг (килограммы)", callback_data='sku_unit_kg'))
    builder.row(InlineKeyboardButton(text="л (литры)", callback_data='sku_unit_liters'))
    builder.row(InlineKeyboardButton(text="г (граммы)", callback_data='sku_unit_grams'))
    builder.row(InlineKeyboardButton(text="шт (штуки)", callback_data='sku_unit_pieces'))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data='cat_cancel'))

    data = await state.get_data()
    category_id = data['category_id']
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    text = (
        f"➕ <b>Создание товара</b>\n\n"
        f"📦 Категория: <b>{category.name}</b>\n"
        f"📝 Название: <b>{name}</b>\n\n"
        "Выберите единицу измерения:"
    )

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(CategoryStates.sku_create_unit)


@categories_router.callback_query(F.data.startswith("sku_unit_"))
async def create_sku_unit(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение единицы измерения."""
    await callback.answer()

    # Извлечение единицы измерения
    unit_code = callback.data.split('_')[2]  # kg, liters, grams, pieces

    # Сохранение единицы измерения
    await state.update_data(sku_unit=unit_code)

    data = await state.get_data()
    category_id = data['category_id']
    category = await session.run_sync(
        lambda sync_session: category_service.get_category(sync_session, category_id)
    )

    unit_names = {
        'kg': 'кг',
        'liters': 'л',
        'grams': 'г',
        'pieces': 'шт'
    }

    text = (
        f"➕ <b>Создание товара</b>\n\n"
        f"📦 Категория: <b>{category.name}</b>\n"
        f"📝 Название: <b>{data['sku_name']}</b>\n"
        f"📏 Единица: <b>{unit_names[unit_code]}</b>\n\n"
        "Введите минимальный остаток (число, например 10):"
    )

    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(CategoryStates.sku_create_min_stock)


@categories_router.message(CategoryStates.sku_create_min_stock)
async def create_sku_min_stock(
    message: Message,
    state: FSMContext,
    session: AsyncSession
) -> None:
    """Получение минимального остатка и создание товара."""
    try:
        min_stock = float(message.text.strip())
        if min_stock < 0:
            raise ValueError("Минимальный остаток не может быть отрицательным")
    except ValueError:
        await message.answer(
            "❌ Введите корректное число (например, 10 или 5.5):",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Получение данных из состояния
    data = await state.get_data()
    category_id = data['category_id']
    sku_name = data['sku_name']
    sku_unit = data['sku_unit']

    # Автоматическая генерация кода из названия товара
    import re
    import time

    # Простая транслитерация
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    code = sku_name.lower()
    for cyr, lat in translit_map.items():
        code = code.replace(cyr, lat)

    # Убираем все кроме букв и цифр
    code = re.sub(r'[^a-z0-9]', '_', code)
    # Убираем повторяющиеся подчеркивания
    code = re.sub(r'_+', '_', code)
    # Убираем подчеркивания в начале и конце
    code = code.strip('_')

    # Если код пустой, генерируем на основе счетчика
    if not code:
        code = f"sku_{int(time.time())}"

    # Проверяем уникальность кода
    from app.database.models import SKU as SKUModel
    base_code = code
    counter = 1
    while True:
        stmt = select(SKUModel).where(SKUModel.code == code)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            break
        code = f"{base_code}_{counter}"
        counter += 1

    try:
        # Создание товара
        from app.database.models import SKUType, UnitType

        new_sku = SKUModel(
            code=code,
            name=sku_name,
            type=SKUType.raw,
            category_id=category_id,
            unit=UnitType[sku_unit],
            min_stock=min_stock,
            is_active=True
        )

        session.add(new_sku)
        await session.commit()
        await session.refresh(new_sku)

        unit_names = {
            'kg': 'кг',
            'liters': 'л',
            'grams': 'г',
            'pieces': 'шт'
        }

        text = (
            "✅ <b>Товар успешно создан!</b>\n\n"
            f"📝 <b>{new_sku.name}</b>\n"
            f"📏 Единица: {unit_names[sku_unit]}\n"
            f"📊 Минимальный остаток: {min_stock}\n"
        )

        await message.answer(text)

        # Показать категорию
        category = await session.run_sync(
            lambda sync_session: category_service.get_category(sync_session, category_id)
        )

        stats = await session.run_sync(
            lambda sync_session: category_service.get_category_stats(sync_session, category_id)
        )

        category_text = (
            f"📦 <b>{category.name}</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Товаров в категории: {stats['total_skus']}\n"
            f"• Активных товаров: {stats['active_skus']}\n"
        )

        await message.answer(category_text, reply_markup=get_category_view_keyboard(category_id))
        await state.clear()

    except Exception as e:
        logger.error(f"Error creating SKU: {e}")
        await message.answer(
            f"❌ Произошла ошибка при создании товара: {str(e)}",
            reply_markup=get_cancel_keyboard()
        )


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
