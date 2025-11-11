"""
Сервис для работы с категориями сырья.

Категории - это управляемый справочник, который может редактировать администратор.
Заменяет жестко закодированный ENUM CategoryType.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Category
from app.logger import get_logger

logger = get_logger("category_service")


def create_category(
    db: Session,
    name: str,
    code: str = None,
    description: str = None,
    sort_order: int = 0
) -> Category:
    """
    Создать новую категорию сырья.

    Args:
        db: Сессия БД
        name: Название категории (например "Загустители")
        code: Код для программного использования (опционально)
        description: Описание категории
        sort_order: Порядок сортировки

    Returns:
        Category: Созданная категория

    Raises:
        ValueError: Если категория с таким именем уже существует
    """
    # Проверка на дубликат имени
    existing = db.execute(
        select(Category).where(Category.name == name)
    ).scalar_one_or_none()

    if existing:
        raise ValueError(f"Категория '{name}' уже существует")

    # Проверка на дубликат кода (если указан)
    if code:
        existing_code = db.execute(
            select(Category).where(Category.code == code)
        ).scalar_one_or_none()

        if existing_code:
            raise ValueError(f"Категория с кодом '{code}' уже существует")

    category = Category(
        name=name,
        code=code,
        description=description,
        sort_order=sort_order
    )
    db.add(category)
    db.flush()
    db.refresh(category)

    logger.info(f"Created category: {name} (ID: {category.id})")
    return category


def get_category(db: Session, category_id: int) -> Optional[Category]:
    """Получить категорию по ID."""
    return db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()


def get_category_by_name(db: Session, name: str) -> Optional[Category]:
    """Получить категорию по имени."""
    return db.execute(
        select(Category).where(Category.name == name)
    ).scalar_one_or_none()


def get_category_by_code(db: Session, code: str) -> Optional[Category]:
    """Получить категорию по коду."""
    return db.execute(
        select(Category).where(Category.code == code)
    ).scalar_one_or_none()


def get_all_categories(db: Session, sort_by_order: bool = True) -> List[Category]:
    """
    Получить все категории.

    Args:
        db: Сессия БД
        sort_by_order: Сортировать по sort_order (по умолчанию True)

    Returns:
        List[Category]: Список категорий
    """
    query = select(Category)

    if sort_by_order:
        query = query.order_by(Category.sort_order, Category.name)
    else:
        query = query.order_by(Category.name)

    return list(db.execute(query).scalars().all())


def update_category(
    db: Session,
    category_id: int,
    name: str = None,
    code: str = None,
    description: str = None,
    sort_order: int = None
) -> Optional[Category]:
    """
    Обновить категорию.

    Args:
        db: Сессия БД
        category_id: ID категории
        name: Новое название (опционально)
        code: Новый код (опционально)
        description: Новое описание (опционально)
        sort_order: Новый порядок сортировки (опционально)

    Returns:
        Optional[Category]: Обновленная категория или None

    Raises:
        ValueError: Если новое имя/код уже используется другой категорией
    """
    category = get_category(db, category_id)
    if not category:
        return None

    # Проверка на дубликат имени
    if name and name != category.name:
        existing = db.execute(
            select(Category).where(Category.name == name, Category.id != category_id)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Категория '{name}' уже существует")

        category.name = name

    # Проверка на дубликат кода
    if code and code != category.code:
        existing_code = db.execute(
            select(Category).where(Category.code == code, Category.id != category_id)
        ).scalar_one_or_none()

        if existing_code:
            raise ValueError(f"Категория с кодом '{code}' уже существует")

        category.code = code

    if description is not None:
        category.description = description

    if sort_order is not None:
        category.sort_order = sort_order

    db.flush()
    db.refresh(category)

    logger.info(f"Updated category {category_id}: {category.name}")
    return category


def delete_category(db: Session, category_id: int) -> bool:
    """
    Удалить категорию.

    ВАЖНО: Удаление возможно только если нет связанных SKU!

    Args:
        db: Сессия БД
        category_id: ID категории

    Returns:
        bool: True если удалена, False если не найдена

    Raises:
        ValueError: Если есть связанные SKU
    """
    category = get_category(db, category_id)
    if not category:
        return False

    # Проверка на наличие связанных SKU
    from app.database.models import SKU
    skus_count = db.execute(
        select(SKU).where(SKU.category_id == category_id)
    ).scalars().all()

    if len(skus_count) > 0:
        raise ValueError(
            f"Невозможно удалить категорию '{category.name}': "
            f"к ней привязано {len(skus_count)} материалов. "
            f"Сначала удалите или переместите материалы."
        )

    db.delete(category)
    db.flush()

    logger.info(f"Deleted category {category_id}: {category.name}")
    return True


def search_categories(db: Session, search_term: str) -> List[Category]:
    """
    Поиск категорий по названию или коду.

    Args:
        db: Сессия БД
        search_term: Строка поиска

    Returns:
        List[Category]: Список найденных категорий
    """
    query = select(Category).where(
        (Category.name.ilike(f"%{search_term}%")) |
        (Category.code.ilike(f"%{search_term}%") if search_term else False)
    ).order_by(Category.sort_order, Category.name)

    return list(db.execute(query).scalars().all())


def reorder_categories(db: Session, category_orders: dict) -> None:
    """
    Изменить порядок сортировки категорий.

    Args:
        db: Сессия БД
        category_orders: Словарь {category_id: new_sort_order}

    Example:
        >>> reorder_categories(db, {1: 0, 2: 10, 3: 20})
    """
    for category_id, sort_order in category_orders.items():
        category = get_category(db, category_id)
        if category:
            category.sort_order = sort_order

    db.flush()
    logger.info(f"Reordered {len(category_orders)} categories")


def get_category_stats(db: Session, category_id: int) -> dict:
    """
    Получить статистику по категории.

    Args:
        db: Сессия БД
        category_id: ID категории

    Returns:
        dict: Статистика (количество SKU, и т.д.)
    """
    from app.database.models import SKU

    category = get_category(db, category_id)
    if not category:
        return None

    # Количество материалов в категории
    skus = db.execute(
        select(SKU).where(SKU.category_id == category_id)
    ).scalars().all()

    # Количество активных материалов
    active_skus = [sku for sku in skus if sku.is_active]

    return {
        'category_id': category.id,
        'category_name': category.name,
        'total_skus': len(skus),
        'active_skus': len(active_skus),
        'inactive_skus': len(skus) - len(active_skus)
    }
