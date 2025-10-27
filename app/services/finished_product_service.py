"""
Сервис для работы с готовой продукцией.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import FinishedProduct, Category, CategoryType, UnitType
from app.exceptions import ValidationError
from app.logger import get_logger

logger = get_logger("finished_product_service")


def create_finished_product(
    db: Session,
    category_id: int,
    name: str,
    package_type: str,
    package_weight: float,
    created_by: int
) -> FinishedProduct:
    """
    Создать новую готовую продукцию.
    
    Args:
        db: Сессия БД
        category_id: ID категории
        name: Название продукции
        package_type: Тип тары (пакет, банка и т.д.)
        package_weight: Вес упаковки
        created_by: Telegram ID создателя
        
    Returns:
        Созданная продукция
    """
    # Проверяем категорию
    category = db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()
    
    if not category:
        raise ValidationError(f"Категория с ID {category_id} не найдена")
    
    if category.type != CategoryType.finished_product:
        raise ValidationError(f"Категория '{category.name}' не является категорией готовой продукции")
    
    # Проверка на дубликаты
    existing = db.execute(
        select(FinishedProduct).where(
            FinishedProduct.category_id == category_id,
            FinishedProduct.name == name,
            FinishedProduct.package_type == package_type,
            FinishedProduct.package_weight == package_weight
        )
    ).scalar_one_or_none()
    
    if existing:
        raise ValidationError(
            f"Продукция '{name}' ({package_type} {package_weight}кг) "
            f"в категории '{category.name}' уже существует"
        )
    
    product = FinishedProduct(
        category_id=category_id,
        name=name,
        package_type=package_type,
        package_weight=package_weight,
        unit=UnitType.piece,
        stock_quantity=0,
        created_by=created_by
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    logger.info(
        f"Создана готовая продукция: {category.name} / {name} "
        f"({package_type} {package_weight}кг, ID: {product.id})"
    )
    return product


def get_finished_products(
    db: Session,
    category_id: Optional[int] = None
) -> List[FinishedProduct]:
    """
    Получить список готовой продукции.
    
    Args:
        db: Сессия БД
        category_id: Фильтр по категории (опционально)
        
    Returns:
        Список продукции
    """
    query = select(FinishedProduct).order_by(FinishedProduct.name)
    
    if category_id:
        query = query.where(FinishedProduct.category_id == category_id)
    
    products = db.execute(query).scalars().all()
    return list(products)


def get_finished_product_by_id(db: Session, product_id: int) -> FinishedProduct:
    """
    Получить готовую продукцию по ID.
    
    Args:
        db: Сессия БД
        product_id: ID продукции
        
    Returns:
        Продукция
        
    Raises:
        ValidationError: Если не найдена
    """
    product = db.execute(
        select(FinishedProduct).where(FinishedProduct.id == product_id)
    ).scalar_one_or_none()
    
    if not product:
        raise ValidationError(f"Готовая продукция с ID {product_id} не найдена")
    
    return product


def update_stock(
    db: Session,
    product_id: int,
    quantity_change: int
) -> FinishedProduct:
    """
    Обновить остаток готовой продукции.
    
    Args:
        db: Сессия БД
        product_id: ID продукции
        quantity_change: Изменение количества упаковок (+ приход, - расход)
        
    Returns:
        Обновленная продукция
        
    Raises:
        ValidationError: Если недостаточно остатка
    """
    product = get_finished_product_by_id(db, product_id)
    
    new_quantity = product.stock_quantity + quantity_change
    
    if new_quantity < 0:
        raise ValidationError(
            f"Недостаточно продукции '{product.name}'. "
            f"Доступно: {int(product.stock_quantity)} шт, "
            f"требуется: {abs(quantity_change)} шт"
        )
    
    product.stock_quantity = new_quantity
    db.commit()
    db.refresh(product)
    
    logger.info(
        f"Обновлен остаток продукции ID {product_id}: "
        f"{quantity_change:+d} шт, "
        f"новый остаток: {int(product.stock_quantity)} шт"
    )
    
    return product
