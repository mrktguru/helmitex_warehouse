"""
Сервис для работы с полуфабрикатами.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import SemiProduct, Category, CategoryType, UnitType
from app.exceptions import ValidationError
from app.logger import get_logger

logger = get_logger("semi_product_service")


def create_semi_product(
    db: Session,
    category_id: int,
    name: str,
    unit: UnitType,
    created_by: int
) -> SemiProduct:
    """
    Создать новый полуфабрикат.
    
    Args:
        db: Сессия БД
        category_id: ID категории
        name: Название полуфабриката
        unit: Единица измерения
        created_by: Telegram ID создателя
        
    Returns:
        Созданный полуфабрикат
    """
    # Проверяем категорию
    category = db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()
    
    if not category:
        raise ValidationError(f"Категория с ID {category_id} не найдена")
    
    if category.type != CategoryType.semi_product:
        raise ValidationError(f"Категория '{category.name}' не является категорией полуфабрикатов")
    
    # Проверка на дубликаты
    existing = db.execute(
        select(SemiProduct).where(
            SemiProduct.category_id == category_id,
            SemiProduct.name == name
        )
    ).scalar_one_or_none()
    
    if existing:
        raise ValidationError(f"Полуфабрикат '{name}' в категории '{category.name}' уже существует")
    
    semi_product = SemiProduct(
        category_id=category_id,
        name=name,
        unit=unit,
        stock_quantity=0.0,
        created_by=created_by
    )
    
    db.add(semi_product)
    db.commit()
    db.refresh(semi_product)
    
    logger.info(f"Создан полуфабрикат: {category.name} / {name} (ID: {semi_product.id})")
    return semi_product


def get_semi_products(
    db: Session,
    category_id: Optional[int] = None
) -> List[SemiProduct]:
    """
    Получить список полуфабрикатов.
    
    Args:
        db: Сессия БД
        category_id: Фильтр по категории (опционально)
        
    Returns:
        Список полуфабрикатов
    """
    query = select(SemiProduct).order_by(SemiProduct.name)
    
    if category_id:
        query = query.where(SemiProduct.category_id == category_id)
    
    products = db.execute(query).scalars().all()
    return list(products)


def get_semi_product_by_id(db: Session, product_id: int) -> SemiProduct:
    """
    Получить полуфабрикат по ID.
    
    Args:
        db: Сессия БД
        product_id: ID полуфабриката
        
    Returns:
        Полуфабрикат
        
    Raises:
        ValidationError: Если не найден
    """
    product = db.execute(
        select(SemiProduct).where(SemiProduct.id == product_id)
    ).scalar_one_or_none()
    
    if not product:
        raise ValidationError(f"Полуфабрикат с ID {product_id} не найден")
    
    return product


def update_stock(
    db: Session,
    product_id: int,
    quantity_change: float
) -> SemiProduct:
    """
    Обновить остаток полуфабриката.
    
    Args:
        db: Сессия БД
        product_id: ID полуфабриката
        quantity_change: Изменение количества (+ приход, - расход)
        
    Returns:
        Обновленный полуфабрикат
        
    Raises:
        ValidationError: Если недостаточно остатка
    """
    product = get_semi_product_by_id(db, product_id)
    
    new_quantity = product.stock_quantity + quantity_change
    
    if new_quantity < 0:
        raise ValidationError(
            f"Недостаточно полуфабриката '{product.name}'. "
            f"Доступно: {product.stock_quantity} {product.unit.value}, "
            f"требуется: {abs(quantity_change)} {product.unit.value}"
        )
    
    product.stock_quantity = new_quantity
    db.commit()
    db.refresh(product)
    
    logger.info(
        f"Обновлен остаток полуфабриката ID {product_id}: "
        f"{quantity_change:+.2f} {product.unit.value}, "
        f"новый остаток: {product.stock_quantity:.2f}"
    )
    
    return product
