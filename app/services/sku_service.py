"""
Сервис для работы с товарами (SKU).

ОБНОВЛЕНО: Поддержка новой модели Category (вместо ENUM CategoryType).
"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.database.models import SKU, SKUType, CategoryType, UnitType, Category
from app.logger import get_logger

logger = get_logger("sku_service")


def create_sku(
    db: Session,
    code: str,
    name: str,
    sku_type: SKUType,
    category_id: int = None,
    unit: UnitType = UnitType.pieces,
    min_stock: float = 0,
    description: str = None,
    notes: str = None,
    is_active: bool = True,
    # Deprecated параметры (для обратной совместимости)
    category: CategoryType = None
) -> SKU:
    """
    Создать новый SKU.

    Args:
        db: Сессия БД
        code: Уникальный код SKU
        name: Название
        sku_type: Тип (raw/semi/finished)
        category_id: ID категории (для сырья) - НОВОЕ!
        unit: Единица измерения
        min_stock: Минимальный остаток
        description: Описание - НОВОЕ!
        notes: Примечания - НОВОЕ!
        is_active: Активен ли материал - НОВОЕ!
        category: DEPRECATED - используйте category_id

    Returns:
        SKU: Созданный SKU

    Raises:
        ValueError: Если код уже существует
    """
    # Проверка на дубликат кода
    existing = db.execute(
        select(SKU).where(SKU.code == code)
    ).scalar_one_or_none()

    if existing:
        raise ValueError(f"SKU с кодом {code} уже существует")

    # Проверка категории для сырья
    if sku_type == SKUType.raw and category_id:
        category_obj = db.get(Category, category_id)
        if not category_obj:
            raise ValueError(f"Категория с ID={category_id} не найдена")

    sku = SKU(
        code=code,
        name=name,
        type=sku_type,
        category_id=category_id,
        category=category,  # Для обратной совместимости
        unit=unit,
        min_stock=min_stock,
        description=description,
        notes=notes,
        is_active=is_active
    )
    db.add(sku)
    db.flush()
    db.refresh(sku)
    logger.info(f"Created SKU: {code} - {name} (ID: {sku.id}, active: {is_active})")
    return sku


def get_sku(db: Session, sku_id: int, load_category: bool = False) -> Optional[SKU]:
    """
    Получить SKU по ID.

    Args:
        db: Сессия БД
        sku_id: ID SKU
        load_category: Загрузить связанную категорию

    Returns:
        Optional[SKU]: SKU или None
    """
    query = select(SKU).where(SKU.id == sku_id)

    if load_category:
        query = query.options(joinedload(SKU.category_rel))

    return db.execute(query).scalar_one_or_none()


def get_sku_by_code(db: Session, code: str, load_category: bool = False) -> Optional[SKU]:
    """
    Получить SKU по коду.

    Args:
        db: Сессия БД
        code: Код SKU
        load_category: Загрузить связанную категорию

    Returns:
        Optional[SKU]: SKU или None
    """
    query = select(SKU).where(SKU.code == code)

    if load_category:
        query = query.options(joinedload(SKU.category_rel))

    return db.execute(query).scalar_one_or_none()


def get_all_skus(
    db: Session,
    sku_type: SKUType = None,
    active_only: bool = False,
    load_category: bool = False
) -> List[SKU]:
    """
    Получить все SKU с фильтрацией.

    Args:
        db: Сессия БД
        sku_type: Фильтр по типу (опционально)
        active_only: Только активные SKU
        load_category: Загрузить категории

    Returns:
        List[SKU]: Список SKU
    """
    query = select(SKU)

    if sku_type:
        query = query.where(SKU.type == sku_type)

    if active_only:
        query = query.where(SKU.is_active == True)

    if load_category:
        query = query.options(joinedload(SKU.category_rel))

    query = query.order_by(SKU.name)

    return list(db.execute(query).scalars().unique().all())


def get_skus_by_category_id(
    db: Session,
    category_id: int,
    active_only: bool = True
) -> List[SKU]:
    """
    Получить все SKU по ID категории (НОВОЕ!).

    Args:
        db: Сессия БД
        category_id: ID категории
        active_only: Только активные SKU

    Returns:
        List[SKU]: Список SKU
    """
    query = select(SKU).where(SKU.category_id == category_id)

    if active_only:
        query = query.where(SKU.is_active == True)

    query = query.order_by(SKU.name)

    return list(db.execute(query).scalars().all())


def get_skus_by_category(db: Session, category: CategoryType) -> List[SKU]:
    """
    DEPRECATED: Получить все SKU по старой категории (ENUM).
    Используйте get_skus_by_category_id() вместо этого.
    """
    return list(db.execute(
        select(SKU).where(SKU.category == category).order_by(SKU.name)
    ).scalars().all())


def get_raw_materials(db: Session, category: CategoryType = None) -> List[SKU]:
    """Получить все сырье, опционально фильтруя по категории."""
    query = select(SKU).where(SKU.type == SKUType.raw)
    if category:
        query = query.where(SKU.category == category)
    return db.execute(query.order_by(SKU.name)).scalars().all()


def update_sku(
    db: Session,
    sku_id: int,
    name: str = None,
    category_id: int = None,
    unit: UnitType = None,
    min_stock: float = None,
    description: str = None,
    notes: str = None,
    is_active: bool = None,
    # Deprecated
    category: CategoryType = None
) -> Optional[SKU]:
    """
    Обновить данные SKU.

    Args:
        db: Сессия БД
        sku_id: ID SKU
        name: Новое название
        category_id: Новая категория (ID) - НОВОЕ!
        unit: Новая единица измерения
        min_stock: Новый минимальный остаток
        description: Новое описание - НОВОЕ!
        notes: Новые примечания - НОВОЕ!
        is_active: Новый статус активности - НОВОЕ!
        category: DEPRECATED

    Returns:
        Optional[SKU]: Обновленный SKU или None
    """
    sku = get_sku(db, sku_id)
    if not sku:
        return None

    if name:
        sku.name = name

    if category_id is not None:
        # Проверка существования категории
        category_obj = db.get(Category, category_id)
        if not category_obj:
            raise ValueError(f"Категория с ID={category_id} не найдена")
        sku.category_id = category_id

    if category:
        sku.category = category

    if unit:
        sku.unit = unit

    if min_stock is not None:
        sku.min_stock = min_stock

    if description is not None:
        sku.description = description

    if notes is not None:
        sku.notes = notes

    if is_active is not None:
        sku.is_active = is_active

    db.flush()
    db.refresh(sku)
    logger.info(f"Updated SKU {sku_id}: {sku.name}")
    return sku


def deactivate_sku(db: Session, sku_id: int) -> Optional[SKU]:
    """
    Деактивировать SKU (убрать из списков, но сохранить в истории).

    Args:
        db: Сессия БД
        sku_id: ID SKU

    Returns:
        Optional[SKU]: Деактивированный SKU или None
    """
    return update_sku(db, sku_id, is_active=False)


def activate_sku(db: Session, sku_id: int) -> Optional[SKU]:
    """
    Активировать SKU.

    Args:
        db: Сессия БД
        sku_id: ID SKU

    Returns:
        Optional[SKU]: Активированный SKU или None
    """
    return update_sku(db, sku_id, is_active=True)


def search_skus(db: Session, search_term: str, sku_type: SKUType = None) -> List[SKU]:
    """Поиск SKU по названию или коду."""
    query = select(SKU).where(
        (SKU.name.ilike(f"%{search_term}%")) | 
        (SKU.code.ilike(f"%{search_term}%"))
    )
    if sku_type:
        query = query.where(SKU.type == sku_type)
    return db.execute(query.order_by(SKU.name)).scalars().all()
