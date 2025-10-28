"""
Сервис для работы с движениями товаров.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from datetime import datetime

from app.database.models import Movement, MovementType
from app.services.stock_service import update_stock
from app.logger import get_logger

logger = get_logger("movement_service")


def create_movement(
    db: Session,
    warehouse_id: int,
    sku_id: int,
    movement_type: MovementType,
    quantity: float,
    user_id: int,
    from_warehouse_id: int = None,
    to_warehouse_id: int = None,
    notes: str = None
) -> Movement:
    """
    Создать движение товара и обновить остатки.
    """
    # Валидация
    if quantity <= 0:
        raise ValueError("Количество должно быть положительным")
    
    if movement_type == MovementType.transfer:
        if not from_warehouse_id or not to_warehouse_id:
            raise ValueError("Для перемещения нужно указать склады отправления и назначения")
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("Склады отправления и назначения должны различаться")
    
    # Создаем движение
    movement = Movement(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        type=movement_type,
        quantity=quantity,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        user_id=user_id,
        notes=notes
    )
    db.add(movement)
    
    # Обновляем остатки в зависимости от типа движения
    try:
        if movement_type == MovementType.in_:
            # Приход - увеличиваем остаток
            update_stock(db, warehouse_id, sku_id, quantity)
        
        elif movement_type == MovementType.out:
            # Расход - уменьшаем остаток
            update_stock(db, warehouse_id, sku_id, -quantity)
        
        elif movement_type == MovementType.transfer:
            # Перемещение - уменьшаем на складе отправления, увеличиваем на складе назначения
            update_stock(db, from_warehouse_id, sku_id, -quantity)
            update_stock(db, to_warehouse_id, sku_id, quantity)
        
        elif movement_type == MovementType.adjustment:
            # Корректировка - изменяем остаток (может быть + или -)
            # Для корректировки quantity может быть отрицательным
            update_stock(db, warehouse_id, sku_id, quantity)
        
        db.commit()
        db.refresh(movement)
        logger.info(f"Created movement: type={movement_type}, warehouse={warehouse_id}, sku={sku_id}, qty={quantity}")
        return movement
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create movement: {e}")
        raise


def get_movement(db: Session, movement_id: int) -> Optional[Movement]:
    """Получить движение по ID."""
    return db.execute(
        select(Movement).where(Movement.id == movement_id)
    ).scalar_one_or_none()


def get_warehouse_movements(
    db: Session,
    warehouse_id: int,
    limit: int = 100
) -> List[Movement]:
    """Получить последние движения по складу."""
    return db.execute(
        select(Movement)
        .where(Movement.warehouse_id == warehouse_id)
        .order_by(desc(Movement.created_at))
        .limit(limit)
    ).scalars().all()


def get_sku_movements(
    db: Session,
    sku_id: int,
    limit: int = 100
) -> List[Movement]:
    """Получить последние движения по товару."""
    return db.execute(
        select(Movement)
        .where(Movement.sku_id == sku_id)
        .order_by(desc(Movement.created_at))
        .limit(limit)
    ).scalars().all()


def get_user_movements(
    db: Session,
    user_id: int,
    limit: int = 100
) -> List[Movement]:
    """Получить последние движения пользователя."""
    return db.execute(
        select(Movement)
        .where(Movement.user_id == user_id)
        .order_by(desc(Movement.created_at))
        .limit(limit)
    ).scalars().all()
