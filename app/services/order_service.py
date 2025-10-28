"""
Сервис для работы с заказами.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from datetime import datetime

from app.database.models import Order, OrderItem, OrderType, OrderStatus
from app.services.movement_service import create_movement
from app.database.models import MovementType
from app.logger import get_logger

logger = get_logger("order_service")


def generate_order_number() -> str:
    """Генерация номера заказа."""
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"


def create_order(
    db: Session,
    order_type: OrderType,
    warehouse_id: int,
    user_id: int,
    items: List[dict],  # [{'sku_id': int, 'quantity': float, 'price': float}, ...]
    notes: str = None
) -> Order:
    """
    Создать новый заказ с позициями.
    items: список словарей с sku_id, quantity, price (опционально)
    """
    # Создаем заказ
    order = Order(
        order_number=generate_order_number(),
        type=order_type,
        status=OrderStatus.pending,
        warehouse_id=warehouse_id,
        user_id=user_id,
        notes=notes
    )
    db.add(order)
    db.flush()  # Получаем ID заказа
    
    # Добавляем позиции заказа
    for item_data in items:
        order_item = OrderItem(
            order_id=order.id,
            sku_id=item_data['sku_id'],
            quantity=item_data['quantity'],
            price=item_data.get('price')
        )
        db.add(order_item)
    
    db.commit()
    db.refresh(order)
    logger.info(f"Created order: {order.order_number} (ID: {order.id})")
    return order


def get_order(db: Session, order_id: int) -> Optional[Order]:
    """Получить заказ по ID."""
    return db.execute(
        select(Order).where(Order.id == order_id)
    ).scalar_one_or_none()


def get_order_by_number(db: Session, order_number: str) -> Optional[Order]:
    """Получить заказ по номеру."""
    return db.execute(
        select(Order).where(Order.order_number == order_number)
    ).scalar_one_or_none()


def get_orders(
    db: Session,
    warehouse_id: int = None,
    order_type: OrderType = None,
    status: OrderStatus = None,
    limit: int = 100
) -> List[Order]:
    """Получить список заказов с фильтрацией."""
    query = select(Order).order_by(desc(Order.created_at)).limit(limit)
    
    if warehouse_id:
        query = query.where(Order.warehouse_id == warehouse_id)
    if order_type:
        query = query.where(Order.type == order_type)
    if status:
        query = query.where(Order.status == status)
    
    return db.execute(query).scalars().all()


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus
) -> Optional[Order]:
    """Обновить статус заказа."""
    order = get_order(db, order_id)
    if not order:
        return None
    
    order.status = new_status
    
    if new_status == OrderStatus.completed:
        order.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    logger.info(f"Updated order {order_id} status to {new_status}")
    return order


def complete_order(
    db: Session,
    order_id: int,
    user_id: int
) -> Order:
    """
    Завершить заказ и создать соответствующие движения товаров.
    """
    order = get_order(db, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")
    
    if order.status == OrderStatus.completed:
        raise ValueError("Заказ уже завершен")
    
    # Определяем тип движения в зависимости от типа заказа
    movement_type_map = {
        OrderType.purchase: MovementType.in_,  # Закупка = приход
        OrderType.sale: MovementType.out,      # Продажа = расход
        OrderType.production: MovementType.in_  # Производство = приход
    }
    
    movement_type = movement_type_map.get(order.type)
    
    # Создаем движения для каждой позиции заказа
    for item in order.items:
        create_movement(
            db=db,
            warehouse_id=order.warehouse_id,
            sku_id=item.sku_id,
            movement_type=movement_type,
            quantity=item.quantity,
            user_id=user_id,
            notes=f"Заказ {order.order_number}"
        )
    
    # Обновляем статус заказа
    order.status = OrderStatus.completed
    order.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    logger.info(f"Completed order {order.order_number}")
    return order


def cancel_order(db: Session, order_id: int) -> Order:
    """Отменить заказ."""
    order = get_order(db, order_id)
    if not order:
        raise ValueError(f"Заказ {order_id} не найден")
    
    if order.status == OrderStatus.completed:
        raise ValueError("Нельзя отменить завершенный заказ")
    
    order.status = OrderStatus.cancelled
    db.commit()
    db.refresh(order)
    logger.info(f"Cancelled order {order.order_number}")
    return order
