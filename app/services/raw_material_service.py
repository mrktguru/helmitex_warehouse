"""
Сервис для работы с сырьем.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import RawMaterial, Category, CategoryType, UnitType
from app.exceptions import ValidationError, SKUNotFoundError
from app.logger import get_logger

logger = get_logger("raw_material_service")


def create_raw_material(
    db: Session,
    category_id: int,
    name: str,
    unit: UnitType,
    created_by: int,
    min_stock: Optional[float] = None
) -> RawMaterial:
    """
    Создать новое сырье.
    
    Args:
        db: Сессия БД
        category_id: ID категории
        name: Название сырья
        unit: Единица измерения
        created_by: Telegram ID создателя
        min_stock: Минимальный остаток (опционально)
        
    Returns:
        Созданное сырье
    """
    # Проверяем что категория существует и имеет правильный тип
    category = db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()
    
    if not category:
        raise ValidationError(f"Категория с ID {category_id} не найдена")
    
    if category.type != CategoryType.raw_material:
        raise ValidationError(f"Категория '{category.name}' не является категорией сырья")
    
    # Проверка на дубликаты
    existing = db.execute(
        select(RawMaterial).where(
            RawMaterial.category_id == category_id,
            RawMaterial.name == name
        )
    ).scalar_one_or_none()
    
    if existing:
        raise ValidationError(f"Сырье '{name}' в категории '{category.name}' уже существует")
    
    raw_material = RawMaterial(
        category_id=category_id,
        name=name,
        unit=unit,
        stock_quantity=0.0,
        min_stock=min_stock,
        created_by=created_by
    )
    
    db.add(raw_material)
    db.commit()
    db.refresh(raw_material)
    
    logger.info(f"Создано сырье: {category.name} / {name} (ID: {raw_material.id})")
    return raw_material


def get_raw_materials(
    db: Session,
    category_id: Optional[int] = None
) -> List[RawMaterial]:
    """
    Получить список сырья.
    
    Args:
        db: Сессия БД
        category_id: Фильтр по категории (опционально)
        
    Returns:
        Список сырья
    """
    query = select(RawMaterial).order_by(RawMaterial.name)
    
    if category_id:
        query = query.where(RawMaterial.category_id == category_id)
    
    materials = db.execute(query).scalars().all()
    return list(materials)


def get_raw_material_by_id(db: Session, material_id: int) -> RawMaterial:
    """
    Получить сырье по ID.
    
    Args:
        db: Сессия БД
        material_id: ID сырья
        
    Returns:
        Сырье
        
    Raises:
        SKUNotFoundError: Если сырье не найдено
    """
    material = db.execute(
        select(RawMaterial).where(RawMaterial.id == material_id)
    ).scalar_one_or_none()
    
    if not material:
        raise SKUNotFoundError(str(material_id))
    
    return material


def update_stock(
    db: Session,
    material_id: int,
    quantity_change: float
) -> RawMaterial:
    """
    Обновить остаток сырья.
    
    Args:
        db: Сессия БД
        material_id: ID сырья
        quantity_change: Изменение количества (+ приход, - расход)
        
    Returns:
        Обновленное сырье
        
    Raises:
        ValidationError: Если недостаточно остатка
    """
    material = get_raw_material_by_id(db, material_id)
    
    new_quantity = material.stock_quantity + quantity_change
    
    if new_quantity < 0:
        raise ValidationError(
            f"Недостаточно сырья '{material.name}'. "
            f"Доступно: {material.stock_quantity} {material.unit.value}, "
            f"требуется: {abs(quantity_change)} {material.unit.value}"
        )
    
    material.stock_quantity = new_quantity
    db.commit()
    db.refresh(material)
    
    logger.info(
        f"Обновлен остаток сырья ID {material_id}: "
        f"{quantity_change:+.2f} {material.unit.value}, "
        f"новый остаток: {material.stock_quantity:.2f}"
    )
    
    return material


def get_low_stock_materials(db: Session) -> List[RawMaterial]:
    """
    Получить список сырья с низким остатком.
    
    Args:
        db: Сессия БД
        
    Returns:
        Список сырья с остатком ниже минимального
    """
    materials = db.execute(
        select(RawMaterial).where(
            RawMaterial.min_stock.isnot(None),
            RawMaterial.stock_quantity <= RawMaterial.min_stock
        )
    ).scalars().all()
    
    return list(materials)
