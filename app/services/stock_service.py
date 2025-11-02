"""
Сервис для работы с остатками на складе.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from app.database.models import Stock, SKU, Warehouse
from app.logger import get_logger

logger = get_logger("stock_service")


def get_stock(db: Session, warehouse_id: int, sku_id: int) -> Optional[Stock]:
    """Получить остаток товара на складе."""
    return db.execute(
        select(Stock).where(
            Stock.warehouse_id == warehouse_id,
            Stock.sku_id == sku_id
        )
    ).scalar_one_or_none()


def get_warehouse_stock(db: Session, warehouse_id: int) -> List[Stock]:
    """Получить все остатки на складе."""
    return db.execute(
        select(Stock).where(Stock.warehouse_id == warehouse_id)
    ).scalars().all()


def get_sku_stock_all_warehouses(db: Session, sku_id: int) -> List[Stock]:
    """Получить остатки товара на всех складах."""
    return db.execute(
        select(Stock).where(Stock.sku_id == sku_id)
    ).scalars().all()


def update_stock(
    db: Session,
    warehouse_id: int,
    sku_id: int,
    quantity_change: float
) -> Stock:
    """
    Обновить остаток товара на складе.
    quantity_change может быть положительным (приход) или отрицательным (расход).
    """
    stock = get_stock(db, warehouse_id, sku_id)
    
    if not stock:
        # Создаем новую запись остатка
        if quantity_change < 0:
            raise ValueError(f"Невозможно создать остаток с отрицательным количеством: {quantity_change}")
        stock = Stock(
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            quantity=quantity_change
        )
        db.add(stock)
    else:
        # Обновляем существующий остаток
        new_quantity = stock.quantity + quantity_change
        if new_quantity < 0:
            raise ValueError(f"Недостаточно товара на складе. Доступно: {stock.quantity}, требуется: {abs(quantity_change)}")
        stock.quantity = new_quantity
        stock.updated_at = datetime.utcnow()
    
    db.flush()
    db.refresh(stock)
    logger.info(f"Updated stock: warehouse={warehouse_id}, sku={sku_id}, change={quantity_change}, new_qty={stock.quantity}")
    return stock


def check_low_stock(db: Session, warehouse_id: int = None) -> List[dict]:
    """
    Проверить товары с низким остатком (ниже min_stock).
    Возвращает список словарей с информацией о товарах.
    """
    query = select(Stock, SKU).join(SKU).where(Stock.quantity < SKU.min_stock)
    
    if warehouse_id:
        query = query.where(Stock.warehouse_id == warehouse_id)
    
    results = db.execute(query).all()
    
    low_stock_items = []
    for stock, sku in results:
        low_stock_items.append({
            'warehouse_id': stock.warehouse_id,
            'sku_id': sku.id,
            'sku_code': sku.code,
            'sku_name': sku.name,
            'current_quantity': stock.quantity,
            'min_stock': sku.min_stock,
            'unit': sku.unit
        })
    
    return low_stock_items


def get_total_stock_value(db: Session, warehouse_id: int = None) -> dict:
    """Получить общую статистику по остаткам."""
    query = select(Stock)
    if warehouse_id:
        query = query.where(Stock.warehouse_id == warehouse_id)
    
    stocks = db.execute(query).scalars().all()
    
    total_items = len(stocks)
    total_quantity = sum(s.quantity for s in stocks)
    
    return {
        'total_items': total_items,
        'total_quantity': total_quantity
    }
