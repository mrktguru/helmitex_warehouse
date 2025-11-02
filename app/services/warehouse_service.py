"""
Сервис для работы со складами.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Warehouse
from app.logger import get_logger

logger = get_logger("warehouse_service")


def create_warehouse(
    db: Session,
    name: str,
    location: str = None,
    is_default: bool = False
) -> Warehouse:
    """Создать новый склад."""
    warehouse = Warehouse(
        name=name,
        location=location,
        is_default=is_default
    )
    db.add(warehouse)
    db.flush()
    db.refresh(warehouse)
    logger.info(f"Created warehouse: {name} (ID: {warehouse.id})")
    return warehouse


def get_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
    """Получить склад по ID."""
    return db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    ).scalar_one_or_none()


def get_default_warehouse(db: Session) -> Optional[Warehouse]:
    """Получить склад по умолчанию."""
    warehouse = db.execute(
        select(Warehouse).where(Warehouse.is_default == True)
    ).scalar_one_or_none()
    
    # Если нет склада по умолчанию, берем первый
    if not warehouse:
        warehouse = db.execute(
            select(Warehouse).limit(1)
        ).scalar_one_or_none()
    
    return warehouse


def get_all_warehouses(db: Session) -> List[Warehouse]:
    """Получить все склады."""
    return db.execute(select(Warehouse)).scalars().all()


def update_warehouse(
    db: Session,
    warehouse_id: int,
    name: str = None,
    location: str = None,
    is_default: bool = None
) -> Optional[Warehouse]:
    """Обновить данные склада."""
    warehouse = get_warehouse(db, warehouse_id)
    if not warehouse:
        return None
    
    if name:
        warehouse.name = name
    if location:
        warehouse.location = location
    if is_default is not None:
        # Если устанавливаем этот склад как default, снимаем флаг с других
        if is_default:
            for wh in db.execute(select(Warehouse)).scalars().all():
                wh.is_default = False
        warehouse.is_default = is_default
    
    db.flush()
    db.refresh(warehouse)
    logger.info(f"Updated warehouse {warehouse_id}")
    return warehouse


def set_default_warehouse(db: Session, warehouse_id: int) -> Optional[Warehouse]:
    """Установить склад как склад по умолчанию."""
    # Снимаем флаг default со всех складов
    for wh in db.execute(select(Warehouse)).scalars().all():
        wh.is_default = False
    
    # Устанавливаем флаг для выбранного склада
    warehouse = get_warehouse(db, warehouse_id)
    if warehouse:
        warehouse.is_default = True
        db.flush()
        db.refresh(warehouse)
        logger.info(f"Set warehouse {warehouse_id} as default")
    
    return warehouse
