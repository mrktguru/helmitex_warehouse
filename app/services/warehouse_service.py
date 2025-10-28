"""
Сервис для работы со складами.
"""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Warehouse
from app.logger import get_logger

logger = get_logger("warehouse_service")


def create_warehouse(db: Session, name: str, location: str = None) -> Warehouse:
    """Создать новый склад."""
    warehouse = Warehouse(name=name, location=location)
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    logger.info(f"Created warehouse: {name} (ID: {warehouse.id})")
    return warehouse


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    """Получить склад по ID."""
    return db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    ).scalar_one_or_none()


def get_all_warehouses(db: Session) -> List[Warehouse]:
    """Получить все склады."""
    return db.execute(select(Warehouse)).scalars().all()


def update_warehouse(
    db: Session,
    warehouse_id: int,
    name: str = None,
    location: str = None
) -> Warehouse:
    """Обновить данные склада."""
    warehouse = get_warehouse(db, warehouse_id)
    if not warehouse:
        return None
    
    if name:
        warehouse.name = name
    if location:
        warehouse.location = location
    
    db.commit()
    db.refresh(warehouse)
    logger.info(f"Updated warehouse {warehouse_id}")
    return warehouse
